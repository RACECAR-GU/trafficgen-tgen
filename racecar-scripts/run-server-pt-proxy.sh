#!/bin/bash

# defaults
start_localhost_port="8888"
start_obfs5_port="9876"

while getopts ":hb:p:" opt; do
    case ${opt} in
        h ) # process option h
            echo "Usage:"
            echo "  run-server-pt-proxy.sh -b LOCALHOST_START_PORT -p OBFS5_START_PORT"
            exit 0
            ;;
        b )
            start_localhost_port=$OPTARG
            ;;
        p )
            start_obfs5_port=$OPTARG
            ;;
        \? )
            echo "Invalid usage.  See '-h' option"
            exit 1
            ;;
    esac
done

echo "localhost bind port start = ${start_localhost_port}"
echo "obfs5 port start = ${start_obfs5_port}"
# python pt-proxy.py -t obfs5 -l log.log -d state/ -b ~/obfsX/obfs4proxy/obfs4proxy server -S 192.168.0.6:9876 -p 8888

