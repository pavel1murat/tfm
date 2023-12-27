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
def get_config_parentdir():
    print("config_funclions_local::get_config_parent_dir: WHY IS IT CALLED ????")
    parentdir = os.environ["TFM_FHICL_DIRECTORY"]
    assert os.path.exists(parentdir), "Expected configuration directory "+parentdir+" doesn't exist"
    return parentdir

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

    if (os.path.exists("%s/common_code" % get_config_parentdir()) and 
        ("common_code" not in self.subconfigs_for_run)    ):

        self.subconfigs_for_run.append("common_code")  # For backwards-compatibility with earlier versions of this function

    for subconfig in self.subconfigs_for_run:
        subconfig_dir = "%s/%s" % (get_config_parentdir(), subconfig)

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
#------------------------------------------------------------------------------
def get_boot_info_base(self, boot_filename):

    inf = open(boot_filename)

    if not inf: 
        raise Exception("ERROR: TFM unable to locate configuration file "+boot_filename)

#     memberDict = {
#         "name"              : None,
#         "label"             : None,
#         "host"              : None,
#         "port"              : "not set",
#         "fhicl"             : None,
#         "subsystem"         : "not set",
#         "allowed_processors": "not set",
#         "target"            : "not set",
#         "prepend"           : "not set",
#     }
#     subsystemDict = {
#         "id"                : None,
#         "source"            : "not set",
#         "destination"       : "not set",
#         "fragmentMode"      : "not set",
#     }

    num_expected_processes = 0
    num_actual_processes   = 0
#------------------------------------------------------------------------------
# assume format : "key : parameters"
####
    lines = inf.readlines()
    for i_line, line in enumerate(lines):
        l1 = line.split('#')[0].strip();
#------------------------------------------------------------------------------
# skip comment lines
########
        if (len(l1) == 0):                                  continue

        words  = l1.split(':')
        nwords = len(words)
        assert (nwords == 2), "ERROR reading the boot.txt line:"+line
#------------------------------------------------------------------------------
# skip comments but not empty lines: John uses empty lines for something
# immediately expand evn vars in the value part...
########
        key = words[0].strip()

        data = os.path.expandvars(words[1]).strip()
        par  = data.split();
        npar = len(par)
#------------------------------------------------------------------------------
# P.M. it looks that the outcome is always false
########
        if self.find_process_manager_variable(line):        continue
#------------------------------------------------------------------------------
# some global parameters
########
        elif (key == "daq_setup_script"):
            self.daq_setup_script = data;
            self.daq_dir          = os.path.dirname(self.daq_setup_script) + "/"

        elif (key == "request_address"):
            self.request_address = data

        elif (key == "debug_level"):
            self.debug_level = int(data)

        elif (key == "manage_processes"):
            if (data.upper() == "TRUE"): self.manage_processes = True
            else                       : self.manage_processes = False

        elif (key == "disable_recovery"):
            if (data.upper() == "TRUE"): self.disable_recovery = True
            else                       : self.disable_recovery = False
        elif (key == "Subsystem"):
            
            s = Subsystem();

            s.id           = par[0];                        # should always be defined

            s.source       = None
            if (par[1] != "none"): s.source      = par[1];

            s.destination  = None;
            if (par[2] != "none"): s.destination = par[2];

            s.fragmentMode = par[3];                        # should always be defined

            # breakpoint()
            self.subsystems[s.id] = s

        elif ((key == "EventBuilder"  ) or 
              (key == "DataLogger"    ) or 
              (key == "Dispatcher"    ) or 
              (key == "RoutingManager")   ):

            assert (npar == 7), "ERROR reading the line:%s, npar=%i" % (line,npar)

            num_actual_processes += 1
            rank                  = num_actual_processes - 1

            label                 = par[0]
            host                  = par[1]
            port                  = par[2]
            if (par[2] == "-1"):
                base_port           = int(os.environ["ARTDAQ_BASE_PORT"])
                ports_per_partition = int(os.environ["ARTDAQ_PORTS_PER_PARTITION"])
                port                = str(base_port+self.partition()*ports_per_partition+100+rank)
            
            subsystem             = par[3]

            ap                    = None            # None = "allow all processors"
            if (par[4] != "-1"): ap = par[4]

            prepend               = "";
            if (par[5] != "none"): prepend = par[5]

            target                = None
            if (par[6] != "none"): target = par[6]
#------------------------------------------------------------------------------
# remember, boardreaders go first
############
            p = Procinfo(name               = key      ,
                         label              = label    ,
                         rank               = rank     ,
                         host               = host     ,
                         port               = port     , 
                         subsystem          = subsystem,
                         allowed_processors = ap       ,
                         target             = target   ,
                         prepend            = prepend
            )
            p.print();
            self.procinfos.append(p)
#------------------------------------------------------------------------------
# P.Murat: 'BoardReader label host port subsystem allowed_processors prepend'
#          if the value of 'allowed_processors' is undefined (-1), set it to None
#          prepend is smth prepenced to the boardreader launch command, looks 
#          like a debugging tool
#          set it to '' 
#          assume no prepend for others 
#          assume boardreaders are defined first
########
        elif (key == "BoardReader"):
            assert (npar == 7), "ERROR reading the line:%s, npar=%i" % (line,npar)
            
            num_actual_processes   += 1
            rank = num_actual_processes - 1
            
            label              = par[0]
            host               = par[1];
            port               = par[2];
            if (port == "-1"): port = str(self.boardreader_port_number(rank));

            subsystem          = par[3];

            ap                 = None
            if (par[4] != "-1"  ): ap = par[4];

            prepend            = "";
            if (par[5] != "none"): prepend = par[5];
            
            target             = par[6];

            p = Procinfo(name               = key      ,
                         rank               = rank     ,
                         host               = host     ,
                         port               = port     ,
                         label              = label    ,
                         subsystem          = subsystem,
                         allowed_processors = ap       ,
                         target             = target   ,
                         prepend            = prepend
                )
            p.print()
            self.procinfos.append(p);
        else:
#------------------------------------------------------------------------------
# JCF, Mar-29-2019

# In light of the experience at ProtoDUNE, it appears necessary to allow experiments 
# an ability to overwrite FHiCL parameters at will in the boot file. A use case that
# came up was that a fragment generator had a parameter whose value needed to be a function 
# of the partition, but the fragment generator had no direct knowledge of what partition it was on
#------------------------------------------------------------------------------
            self.bootfile_fhicl_overwrites[key] = data
#------------------------------------------------------------------------------
# end of the loop
####

    self.set_process_manager_default_variables()
    return

#------------------------------------------------------------------------------
def listconfigs_base(self):
    subdirs = next(os.walk(get_config_parentdir()))[1]
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
    print("Calling listdaqcomps_base: ")
    listdaqcomps_base("ignored_argument")


if __name__ == "__main__":
    main()
