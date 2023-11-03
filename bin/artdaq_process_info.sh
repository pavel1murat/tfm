#!/bin/env bash

. $ARTDAQ_DAQINTERFACE_DIR/bin/exit_if_bad_environment.sh
. $ARTDAQ_DAQINTERFACE_DIR/bin/daqinterface_functions.sh
daqinterface_preamble

scriptdir="$(dirname "$0")"
. $scriptdir/package_setup.sh xmlrpc_c

xmlrpc_retval=$?

if [[ "$xmlrpc_retval" != "0" ]]; then
    echo "Problem attempting to setup xmlrpc_c package" >&2
    exit 40
fi

full_cmd="xmlrpc http://localhost:$DAQINTERFACE_PORT/RPC2 artdaq_process_info daqint"
eval $full_cmd

exit 0
