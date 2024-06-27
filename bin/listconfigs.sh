#!/bin/env bash

. $SPACK_VIEW/tfm/bin/daqinterface_functions.sh
daqinterface_preamble

xmlrpc http://localhost:$TFM_PORT/RPC2 listconfigs
exit $?
