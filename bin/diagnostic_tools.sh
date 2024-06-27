#!/usr/bin/bash
script=`basename $0`

config_dir=$MU2E_DAQ_DIR/config/$TFM_CONFIG_NAME

echo [$script:$LINENO] : config_dir=$config_dir 

x=`cat $config_dir/settings | grep '^record_directory' | awk -F : '{print $2}'`
recorddir=$(eval echo $x)  # Expand environ variables in string     

# echo recorddir=$recorddir
function file_locations() {
    file_locations=""

    for proctype in EventBuilder Aggregator DataLogger ; do
        for file in $( ls $recorddir/$runnum/${proctype}*.fcl 2>/dev/null ) ; do
	          rootfile_host=$( echo $file | sed -r 's/.*'${proctype}'_(.*)_.*/\1/' )
	          rootfile_dir=$( sed -r -n '/^\s*#/d;/fileName.*\.root/s/.*fileName[^/]*(\/.*\/).*/\1/p' $file )
	          if [[ -n $rootfile_dir && ! $file_locations =~ "${rootfile_host}:${rootfile_dir}" ]]; then
	              file_locations="${rootfile_host}:${rootfile_dir} ${file_locations}"
	          fi
        done
    done
    
    echo $file_locations
}

echo [$script:$LINENO] : done



