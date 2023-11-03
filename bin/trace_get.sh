#!/bin/env bash

if (( "$#" > 1 )); then
    echo "Usage: "$( basename $0 )" (optional argument to pass to trace_get call - default is \"ALL\")" >&2
    exit 1
fi

trace_get_arg=ALL

if [[ -n $1 ]]; then
    trace_get_arg=$1
fi

. $ARTDAQ_DAQINTERFACE_DIR/bin/exit_if_bad_environment.sh
. $ARTDAQ_DAQINTERFACE_DIR/bin/daqinterface_functions.sh
daqinterface_preamble


. $ARTDAQ_DAQINTERFACE_DIR/bin/package_setup.sh xmlrpc_c

xmlrpc_retval=$?

if [[ "$xmlrpc_retval" != "0" ]]; then
    echo "Problem attempting to setup xmlrpc_c package" >&2
    exit 40
fi


xmlrpc http://localhost:$DAQINTERFACE_PORT/RPC2 trace_get daqint struct/{name:s/$trace_get_arg}
retval="$?"

if [[ "$retval" != "0" ]]; then
    echo "Something went wrong in the xmlrpc call for trace_get; returned value was $retval"
    exit $retval
fi

echo "Results of trace_get.sh call can be found in /tmp/trace_get_<process label>_<user running daqinterface>_partition${DAQINTERFACE_PARTITION_NUMBER}.txt"

exit 0
