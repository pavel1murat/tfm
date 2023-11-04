#!/bin/env bash
#------------------------------------------------------------------------------
# some info on running processes
# call signature: artdaq_process_info.sh <partition>
#------------------------------------------------------------------------------
source $TFM_DIR/bin/tfm_utils.sh
partition=0
if [ -n $1 ] ; then partition=$1 ; fi

scriptdir="$(dirname "$0")"
source $scriptdir/package_setup.sh xmlrpc_c

xmlrpc_retval=$?

if [[ "$xmlrpc_retval" != "0" ]]; then
    echo "Problem attempting to setup xmlrpc_c package" >&2
    exit 40
fi

port=`tfm_port $partition`
cmd="xmlrpc http://localhost:$partition/RPC2 artdaq_process_info daqint"
eval $cmd

exit 0
