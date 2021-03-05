#!/bin/bash

## TODO: figure out how to get certs


# defaults
tgen_port="8888"
start_obfs5_port="9876"
num_obfs5_instances="10"
listen_ip="192.168.0.6"
obfs5_client=$HOME/obfsX/obfs4proxy/obfs4proxy
obfs5_certs_path="obfs5-certs"
pt_proxy="pt-proxy.py"

while getopts ":ht:p:l:n:P:c:C:" opt; do
    case ${opt} in
        h ) # process option h
            echo "Usage:"
            echo "  run-client-pt-proxy.sh -P PT_PROXY_PATH -c OBFS5_CLIENT_PATH -n NUM_OBFS5_INSTANCES -t TGEN_PORT -p OBFS5_START_PORT -l LISTEN_IP -C OBFS5_CERTS_PATH"
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
        l )
            listen_ip=$OPTARG
            ;;
        C )
            obfs5_certs_path=$OPTARG
            ;;            
        t )
            tgen_port=$OPTARG
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
echo "tgen port = ${tgen_port}"
echo "obfs5 port start = ${start_obfs5_port}"
echo "listen IP = ${listen_ip}"

for ((i=0;i<$num_obfs5_instances;i++));
do
    state_dir="state_obfs5_${i}/"
    log_file="log_obfs5_${i}.log"

    let server_port=$i+$start_obfs5_port

    if [ \! -e "${obfs5_certs_path}/cert_${i}" ]; then
        echo
        echo
        echo "You need to provide a cert file at ${obfs5_certs_path}/cert_${i}"
        echo "You can generate that with something like:"
        echo '   echo -n "cert=" && grep cert state_obfs5_3/obfs4_bridgeline.txt | cut -d "=" -f 2 | sed -e '\'s/ /\;/\'''    
        exit 1
    else
        cert=`cat ${obfs5_certs_path}/cert_${i}`
    fi

    echo "Starting up pt-proxy instance ${i}..."
    python ${pt_proxy} -t obfs5 -l ${log_file} -d ${state_dir} -b ${obfs5_client} server -S ${listen_ip}:${server_port} -p ${tgen_port} -i "${cert}" --help

done


