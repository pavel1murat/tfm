#!/usr/bin/bash 
#------------------------------------------------------------------------------
# call format: tfm_port $partition
# uses env(ARTDAQ_BASE_PORT)  and env(ARTDAQ_PORTS_PER_PARTITION) set by source_me
#------------------------------------------------------------------------------
function tfm_port() {
    partition=$1
    echo $(($ARTDAQ_BASE_PORT + $partition * $ARTDAQ_PORTS_PER_PARTITION))
}

#------------------------------------------------------------------------------
function tfm_list_instances() {
    ps aux | grep "bin/tfm_launch_fe.py" | grep -v grep | \
        awk '{ print "TFM instance was launched at "$9" by "$1" in partition "$14" on port "$NF  }'
}

function tfm_n_instances() {
    echo `tfm_list_instances | wc -l`
}

#------------------------------------------------------------------------------
function port_disclaimer_message() {
    if (( `tfm_n_instances` > 1 )); then
        cat <<EOF
This command will be sent to a DAQInterface instance in partition
$ARTDAQ_PARTITION_NUMBER listening on port TFM_PORT=$TFM_PORT if it exists
To start TF manager on another partition, execute 
"export ARTDAQ_PARTITION_NUMBER=<desired partition number>"
EOF
        tfm_list_instances
    fi
}

#------------------------------------------------------------------------------
# rc=140: no running TFM instances
#------------------------------------------------------------------------------
function tfm_preamble() {
    n=`tfm_n_instances`
    if   (( $n  > 1)); then port_disclaimer_message
    elif (( $n == 0)); then
        cat <<EOF
No running TFM instances found. EXIT rc=140 
EOF
        exit 140
    fi
}
