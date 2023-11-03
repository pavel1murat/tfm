# ======================================================================
#  tfm main build file
#
#  cd .../path/to/build/directory
#  source .../path/to/tfm/ups/setup_for_development
#  cmake [-DCMAKE_INSTALL_PREFIX=/install/path]
#        -Dqualifier:STRING=$CETPKG_QUAL
#        -DCMAKE_BUILD_TYPE=$CETPKG_TYPE
#        $CETPKG_SOURCE
#  make
#  make test
#  make install
#  make package
# ======================================================================
# to be validated

# use cmake 2.8 or later
cmake_minimum_required (VERSION 3.16)

# find_package(cetmodules)

project(tfm VERSION 0.0.1)

set(tfm_NOARCH TRUE)

# include(CetCMakeEnv)
# cet_cmake_env()

add_compile_options(DIAGS VIGILANT
  WERROR
  NO_UNDEFINED
  EXTRA_FLAGS -pedantic
)

#cet_report_compiler_flags()

install(DIRECTORY bin       DESTINATION . FILE_PERMISSIONS USE_SOURCE_PERMISSIONS)
install(DIRECTORY examples  DESTINATION . FILE_PERMISSIONS USE_SOURCE_PERMISSIONS)
install(DIRECTORY rc        DESTINATION . FILE_PERMISSIONS USE_SOURCE_PERMISSIONS)
install(DIRECTORY config    DESTINATION . FILE_PERMISSIONS USE_SOURCE_PERMISSIONS)
install(DIRECTORY utils     DESTINATION . FILE_PERMISSIONS USE_SOURCE_PERMISSIONS)
install(FILES     source_me DESTINATION .)

# cet_cmake_config()
