#!/usr/bin/bash

#------------------------------------------------------------------------------
# always require that to be sourced first
#------------------------------------------------------------------------------
if [[ -z $TFM_STANDARD_SOURCEFILE_SOURCED ]]; then
    echo \$TFM_DIR/source_me not sourced. BAIL OUT
    exit 1
fi

if [[ ! -e $TFM_SETTINGS ]]; then
    echo "Unable to find settings file \"$TFM_SETTINGS\"; exiting..." >&2
    exit 1
fi

recorddir=$( sed -r -n 's/^\s*record[_ ]directory\s*:\s*(\S+).*/\1/p' $TFM_SETTINGS )
recorddir=$( echo $( eval echo $recorddir ) )  # Expand environ variables in string     

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










