#!/bin/env bash
script=`basename $0`
#------------------------------------------------------------------------------
# some info on running processes
# call signature: artdaq_process_info.sh <partition>
#------------------------------------------------------------------------------
function artdaq_process_info_() {
    local debug=0
    source $SPACK_VIEW/tfm/bin/tfm_utils.sh

    if [ ".$1" != "." ] ; then 
        if [ $debug != 0 ] ; then echo [$script:$LINENO] : \$1=$1 ; fi
#------------------------------------------------------------------------------
# assume partition is defined on the comamnd line, so this is a main branch
#------------------------------------------------------------------------------
        partition=$1 ; 
        port=`tfm_port $partition`
    else
#------------------------------------------------------------------------------
# partition has not been defined on the command line, hope for TFM_PORT
#------------------------------------------------------------------------------
        if [ $debug != 0 ] ; then echo [$script:$LINENO] : TFM_PORT=$TFM_PORT ; fi
        if [ -n $TFM_PORT ] ; then
            port=$TFM_PORT
        else
            echo "ERROR: port is not defined , RC=1"
            return 1
        fi
    fi

    cmd="xmlrpc http://localhost:$port/RPC2 artdaq_process_info daqint"
    if [ $debug != 0 ] ; then echo [$script:$LINENO] : cmd=$cmd ; fi
    $cmd
}
#------------------------------------------------------------------------------
# always make it a function
#------------------------------------------------------------------------------
artdaq_process_info_ $@
rc=$?
exit $rc
