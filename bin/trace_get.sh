#!/bin/env bash
#------------------------------------------------------------------------------
source $SPACK_VIEW/tfm/bin/tfm_utils.sh
tfm_preamble

if (( "$#" > 1 )); then
    echo "Usage: "$( basename $0 )" (optional argument to pass to trace_get call - default is \"ALL\")" >&2
    exit 1
fi

trace_get_arg="ALL"
if [[ -n $1 ]]; then trace_get_arg=$1 ; fi

xmlrpc http://localhost:$TFM_PORT/RPC2 trace_get daqint struct/{name:s/$trace_get_arg}
retval="$?"

if [[ "$retval" != "0" ]]; then
    echo "Something went wrong in the xmlrpc call for trace_get; returned value was $retval"
    exit $retval
fi

echo "Results of trace_get.sh call can be found in /tmp/trace_get_<process label>_<tfm_user>_partition${ARTDAQ_PARTITION_NUMBER}.txt"

exit 0
