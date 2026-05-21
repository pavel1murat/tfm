# the file is auto-generated, dont edit
set +C
export MU2E_DAQ_DIR=/home/mu2etrk/daquser_002
source $MU2E_DAQ_DIR/config/scripts/quick_setup.sh
export MIDAS_SERVER_HOST=mu2e-dl-01-data
export MIDAS_EXPT_NAME=tracker
export FHICL_FILE_PATH=/home/mu2etrk/daquser_002/config/artdaq:/home/mu2etrk/daquser_002/spack/var/spack/environments/v001:/home/mu2etrk/daquser_002/spack/var/spack/environments/v001/.spack-env/view/fcl
export ARTDAQ_RUN_NUMBER=50109
export ARTDAQ_LOG_ROOT=/scratch/mu2e/mu2etrk/daquser_002_v001/logs
export ARTDAQ_LOG_FHICL=/tmp/messagefacility_partition11_mu2etrk.fcl
export ARTDAQ_PARTITION_NUMBER=11
export ARTDAQ_PORTS_PER_PARTITION=1000
export ARTDAQ_BASE_PORT_NUMBER=10000
cp /home/mu2etrk/daquser_002/config/artdaq/demo_mc2/messagefacility_partition11_mu2etrk.fcl /tmp/.
nodename=`hostname -s`
echo creating /scratch/mu2e/mu2etrk/daquser_002_v001/logs/pmt
if [ ! -d /scratch/mu2e/mu2etrk/daquser_002_v001/logs/pmt ] ; then mkdir -p -m 0775 /scratch/mu2e/mu2etrk/daquser_002_v001/logs/pmt ; fi

pmt_log_fn=/scratch/mu2e/mu2etrk/daquser_002_v001/logs/pmt/pmt_050109_${nodename}_mu2etrk_partition_11_20260517154306
/home/mu2etrk/daquser_002/config/scripts/cleanup_partition 11 >| $pmt_log_fn 2>&1
/home/mu2etrk/daquser_002/spack/var/spack/environments/v001/.spack-env/view/bin/mopup_shmem.sh 11 --force >> $pmt_log_fn 2>&1

if   [ $nodename == "mu2e-dl-01" ] ; then
    nohup datalogger   -c "id: 21301 commanderPluginType: xmlrpc rank: 301 application_name: dl01 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-01" ] ; then
    nohup boardreader  -c "id: 21101 commanderPluginType: xmlrpc rank: 101 application_name: br01 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21102 commanderPluginType: xmlrpc rank: 102 application_name: br02 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21201 commanderPluginType: xmlrpc rank: 201 application_name: eb01 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-02" ] ; then
    nohup boardreader  -c "id: 21103 commanderPluginType: xmlrpc rank: 103 application_name: br03 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21104 commanderPluginType: xmlrpc rank: 104 application_name: br04 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21202 commanderPluginType: xmlrpc rank: 202 application_name: eb02 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-03" ] ; then
    nohup boardreader  -c "id: 21105 commanderPluginType: xmlrpc rank: 105 application_name: br05 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21106 commanderPluginType: xmlrpc rank: 106 application_name: br06 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21203 commanderPluginType: xmlrpc rank: 203 application_name: eb03 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-04" ] ; then
    nohup boardreader  -c "id: 21107 commanderPluginType: xmlrpc rank: 107 application_name: br07 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21108 commanderPluginType: xmlrpc rank: 108 application_name: br08 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21204 commanderPluginType: xmlrpc rank: 204 application_name: eb04 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-05" ] ; then
    nohup boardreader  -c "id: 21109 commanderPluginType: xmlrpc rank: 109 application_name: br09 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21110 commanderPluginType: xmlrpc rank: 110 application_name: br10 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21205 commanderPluginType: xmlrpc rank: 205 application_name: eb05 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-06" ] ; then
    nohup boardreader  -c "id: 21111 commanderPluginType: xmlrpc rank: 111 application_name: br11 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21112 commanderPluginType: xmlrpc rank: 112 application_name: br12 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21206 commanderPluginType: xmlrpc rank: 206 application_name: eb06 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-07" ] ; then
    nohup boardreader  -c "id: 21113 commanderPluginType: xmlrpc rank: 113 application_name: br13 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21114 commanderPluginType: xmlrpc rank: 114 application_name: br14 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21207 commanderPluginType: xmlrpc rank: 207 application_name: eb07 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-08" ] ; then
    nohup boardreader  -c "id: 21115 commanderPluginType: xmlrpc rank: 115 application_name: br15 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21116 commanderPluginType: xmlrpc rank: 116 application_name: br16 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21208 commanderPluginType: xmlrpc rank: 208 application_name: eb08 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-09" ] ; then
    nohup boardreader  -c "id: 21117 commanderPluginType: xmlrpc rank: 117 application_name: br17 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21118 commanderPluginType: xmlrpc rank: 118 application_name: br18 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21209 commanderPluginType: xmlrpc rank: 209 application_name: eb09 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-10" ] ; then
    nohup boardreader  -c "id: 21119 commanderPluginType: xmlrpc rank: 119 application_name: br19 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21120 commanderPluginType: xmlrpc rank: 120 application_name: br20 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21210 commanderPluginType: xmlrpc rank: 210 application_name: eb10 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-11" ] ; then
    nohup boardreader  -c "id: 21121 commanderPluginType: xmlrpc rank: 121 application_name: br21 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21122 commanderPluginType: xmlrpc rank: 122 application_name: br22 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21211 commanderPluginType: xmlrpc rank: 211 application_name: eb11 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-12" ] ; then
    nohup boardreader  -c "id: 21123 commanderPluginType: xmlrpc rank: 123 application_name: br23 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21124 commanderPluginType: xmlrpc rank: 124 application_name: br24 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21212 commanderPluginType: xmlrpc rank: 212 application_name: eb12 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-13" ] ; then
    nohup boardreader  -c "id: 21125 commanderPluginType: xmlrpc rank: 125 application_name: br25 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21126 commanderPluginType: xmlrpc rank: 126 application_name: br26 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21213 commanderPluginType: xmlrpc rank: 213 application_name: eb13 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-14" ] ; then
    nohup boardreader  -c "id: 21127 commanderPluginType: xmlrpc rank: 127 application_name: br27 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21128 commanderPluginType: xmlrpc rank: 128 application_name: br28 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21214 commanderPluginType: xmlrpc rank: 214 application_name: eb14 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-15" ] ; then
    nohup boardreader  -c "id: 21129 commanderPluginType: xmlrpc rank: 129 application_name: br29 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21130 commanderPluginType: xmlrpc rank: 130 application_name: br30 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21215 commanderPluginType: xmlrpc rank: 215 application_name: eb15 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-16" ] ; then
    nohup boardreader  -c "id: 21131 commanderPluginType: xmlrpc rank: 131 application_name: br31 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21132 commanderPluginType: xmlrpc rank: 132 application_name: br32 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21216 commanderPluginType: xmlrpc rank: 216 application_name: eb16 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-17" ] ; then
    nohup boardreader  -c "id: 21133 commanderPluginType: xmlrpc rank: 133 application_name: br33 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21134 commanderPluginType: xmlrpc rank: 134 application_name: br34 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21217 commanderPluginType: xmlrpc rank: 217 application_name: eb17 partition_number: 11" >> $pmt_log_fn 2>&1 &
elif [ $nodename == "mu2e-trk-18" ] ; then
    nohup boardreader  -c "id: 21135 commanderPluginType: xmlrpc rank: 135 application_name: br35 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup boardreader  -c "id: 21136 commanderPluginType: xmlrpc rank: 136 application_name: br36 partition_number: 11" >> $pmt_log_fn 2>&1 &
    nohup eventbuilder -c "id: 21218 commanderPluginType: xmlrpc rank: 218 application_name: eb18 partition_number: 11" >> $pmt_log_fn 2>&1 &
fi
sleep 1
