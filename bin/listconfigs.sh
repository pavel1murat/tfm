#!/bin/env bash

. $TFM_DIR/bin/daqinterface_functions.sh
daqinterface_preamble

xmlrpc http://localhost:$TFM_PORT/RPC2 listconfigs
exit $?
