#!/bin/env bash

. $ARTDAQ_DAQINTERFACE_DIR/bin/exit_if_bad_environment.sh
. $ARTDAQ_DAQINTERFACE_DIR/bin/daqinterface_functions.sh
daqinterface_preamble

. $ARTDAQ_DAQINTERFACE_DIR/bin/package_setup.sh xmlrpc_c

xmlrpc_retval=$?

if [[ "$xmlrpc_retval" != "0" ]]; then
    echo "Problem attempting to setup xmlrpc_c package" >&2
    exit 40
fi

xmlrpc http://localhost:$DAQINTERFACE_PORT/RPC2 listconfigs
exit $?
