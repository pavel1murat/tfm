
# Get the products directory containing the desired package from the
# .settings file, and use it to perform a ups setup of the package

packagename=$1

settings=$TFM_CONFIG_DIR/$TFM_CONFIG_NAME/settings

if [[ -z $packagename ]]; then
    echo "An argument with the desired packagename is required" >&2
    return 70
fi

# 27-Jan-2017, KAB, if the requested package is already set up, let's assume that it's OK to use it
# (probably better tests that can be used...)
upcasePackageName=`echo ${packagename} | tr [a-z] [A-Z]`
prodDirEnvVar="${upcasePackageName}_DIR"
#echo $prodDirEnvVar
#echo ${!prodDirEnvVar}
if [[ -n "${!prodDirEnvVar}" ]]; then
    return
fi

test -z "${SPACK_VIEW-}" && { echo "Error: tfm not setup"; return 40; }

proddir=$( sed -r -n 's/^\s*productsdir[_ ]for[_ ]bash[_ ]scripts\s*:\s*(\S+).*/\1/p' $settings )
export PRODUCTS
eval "PRODUCTS=\"$proddir\"" # Expand environ variables in string
proddir=`$SPACK_VIEW/python/tfm/rc/control/utilities.py upsproddir_from_productsdir "$PRODUCTS"`

if [[ -n $proddir ]]; then

    . $proddir/setup 

    if [[ "$?" != "0" ]]; then
	echo -e "\n\nCommand will not work: attempted setup of $proddir failed" >&2
	return 50
    fi
    
    num_packages=$(ups list -aK+ $packagename | wc -l )

    if (( $num_packages == 0 )); then
	echo -e "\n\nCommand will not work: unable to find any $packagename packages in products directory $proddir" >&2
	echo
	return 60
    fi

    unsetup_all()
    {
	for pp in `printenv | sed -ne '/^SETUP_/{s/SETUP_//;s/=.*//;p}'`;do
            test $pp = UPS && continue;
            prod=`echo $pp | tr 'A-Z' 'a-z'`;
            eval "tmp=\${SETUP_$pp-}";
            test -z "$tmp" && echo already unsetup && continue;
            unsetup -j $prod;
	done
    }

    # Call Ron's unsetup function. Remove the ups packages of the
    # environment which sourced package_setup to avoid unnecessary version
    # conflicts. Note that this also requires that package_setup not have
    # already been sourced in the environment; if it HAS, then unsetup_all
    # will remove a package which the externval environment needs

    if [[ -z $TFM_ALREADY_CALLED_PACKAGE_SETUP ]]; then
	      export TFM_ALREADY_CALLED_PACKAGE_SETUP=true
	      unsetup_all
    else
	      cat >&2 <<EOF
        DEVELOPER ERROR: package_setup.sh shouldn't be sourced twice
        in the same environment as its first action is to unsetup any
        previously-set-up ups package. Please contact the 
        artdaq-developers@fnal.gov mailing list. 
EOF
	      return 1
    fi

    nv=$( ups list -aK+ $packagename | wc -l )
    successful_setup=false

    while (( $nv > 0 )); do
	      setup_cmd=$( ups list -aK+ $packagename | sort -n | head -$nv | tail -1 | awk '{print "setup $packagename",$2," -q ", $4}' )
	      eval $setup_cmd

	      if [[ "$?" == "0" ]]; then
	          break
	      else
	          nv=$(( nv - 1 ))
	      fi
    done
    
    if (( nv == 0 )); then
	      echo "Unable to set up any of the versions of $packagename found in $proddir" >&2
	      return 50
    fi
    
    return 0
else
    echo "Unable to find valid products/ directory from TFM settings file \"$settings\"" >&2
    return 40
fi
