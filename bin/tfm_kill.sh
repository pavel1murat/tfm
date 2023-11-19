#!/bin/env bash
#------------------------------------------------------------------------------
# call signature: tfm_kill <partition_number>
#------------------------------------------------------------------------------
source $TFM_DIR/bin/tfm_utis.sh

scriptdir="$(dirname "$0")"
daqutils_script=$scriptdir/daqutils.sh

if ! [[ -e $daqutils_script ]]; then 
    echo $(date) "Unable to source $daqutils_script - script not found" >&2
    exit 30
else   
    . $daqutils_script
fi   

forcibly_kill=false

for token in "$@"; do
    if [[ "$token" == "--force" ]]; then
	if (( "$#" < 2 )); then
	    echo "$usage_blurb" >&2
	    exit 1
	fi
	forcibly_kill=true
    fi
done

# JCF, Mar-22-2019

# Since I discovered that getting Tfm to recover gracefully
# in the event of a window close (SIGHUP) required that I stop tee-ing
# the output and instead tail -f its logfile as a way to get output to
# screen, I need to make sure that we don't leave any zombie tail
# -f's...otherwise double (triple, etc.) lines of output may get
# printed to screen!

# Note that the assumed basename of $TFM_LOGFILE is
# Tfm_partition<partition number>.log as defined in
# source_me; if this changes, the logic here will need to change as
# well

function kill_tail_f {
    for pid in $( ps aux | grep -E "tail -f.*tfm_partition${1}" | grep -v grep | awk '{print $2}' ); do
	      kill $pid
    done
}

for partition in "$@"; do
    if [[ "$partition" == "--force" ]]; then continue ; fi

    if ! [[ "$partition" =~ ^[0-9]+$ ]]; then  
	      echo "Error: argument \"$partition\" does not appear to be a partition number or an accepted option" >&2
	      exit 1
    fi

    cmd="ps aux | grep -E \"python.*farm_manager.py.*--partition-number\s+$partition\" | grep -v grep | awk '{print \$2}'"
    tfm_pid=$( eval $cmd )
    
    if [[ -n $tfm_pid ]]; then
	      
	      if ! $forcibly_kill ; then

            cat <<EOF
Checking to make sure that Tfm on partition $partition is in the "stopped" state.
If the script appears to hang here, there's an issue communicating with Tfm; hit Ctrl-c, 
and then re-run this script with the "--force" option added at the end.
EOF

	          export ARTDAQ_PARTITION_NUMBER=$partition
	          state_true="0"
	          check_for_state "stopped" state_true >&2 > /dev/null

	          if [[ "$state_true" != "1" ]]; then
		            cat <<EOF
TFM instance on partition $partition is not confirmed to be in the "stopped" state:
EOF
		            status.sh | grep "Result\|String"

		            cat<<EOF 
Are you *sure* you want to go ahead and kill it? Doing so may result
in improper cleanup of artdaq processes, etc. Respond with "y" or "Y"
to kill; any other string entered will not kill the instance:
EOF
		            read response
      
		            if ! [[ "$response" =~ ^[yY]$ ]]; then
		                echo "Will skip the killing of Tfm instance on partition $partition"
		                continue
		            fi
	          fi

	          echo "Killing TF manager listening on partition $partition"
	          kill $tfm_pid 
	          kill_tail_f $partition
	      else
	          kill $tfm_pid 
	          kill_tail_f $partition	     
            
	          tfm_pid=$( eval $cmd )

	          if [[ -n $tfm_pid ]]; then
		            echo "Regular kill didn't work on TF manager listening on partition $partition; use 'kill -9'"
		            kill -9 $tfm_pid
		            kill_tail_f $partition
	          fi
	      fi
    else
	      echo "No TF manager listening on partition $partition was found" >&2
	      continue
    fi
done



