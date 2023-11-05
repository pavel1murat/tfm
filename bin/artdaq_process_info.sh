#!/bin/env bash
script=`basename $0`
#------------------------------------------------------------------------------
# some info on running processes
# call signature: artdaq_process_info.sh <partition>
#------------------------------------------------------------------------------
function artdaq_process_info() {
    local debug=0
    source $TFM_DIR/bin/tfm_utils.sh
    port=$TFM_PORT
    if [ -n $1 ] ; then 
        partition=$1 ; 
        port=`tfm_port $partition`
    fi

    cmd="xmlrpc http://localhost:$port/RPC2 artdaq_process_info daqint"
    if [ $debug != 0 ] ; then echo [$script:$LINENO] : cmd=$cmd ; fi
    $cmd
}
#------------------------------------------------------------------------------
# always make it a function
#------------------------------------------------------------------------------
artdaq_process_info $@
rc=$?
exit $rc
