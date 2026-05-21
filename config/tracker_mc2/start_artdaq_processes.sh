# the file is auto-generated, dont edit
set +C
source $MU2E_DAQ_DIR/config/scripts/auto_setup.sh
export MIDAS_SERVER_HOST=mu2e-dl-01-data
export MIDAS_EXPT_NAME=tracker
export FHICL_FILE_PATH=/home/mu2etrk/daquser_002/config/artdaq:/home/mu2etrk/daquser_002/spack/var/spack/environments/v001:/home/mu2etrk/daquser_002/spack/var/spack/environments/v001/.spack-env/view/fcl
export ARTDAQ_RUN_NUMBER=121752
export ARTDAQ_LOG_ROOT=/scratch/mu2e/mu2etrk/daquser_002_v001/logs
export ARTDAQ_LOG_FHICL=/tmp/messagefacility_partition11_mu2etrk.fcl
export ARTDAQ_PARTITION_NUMBER=<bound method Component.partition of <tfm.rc.control.farm_manager.FarmManager object at 0x7fbd7da81c10>>
export ARTDAQ_PORTS_PER_PARTITION=1000
export ARTDAQ_BASE_PORT_NUMBER=10000

nodename=`hostname -s`

pmt_log_fn=/scratch/mu2e/mu2etrk/daquser_002_v001/logs/pmt/pmt_121752_${nodename}_mu2etrk_partition_11_20260515170114
/home/mu2etrk/daquser_002/spack/var/spack/environments/v001/.spack-env/view/bin/mopup_shmem.sh 11 --force >> $pmt_log_fn 2>&1

if   [ nodename == "mu2e-dl-01" ] ; then
    nohup datalogger   -c "id: 21301 commanderPluginType: xmlrpc rank: 301 application_name: dl01 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ nodename == "mu2e-trk-01" ] ; then
    nohup boardreader  -c "id: 21101 commanderPluginType: xmlrpc rank: 101 application_name: br01 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21102 commanderPluginType: xmlrpc rank: 102 application_name: br02 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21201 commanderPluginType: xmlrpc rank: 201 application_name: eb01 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ nodename == "mu2e-trk-02" ] ; then
    nohup boardreader  -c "id: 21103 commanderPluginType: xmlrpc rank: 103 application_name: br03 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21104 commanderPluginType: xmlrpc rank: 104 application_name: br04 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21202 commanderPluginType: xmlrpc rank: 202 application_name: eb02 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ nodename == "mu2e-trk-03" ] ; then
    nohup boardreader  -c "id: 21105 commanderPluginType: xmlrpc rank: 105 application_name: br05 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21106 commanderPluginType: xmlrpc rank: 106 application_name: br06 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21203 commanderPluginType: xmlrpc rank: 203 application_name: eb03 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ nodename == "mu2e-trk-04" ] ; then
    nohup boardreader  -c "id: 21107 commanderPluginType: xmlrpc rank: 107 application_name: br07 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21108 commanderPluginType: xmlrpc rank: 108 application_name: br08 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21204 commanderPluginType: xmlrpc rank: 204 application_name: eb04 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ nodename == "mu2e-trk-06" ] ; then
    nohup boardreader  -c "id: 21111 commanderPluginType: xmlrpc rank: 111 application_name: br11 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21112 commanderPluginType: xmlrpc rank: 112 application_name: br12 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21206 commanderPluginType: xmlrpc rank: 206 application_name: eb06 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ nodename == "mu2e-trk-07" ] ; then
    nohup boardreader  -c "id: 21113 commanderPluginType: xmlrpc rank: 113 application_name: br13 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21114 commanderPluginType: xmlrpc rank: 114 application_name: br14 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21207 commanderPluginType: xmlrpc rank: 207 application_name: eb07 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ nodename == "mu2e-trk-08" ] ; then
    nohup boardreader  -c "id: 21115 commanderPluginType: xmlrpc rank: 115 application_name: br15 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21116 commanderPluginType: xmlrpc rank: 116 application_name: br16 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21208 commanderPluginType: xmlrpc rank: 208 application_name: eb08 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ nodename == "mu2e-trk-09" ] ; then
    nohup boardreader  -c "id: 21117 commanderPluginType: xmlrpc rank: 117 application_name: br17 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21118 commanderPluginType: xmlrpc rank: 118 application_name: br18 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21209 commanderPluginType: xmlrpc rank: 209 application_name: eb09 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ nodename == "mu2e-trk-18" ] ; then
    nohup boardreader  -c "id: 21135 commanderPluginType: xmlrpc rank: 135 application_name: br35 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21136 commanderPluginType: xmlrpc rank: 136 application_name: br36 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21218 commanderPluginType: xmlrpc rank: 218 application_name: eb18 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ nodename == "mu2e-calo-13" ] ; then
    nohup boardreader  -c "id: 21100 commanderPluginType: xmlrpc rank: 100 application_name: br00 partition_number: 11" >> $pmt_log_fn 2>&1 &
fi
