#!/bin/env bash

if (( "$#" != 3 )); then
    echo "Usage: "$( basename $0 )" <name> <masktype> <maskval>" >&2
    exit 1
fi

name=$1
masktype=$2
maskval=$3

. $ARTDAQ_DAQINTERFACE_DIR/bin/exit_if_bad_environment.sh
. $ARTDAQ_DAQINTERFACE_DIR/bin/daqinterface_functions.sh
daqinterface_preamble


. $ARTDAQ_DAQINTERFACE_DIR/bin/package_setup.sh xmlrpc_c

xmlrpc_retval=$?

if [[ "$xmlrpc_retval" != "0" ]]; then
    echo "Problem attempting to setup xmlrpc_c package" >&2
    exit 40
fi


xmlrpc http://localhost:$DAQINTERFACE_PORT/RPC2 trace_set daqint 'struct/{name:s/'$name',masktype:s/'$masktype',maskval:s/'$maskval'}'
retval="$?"

if [[ "$retval" != "0" ]]; then
    echo "Something went wrong in the xmlrpc call for trace_set; returned value was $retval"
    exit $retval
fi

exit 0
