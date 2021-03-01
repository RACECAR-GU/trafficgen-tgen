"""
A program to generate a bunch of maybe plausible looking different protocols
"""

import sys
import networkx as nx
import argparse
import logging
import os
import random
import time


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument( '-o', '--outputdir', dest='outputdir', default='graphs/', help='directory to place output files')
    parser.add_argument( '-n', '--numprotos', dest='number_of_protocols', type=int, default=10, help='number of protocols')
    parser.add_argument( '-s', '--randseed', dest='seed', type=int, default=time.time(), help='RNG seed (not cryptographically secure)')
    parser.add_argument( '-p', '--peer', dest='peer', required=True, help='host:port to connect to')
    args = parser.parse_args()
    return args



def generate_protocol( args, proto_num ):

    # TODO: basically, everything hard-coded should really be a configurable option

    # a simple server
    G_server = nx.DiGraph()
    G_server.add_node("start", serverport="8888", heartbeat="1 second", loglevel="message")
    nx.write_graphml( 
        G_server, 
        "%s/proto-%d-server-stream.tgenrc.graphml" % (args.outputdir, proto_num) 
    )

    # a client
    G_client = nx.DiGraph()
    G_client.add_node("start", time="1 second", heartbeat="1 second", loglevel="message", peers=args.peer)
    G_client.add_node("end", time="1 minute", count="1", recvsize="1 GiB", sendsize="1 GiB")

    num_streams = random.randint(1,50)          # TODO
    for stream_id in range(num_streams):
        G_client.add_node("stream%d" % stream_id,
            sendsize="%d kib" % random.randint(1,1000),
            recvsize="%d kib" % random.randint(1,1000),
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




def main():
    logging.basicConfig(format='%(asctime)s %(message)s',level=logging.DEBUG)

    args = parse_args()
    logging.info( 'running with arguments: %s' % args)
    random.seed( args.seed )

    try:
        os.mkdir( args.outputdir, mode=0o755 )
    except FileExistsError:
        pass

    
    for i in range(args.number_of_protocols):
        logging.info( 'creating protocol number %d', i )
        generate_protocol( args, i )



if __name__ == '__main__': sys.exit(main())
