#!/bin/env bash
#------------------------------------------------------------------------------
source $TFM_DIR/bin/tfm_utils.sh
tfm_preamble

scriptdir="$(dirname "$0")"
. $scriptdir/package_setup.sh xmlrpc_c

xmlrpc_retval=$?

if [[ "$xmlrpc_retval" != "0" ]]; then
    echo "Problem attempting to setup xmlrpc_c package" >&2
    exit 40
fi

full_cmd="xmlrpc http://localhost:$TFM_PORT/RPC2 state daqint "
eval $full_cmd

exit 0
