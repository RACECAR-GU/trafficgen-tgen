"""
A program to generate a bunch of maybe plausible looking different protocols

MAJOR TODOs:
* add better traffic shaping and delays
"""

import sys
import networkx as nx
import argparse
import logging
import os
import random
import time
import scapy
import signal
import subprocess


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument( '-g', '--outputdir', dest='outputdir', default='graphs/', help='directory to place graph output files')
    parser.add_argument( '-c', '--capdir', dest='capdir', default='captures/', help='directory to place pcap files')
    parser.add_argument( '-n', '--numprotos', dest='number_of_protocols', type=int, default=10, help='number of protocols')
    parser.add_argument( '-s', '--randseed', dest='seed', type=int, default=time.time(), help='RNG seed (not cryptographically secure)')
    parser.add_argument( '-p', '--peer', dest='peer', required=True, help='host:port to connect to')
    parser.add_argument( '-t', '--tgen', dest='tgen', default='../build/src/tgen', help='path to tgen')
    parser.add_argument( '-r', '--run', dest='run_tgen', default=False, action='store_true', help='run tgen')
    parser.add_argument( '-R', '--runs', dest='runs', type=int, default=1, help='number of iterations of each protocol to run')
    parser.add_argument( '-i', '--capinterface', dest='cap_interface', default="eno1", help='interface to capture packets')
    args = parser.parse_args()
    return args


def silent_mkdir( dir ):
    try:
        os.mkdir( dir, mode=0o750 )
    except FileExistsError:
        pass
    

def generate_packetflow_markov_model( args, protocol_number ):
    logging.info( 'creating a new packetflow Markov Model; protocol number %d' % protocol_number )
    G = nx.DiGraph()

    switch_bias_sending = random.uniform(0.01,0.3)
    switch_bias_receiving = random.uniform(0.01,0.3)

    logging.info( f'send/recv switch biases are {switch_bias_sending} and {switch_bias_receiving}')

    G.add_node('s0', type="state", name='start')
    G.add_node('s1', type="state", name='clientsend')
    G.add_node('s2', type="state", name='serversend')
    G.add_node('s3', type="state", name='devnull')

    G.add_node('o1', type="observation", name='+')  # client to server
    G.add_node('o2', type="observation", name='-')  # server to client
    G.add_node('o3', type="observation", name='F')  # stop sending

    # we start by either having the client or server send
    G.add_edge('s0', 's1', type='transition', weight=1.0)
    G.add_edge('s0', 's2', type='transition', weight=1.0)

    # moving between send and receive states is biased in favor of not switching
    G.add_edge('s1', 's2', type='transition', weight=switch_bias_sending)
    G.add_edge('s1', 's1', type='transition', weight=(1-switch_bias_sending))   # don't switch
    
    G.add_edge('s2', 's1', type='transition', weight=switch_bias_receiving)
    G.add_edge('s2', 's2', type='transition', weight=(1-switch_bias_receiving))   # don't switch

    # define some emissions for sending and receiving states
    # TODO: random the delays; remove hardcoded stuff
    G.add_edge('s1', 'o1', type='emission', weight=1.0, distribution='exponential', param_rate=100.0)
    G.add_edge('s2', 'o2', type='emission', weight=1.0, distribution='exponential', param_rate=100.0)
    
    # add some probability of ending
    #G.add_edge('s1', 'o3', type='emission', weight=0.01, distribution='uniform', param_low=50, param_high=500)
    #G.add_edge('s2', 'o3', type='emission', weight=0.03, distribution='uniform', param_low=50, param_high=500)
    
    #G.add_edge('s1', 's3', type='transition', weight=0.0001)
    #G.add_edge('s2', 's3', type='transition', weight=0.0001)
    #G.add_edge('s3', 's3', type='transition', weight=1.0)
    #G.add_edge('s3', 'o3', type='emission', weight=1.0, distribution='uniform', param_low=50, param_high=500)

    nx.write_graphml(G, f"{args.outputdir}/protocol{protocol_number}.tgenrc.graphml" )



def generate_client_protocol( args, number_of_protocols ):
    logging.info( 'creating the client, with %d protocols' % number_of_protocols )
    G = nx.DiGraph()

    G.add_node("start", time="1 second", heartbeat="1 second", loglevel="message", peers=args.peer)
    G.add_node("pause", time="5 seconds")
    for i in range(number_of_protocols):
        generate_packetflow_markov_model( args, i )
        G.add_node(f"stream{i}", packetmodelpath=f"{args.outputdir}/protocol{i}.tgenrc.graphml", packetmodelmode="graphml", timeout="10 minutes", stallout="5 minutes")
    
    G.add_edge("start", "pause")
    for i in range(number_of_protocols):
        G.add_edge("pause", f"stream{i}", weight="1.0")     # TODO: wouldn't there be a large outdegree from single pause node?
        G.add_edge(f"stream{i}", "pause")

    nx.write_graphml(G, "%s/client-unclass.tgenrc.graphml" % args.outputdir)



def run_tgen( args ):
    for run in range(args.runs):
        logging.debug( "starting pcap")
        proc = subprocess.Popen( [
            '/usr/sbin/tcpdump',
            '-n', 
            '-i', args.cap_interface,
            '-w', '%s/capture-proto-run-%d.pcap' % (args.capdir,run)
            ] )
        logging.debug( "starting tgen" )
        os.system( "%s %s" % (
            args.tgen,
            os.path.abspath( f"{args.outputdir}/client-unclass.tgenrc.graphml" )
        ))
        logging.debug("stopping tgen and waiting 2 seconds")
        time.sleep(1.5)
        proc.kill()
        time.sleep(0.5)


def main():
    logging.basicConfig(format='%(asctime)s %(message)s',level=logging.DEBUG)

    args = parse_args()
    logging.info( 'running with arguments: %s' % args)
    random.seed( args.seed )

    silent_mkdir( args.outputdir )
    if args.capdir is not None:
        silent_mkdir( args.capdir )
    

    # a simple server
    logging.info( 'creating the server protocol')
    G_server = nx.DiGraph()
    G_server.add_node("start", serverport="8888", heartbeat="1 second", loglevel="message")
    nx.write_graphml( 
        G_server, 
        "%s/proto-server-stream.tgenrc.graphml" % args.outputdir 
    )

    generate_client_protocol( args, args.number_of_protocols )

    if args.run_tgen is True:
        logging.warning( "you should run the noroot_tcpdump.sh script to ensure this user can actually run tcpdump")
        logging.info( 'running tgen' )
        run_tgen( args )

    return 0        # all's well that ends well


if __name__ == '__main__': sys.exit(main())
