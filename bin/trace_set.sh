#!/bin/env bash
#------------------------------------------------------------------------------
# depends on XMLRPC_C, that is addressed via UPS setup
#------------------------------------------------------------------------------
source $ARTDAQ_DAQINTERFACE_DIR/bin/tfm_utils.sh
daqinterface_preamble

if (( "$#" != 3 )); then
    echo "Usage: "$( basename $0 )" <name> <masktype> <maskval>" >&2
    exit 1
fi

    name=$1
masktype=$2
 maskval=$3

xmlrpc http://localhost:$TFM_PORT/RPC2 trace_set daqint 'struct/{name:s/'$name',masktype:s/'$masktype',maskval:s/'$maskval'}'
retval="$?"

if [[ "$retval" != "0" ]]; then
    echo "Something went wrong in the xmlrpc call for trace_set; returned value was $retval"
    exit $retval
fi

exit 0
