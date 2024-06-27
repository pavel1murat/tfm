
# Get the products directory containing the desired package from the
# .settings file, and use it to perform a ups setup of the package

packagename=$1

# Spack packages use - where UPS uses _
packagename=`echo ${packagename} | tr _ -`

settings=$TFM_CONFIG_DIR/$TFM_CONFIG_NAME/settings

if [[ -z $packagename ]]; then
    echo "An argument with the desired packagename is required" >&2
    return 70
fi

test -z "${SPACK_VIEW-}" && { echo "Error: TFM not setup"; return 40; }

spackdir=$( sed -r -n 's/^\s*spack[_ ]root[_ ]for[_ ]bash[_ ]scripts\s*:\s*(\S+).*/\1/p' $settings )

if [[ -n $spackdir ]]; then

    cmd_save=$cmd
    . $spackdir/share/spack/setup-env.sh
    cmd=$cmd_save

    if [[ "$?" != "0" ]]; then
	echo -e "\n\nCommand will not work: attempted setup of $spackdir failed" >&2
	return 50
    fi
    
    num_packages=$(spack find --no-groups $packagename | wc -l )

    if (( num_packages == 0 )); then
	echo -e "\n\nCommand will not work: unable to find any $packagename packages in products directory $spackdir" >&2
	echo
	return 60
    fi

    # Unload everything from the environment
    spack unload >/dev/null 2>&1

    # Load desired package
    spack load --first $packagename

    return $?
else
    echo "Unable to find valid products/ directory from tfm settings file \"$settings\"" >&2
    return 40
fi
