
# Determine which package setup script to call
settings=$TFM_CONFIG_DIR/$TFM_CONFIG_NAME/settings

if [[ ! -e $settings ]]; then
    echo "Unable to find TFM settings file \"$settings\"" >&2
    return 30
fi
test -z "${SPACK_VIEW-}" && { echo "Error: tfm not setup"; return 40; }

spackdir=$( sed -r -n 's/^\s*spack[_ ]root[_ ]for[_ ]bash[_ ]scripts\s*:\s*(\S+).*/\1/p' $settings )
 proddir=$( sed -r -n 's/^\s*productsdir[_ ]for[_ ]bash[_ ]scripts\s*:\s*(\S+).*/\1/p'   $settings )

if [[ -d ${proddir%%:*} ]]; then
    source package_setup_ups.sh $@
elif [[ -d $spackdir ]]; then
    source package_setup_spack.sh $@
else
    echo "Unable to find valid products/ directory from TFM settings file \"$settings\"" >&2
    return 40
fi
