#!/bin/env bash

source $SPACK_VIEW/tfm/bin/tfm_utils.sh
daqinterface_preamble

xmlrpc http://localhost:$DAQINTERFACE_PORT/RPC2 listdaqcomps
exit $?
