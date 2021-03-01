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
    


def generate_protocol( args, proto_num ):

    # TODO: basically, everything hard-coded should really be a configurable option

    # a client
    num_streams = random.randint(1,5)          # TODO
    G_client = nx.DiGraph()
    G_client.add_node("start", time="1 second", heartbeat="1 second", loglevel="message", peers=args.peer)
    G_client.add_node("end", time="1 minute", count="%s" % num_streams, recvsize="1 GiB", sendsize="1 GiB")

    for stream_id in range(num_streams):
        G_client.add_node("stream%d" % stream_id,
            sendsize="%d kib" % random.randint(1,10),
            recvsize="%d kib" % random.randint(1,100),
        )
        G_client.add_node(
            "pause%d" % stream_id,
            time="%d ms" % random.randint(0,1000)
        )


    # connect the graph
    prev_stream = "start"
    for stream_id in range(num_streams):
        G_client.add_edge( 
            prev_stream,
             "pause%d" % stream_id
        )
        G_client.add_edge( 
             "pause%d" % stream_id,
             "stream%d" % stream_id
        )
        prev_stream = "stream%d" % stream_id
    G_client.add_edge( 
        "stream%d" % (num_streams - 1),
        "end")

    nx.write_graphml( 
        G_client, 
        "%s/proto-%d-client-stream.tgenrc.graphml" % (args.outputdir, proto_num) 
    )



def run_tgen( args, proto_num ):
    for run in range(args.runs):
        logging.debug( "starting pcap")
        proc = subprocess.Popen( [
            '/usr/sbin/tcpdump',
            '-n', 
            '-i', args.cap_interface,
            '-w', '%s/capture-proto-%d-run-%d.pcap' % (args.capdir,proto_num,run)
            ] )
        logging.debug( "starting tgen" )
        os.system( "%s %s" % (
            args.tgen,
            os.path.abspath("%s/proto-%d-client-stream.tgenrc.graphml" % (args.outputdir,proto_num))
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



    for i in range(args.number_of_protocols):
        logging.info( 'creating protocol number %d', i )
        generate_protocol( args, i )

    if args.run_tgen is True:
        logging.warning( "you should run the noroot_tcpdump.sh script to ensure this user can ")
        for i in range(args.number_of_protocols):
            logging.info( 'running tgen for protocol %d' % i )
            run_tgen( args, i )

    return 0        # all's well that ends well


if __name__ == '__main__': sys.exit(main())
