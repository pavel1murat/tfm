#!/bin/bash
#------------------------------------------------------------------------------
# start Trigger Farm Manager in a given partition - $TFM_PARTITION_NUMBER
# ARTDAQ_BASE_PORT and ARTDAQ_PORTS_PER_PARTITION are used by artdaq/artdaq/DAQdata/PortManager.cc
# artdaq/artdaq/DAQdata/Globals.hh also uses ARTDAQ_PARTITION_NUMBER
#------------------------------------------------------------------------------
script=$(basename $0)

source $TFM_DIR/bin/tfm_utils.sh
#------------------------------------------------------------------------------
# -The "nohup" is there so DAQInterface can wind down cleanly if users close its terminal
# -The "stdbuf -oL" is there so that DAQInterface output makes it into the logfile in realtime
# -The "<&-" is there to avoid hangs if users type in the terminal DAQInterface is running in (see Issue #21804)
#------------------------------------------------------------------------------
export TFM_PORT=`tfm_port $TFM_PARTITION_NUMBER`

logfile=$(echo $(eval echo $TFM_LOGFILE))
touch $logfile 
echo [$script:$LINENO] : \$TFM_LOGFILE=$TFM_LOGFILE \$TFM_PORT=$TFM_PORT

if [[ -z $( ps aux | grep "$TFM_TTY.*tail -n0 -f $logfile" | grep -v grep ) ]]; then
    tail -n0 -f $logfile &
fi

nohup stdbuf -oL $TFM_DIR/rc/control/farm_manager.py -p $TFM_PARTITION_NUMBER --rpc-port $TFM_PORT <&- >> $logfile 2>&1

pid=$( ps aux | grep "$TFM_TTY.*tail -n0 -f $logfile" | grep -v grep | awk '{print $2}' )

if [[ -n $pid ]]; then kill $pid ; fi

unset pid
unset logfile
