#!/bin/env bash

source $TFM_DIR/bin/tfm_utils.sh
daqinterface_preamble

xmlrpc http://localhost:$DAQINTERFACE_PORT/RPC2 listdaqcomps
exit $?
