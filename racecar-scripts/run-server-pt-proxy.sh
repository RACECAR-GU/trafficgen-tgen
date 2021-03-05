#!/bin/bash

echo """
THIS SCRIPT ISN'T FUNCTIONAL YET.

DON'T USE IT.
"""


# defaults
start_localhost_port="8888"
start_obfs5_port="9876"
num_obfs5_instances="10"
dest="192.168.0.6"
obfs5_client=$HOME/obfsX/obfs4proxy/obfs4proxy
pt_proxy="pt-proxy.py"

while getopts ":hb:p:d:n:P:c:" opt; do
    case ${opt} in
        h ) # process option h
            echo "Usage:"
            echo "  run-server-pt-proxy.sh -P PT_PROXY_PATH -c OBFS5_CLIENT_PATH -n NUM_OBFS5_INSTANCES -b LOCALHOST_START_PORT -p OBFS5_START_PORT -d DEST"
            exit 0
            ;;
        P )
            pt_proxy=$OPTARG
            ;;
        c )
            obfs5_client=$OPTARG
            ;;
        n )
            num_obfs5_instances=$OPTARG
            ;;
        d )
            dest=$OPTARG
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

echo "number of obfs5 instances = ${num_obfs5_instances}"
echo "localhost bind port start = ${start_localhost_port}"
echo "obfs5 port start = ${start_obfs5_port}"
echo "destination = ${dest}"

for ((i=0;i<$num_obfs5_instances;i++));
do
    state_dir="state_obfs5_${i}/"
    log_file="log_obfs5_${i}.log"

    let server_port=$i+$start_obfs5_port
    let local_port=$i+$start_localhost_port

    echo "Starting up pt-proxy instance ${i}..."
    python ${pt_proxy} -t obfs5 -l ${log_file} -d ${state_dir} -b ${obfs5_client} server -S ${dest}:${server_port} -p ${local_port} &
done

# next, print out the bridge lines
for ((i=0;i<$num_obfs5_instances;i++));
do
    state_dir="state_obfs5_${i}/"
    echo "bridge line for obfs5 instance ${i}"
    grep iat-mode ${state_dir}/obfs4_bridgeline.txt
done

