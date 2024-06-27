#!/bin/env bash
#------------------------------------------------------------------------------
source $SPACK_VIEW/tfm/bin/tfm_utils.sh

if ((`n_tfm_instances` > 0 )); then list_tfm_instances 
else                           echo "No TFM instances are running"
fi
