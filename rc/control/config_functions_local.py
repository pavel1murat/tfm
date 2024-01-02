#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
import os, sys, re

sys.path.append(os.environ["TFM_DIR"])

import traceback
import shutil
import subprocess

from rc.control.subsystem import Subsystem
from rc.control.procinfo  import Procinfo

# from rc.control.utilities import make_paragraph
import rc.control.utilities as rcu; # import make_paragraph

#------------------------------------------------------------------------------
def get_config_info_base(self):

    uuidgen = (
        subprocess.Popen("uuidgen", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        .stdout.readlines()[0]
        .strip()
        .decode("utf-8")
    )
    tmpdir = "/tmp/%s" % (uuidgen)
    os.mkdir(tmpdir)

    ffp = []

    if (os.path.exists("%s/common_code" % self.get_config_parentdir()) and 
        ("common_code" not in self.subconfigs_for_run)    ):
#------------------------------------------------------------------------------
# For backwards-compatibility with earlier versions of this function
#-------v----------------------------------------------------------------------
        self.subconfigs_for_run.append("common_code")  

    for subconfig in self.subconfigs_for_run:
        subconfig_dir = "%s/%s" % (self.get_config_parentdir(), subconfig)

        if os.path.exists(subconfig_dir):
            tmp_subconfig_dir = "%s/%s" % (tmpdir, subconfig)
            if os.path.exists(tmp_subconfig_dir): 
                shutil.rmtree(tmp_subconfig_dir)
            shutil.copytree(subconfig_dir, tmp_subconfig_dir)
            assert os.path.exists(tmp_subconfig_dir)

            for dirname, dummy, dummy in os.walk(tmp_subconfig_dir):
                ffp.append(dirname)
        else:
            raise Exception(
                rcu.make_paragraph(
                    'Error: unable to find expected directory of FHiCL configuration files "%s"'
                    % (subconfig_dir)
                )
            )

    return tmpdir, ffp


# put_config_info_base and put_config_info_on_stop_base should be no-ops


def put_config_info_base(self):
    pass


def put_config_info_on_stop_base(self):
    pass

#------------------------------------------------------------------------------
# default input function - reads boot.txt file
# no need to do this any longer - all input parameters come from the 'settings' file
#------------------------------------------------------------------------------
# def get_boot_info_base(self, boot_filename):
#     return

#------------------------------------------------------------------------------
def listconfigs_base(self):
    subdirs = next(os.walk(self.get_config_parentdir()))[1]
    configs = [subdir for subdir in subdirs if subdir != "common_code"]

    listconfigs_file = "/tmp/listconfigs_" + os.environ["USER"] + ".txt"

    outf = open(listconfigs_file, "w")

    print("\nAvailable configurations: ")
    for config in sorted(configs):
        print(config)
        outf.write("%s\n" % config)

    print('\nSee file "%s" for saved record of the above configurations' % (listconfigs_file))
    print(
        rcu.make_paragraph(
            "Please note that for the time being, the optional max_configurations_to_list variable "
            "which may be set in %s is only applicable when working with the database\n"
            % os.environ["TFM_SETTINGS"]
        )
    )

    # print(flush=True)
    sys.stdout.flush()


def main():
#    print("Calling listdaqcomps_base: ")
    return

if __name__ == "__main__":
    main()
