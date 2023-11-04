#!/usr/bin/bash
#------------------------------------------------------------------------------
# during the transition, test functions, ultimately, throw them away
#------------------------------------------------------------------------------
source $PWD/srcs/tfm/bin/tfm_util_functions.sh

export           ARTDAQ_BASE_PORT=10000
export ARTDAQ_PORTS_PER_PARTITION=1000

partition=2
echo "1. test tfm_port for partition $partition"
echo "   x="`tfm_port $partition`


echo "2. test tfm_list_instances:"
echo "   running tfm instances:" `tfm_list_instances`

echo "3. test tfm_n_instances:"
echo "   N(running tfm_n_instances)": `tfm_n_instances`


echo "4. test tfm_preamble"
echo "   tfm_preamble:"`tfm_preamble`

