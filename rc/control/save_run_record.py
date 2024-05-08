
import os
import stat
import re
import subprocess
from subprocess import Popen
import traceback
import shutil
import string
from   inspect import currentframe, getframeinfo

from rc.control.utilities import make_paragraph
from rc.control.utilities import get_commit_info
from rc.control.utilities import get_commit_info_filename
from rc.control.utilities import get_build_info
#------------------------------------------------------------------------------
# Save the FHiCL documents which were used to initialize the artdaq processes
#------------------------------------------------------------------------------
def save_run_record_base(self):
#------------------------------------------------------------------------------
# Step 1: save them into a temporary directory - no need - can write directly to the permanent position
#------------------------------------------------------------------------------
    self.print_log("d", "%s:save_record_base 001" % (__file__),2)

    outdir = self.record_directory+'/%06d'%self.run_number # self.tmp_run_record

    try:
        os.makedirs(outdir)
    except Exception:
        raise Exception("%s::save_run_record_base:%d Exception raised during creation of %s"
                        % (__file__,getframeinfo(currentframe()).lineno,outdir))
        return
#------------------------------------------------------------------------------
# P.M. assume the directory has been created
#---v--------------------------------------------------------------------------
    self.print_log("d", "%s:save_record_base 002" % (__file__),2)

    for procinfo in self.procinfos:
        outf = open(outdir + "/" + procinfo.label + ".fcl", "w")
        outf.write(procinfo.fhicl_used)
        outf.close()
#------------------------------------------------------------------------------
# For good measure, let's also save the DAQ setup script
# JCF, Oct-25-2018: but save it with environment variables expanded (see Issue #21225)
# P.M. no boot.txt file anymore - everything is in 'settings'
# - why on earth using Popen when there is copy2 ?
#---v--------------------------------------------------------------------------
    new_fn = outdir + "/setup.txt";
    try:
        shutil.copy2(self.daq_setup_script,new_fn);
    except Exception:
        raise Exception("%s::save_run_record_base:%d problem creating %s"
                        % (__file__,getframeinfo(currentframe()).lineno,new_fn))
        return

#    Popen(
#        "cp -p " + self.daq_setup_script + " " + outdir + "/setup.txt",
#        shell=True,
#        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
#    ).wait()

#    if not os.path.exists(outdir + "/setup.txt"):
#        self.alert_and_recover("Problem creating file %s/setup.txt" % (outdir))

    self.print_log("d", "%s:save_record_base 003" % (__file__),2)

    settings_fn = self.settings_filename();
    # assert os.path.exists(settings_fn)

    new_settings_fn = outdir + "/settings";
    try:
        shutil.copy2(settings_fn,new_settings_fn);
    except Exception:
        raise Exception("%s::save_run_record_base:%d problem creating %s"
                        % (__file__,getframeinfo(currentframe()).lineno,new_settingsfn))
        return

#    Popen(
#        "cp -p " + settings_fn + " " + outdir + "/settings.txt",
#        shell=True,
#        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
#    ).wait()
#
#    if not os.path.exists(outdir + "/settings.txt"):
#        self.alert_and_recover("Problem creating file " + outdir + "/settings.txt")

#------------------------------------------------------------------------------
# save information about ARTDAQ processes, ordered by rank 
# P.M. better to ahve it first ordered by the host
#------------------------------------------------------------------------------
    self.print_log("d", "%s:save_record_base 004" % (__file__),2)
    ranksfilename = "%s/ranks.txt" % (outdir)

    with open(ranksfilename, "w") as ranksfile:
        ranksfile.write("%-30s%-10s%-20s%-15s%-10s\n"  % ("host", "port", "label", "subsystem", "rank"))
        ranksfile.write("\n")

        procinfos_sorted_by_rank = sorted(self.procinfos, key=lambda procinfo: procinfo.rank)

        for procinfo in procinfos_sorted_by_rank:
            host = procinfo.host
            if host == "localhost":
                host = os.environ["HOSTNAME"]
            ranksfile.write("%-29s %-9s %-19s %-14s %-9d\n"
                            % (host,procinfo.port,procinfo.label,procinfo.subsystem,procinfo.rank))
#------------------------------------------------------------------------------
# P.M. why this one is needed at all ? - why not the full environment ?
#------------------------------------------------------------------------------
    self.print_log("d", "%s:save_record_base 005" % (__file__),2)

    environfilename = "%s/environment.txt" % (outdir)
    with open(environfilename, "w") as environfile:
        for var in sorted([varname for varname in os.environ if re.search(r"^TFM_", varname)]):
            environfile.write("export %s=%s\n"% (var,os.environ[var]))
#------------------------------------------------------------------------------
# JCF, 11/20/14
#                  Now save "metadata" about the run in the "metadata_r<run #>.txt" file. This includes the
#                  selected configuration, selected components, and commit hashes of lbne-artdaq and lbnerc
# JCF, Dec-4-2016: 
#                  changed to metadata.txt, as this is executed before the start transition
#------------------------------------------------------------------------------
    self.print_log("d", "%s:save_record_base 006" % (__file__),2)

    outf = open(outdir + "/metadata.txt", "w")

    outf.write("Config name  : %s\n"    % (" ".join(self.subconfigs_for_run)))
    outf.write("TFM directory: %s:%s\n" % (os.environ["HOSTNAME"], os.getcwd()))
    outf.write("TFM logfile  : %s:%s\n" % (os.environ["HOSTNAME"],os.environ["TFM_LOGFILE"]))

    # Now save the commit hashes / versions of the packages listed in the settings file

    # JCF, Jul-9-2019
    # Add additional info along with that described above, as per Redmine Issue #22777

    outf.write(
        "\n# Two possible sets of fields provided below for code info, depending on if a git repo was available: "
    )
    outf.write(
        ("\n# <git commit hash> <LoCs added on top of commit> <LoCs removed on top of commit> "
         "<git commit comment> <git commit time> <git branch> <BuildInfo build time (if available)> "
         "<BuildInfo version (if available)>")
    )
    outf.write(
        "\n# <package version> <BuildInfo build time (if available)> <BuildInfo version (if available)>\n\n"
    )

    # assert "TFM_DIR" in os.environ and os.path.exists(os.environ["TFM_DIR"])

    buildinfo_packages = [pkg for pkg in self.package_hashes_to_save]  
#     buildinfo_packages.append("tfm")

    self.print_log("d", "%s:save_record_base 0061" % (__file__),2)
#------------------------------------------------------------------------------
# this is the step which takes 12 seconds, mostly useless
# for the demo example it returns 
# {
#   'artdaq-demo': '"01-Jan-2024 22:14:44 UTC" "v3_12_07-4-g0f6d3df"', 
#   'artdaq'     : '"01-Jan-2024 22:14:33 UTC" "v3_12_07-1-g67026501"', 
#   'tfm'        : '"time from BuildInfo undetermined" "version from BuildInfo undetermined"'
# }
# P.M. it takes 12 sec even for an empty list of buildinfo_packages, which is nuts
#------------------------------------------------------------------------------
    package_buildinfo_dict = {} # get_build_info(buildinfo_packages, self.daq_setup_script)
    
    self.print_log("d", "%s:save_record_base 00611" % (__file__),2)

#    print("package_buildinfo_dict:\n",package_buildinfo_dict)

#     try:
#         commit_info_fullpathname = "%s/%s" % (
#             os.path.dirname(self.daq_setup_script),get_commit_info_filename("tfm_start")
#         )
#         if os.path.exists(commit_info_fullpathname):
#             with open(commit_info_fullpathname) as commitfile:
#                 outf.write("%s" % (commitfile.read()))
#         else:
#             outf.write("%s" % (get_commit_info("tfm_start",os.environ["TFM_DIR"])))
#     except Exception:
#         # Not an exception in a bad sense as the throw just means we're using DAQInterface as a ups product
#         self.fill_package_versions(["tfm"])
#         outf.write("tfm commit/version: %s" % (self.package_versions["tfm"]))
# 
#    outf.write(" %s\n\n" % (package_buildinfo_dict["tfm"]))

    package_commit_dict             = {}
    packages_whose_versions_we_need = []

    for pkgname in self.package_hashes_to_save:

        self.print_log("d", "%s:save_record_base 0062 pkgname:%s" % (__file__,pkgname),2)

        pkg_full_path = "%s/srcs/%s" % (self.daq_dir, pkgname.replace("-", "_"))
        commit_info_fullpathname = "%s/%s" % (
            os.path.dirname(self.daq_setup_script),
            get_commit_info_filename(pkgname),
        )

        if os.path.exists(commit_info_fullpathname):
            with open(commit_info_fullpathname) as commitfile:
                package_commit_dict[pkgname] = commitfile.read()

        elif os.path.exists(pkg_full_path):
            try:
                package_commit_dict[pkgname] = get_commit_info(pkgname, pkg_full_path)
            except Exception:
                self.print_log("e", traceback.format_exc())
                self.alert_and_recover(
                    "An exception was thrown in get_commit_info; see traceback above for more info"
                )
                return
        else:
            # We'll throw this on the list of packages whose actual versions we need to figure out in real-time
            packages_whose_versions_we_need.append(pkgname)

    self.fill_package_versions(
        [pkg.replace("-", "_") for pkg in packages_whose_versions_we_need]
    )

    self.print_log("d", "%s:save_record_base 0063" % (__file__),2)

    for pkgname in packages_whose_versions_we_need:
        package_commit_dict[pkgname] = "%s commit/version: %s" % (
            pkgname,
            self.package_versions[pkgname.replace("-", "_")],
        )

    for pkg in sorted(package_commit_dict.keys()):
        outf.write("%s"      % (package_commit_dict[pkg]))
        outf.write(" %s\n\n" % (package_buildinfo_dict[pkg]))

#    outf.write(
#        "\nprocess management method: %s\n"
#        % (os.environ["TFM_PROCESS_MANAGEMENT_METHOD"])
#    )

    self.print_log("d", "%s:save_record_base 0064" % (__file__),2)

    if self.manage_processes:

        logtuples = [
            ("process manager", self.process_manager_log_filenames),
            ("boardreader"    , self.boardreader_log_filenames),
            ("eventbuilder"   , self.eventbuilder_log_filenames),
            ("datalogger"     , self.datalogger_log_filenames),
            ("dispatcher"     , self.dispatcher_log_filenames),
            ("routingmanager" , self.routingmanager_log_filenames),
        ]

        for logtuple in logtuples:

            outf.write("\n")
            outf.write("\n%s logfiles: " % logtuple[0])

            for filename in logtuple[1]:
                outf.write("\n" + filename)

    outf.write("\n")
    outf.close()

    self.print_log("d", "%s:save_record_base 007" % (__file__),2)

#     for (recorddir, dummy, recordfiles) in os.walk(self.tmp_run_record):
#         for recordfile in recordfiles:
#             os.chmod("%s/%s" % (recorddir, recordfile), 0o444)
#
#     try:
#         shutil.copytree(self.tmp_run_record, self.semipermanent_run_record)
#     except:
#         self.print_log("w", traceback.format_exc())
#         self.print_log(
#             "w",
#             make_paragraph(
#                 ('Attempt to copy temporary run record "%s" into "%s" didn\'t work; '
#                  'keep in mind that %s will be clobbered next time you run on this partition')
#                 % (
#                     self.tmp_run_record,
#                     self.semipermanent_run_record,
#                     self.tmp_run_record,
#                 )
#             ),
#         )
#------------------------------------------------------------------------------
# make the directory read-only
#------------------------------------------------------------------------------
    os.chmod(outdir, 0o555)
    self.print_log("d","%s: Saved run record in %s"%(__file__,outdir),2)

    return

def save_metadata_value_base(self, key, value):

#     metadata_filename = "%s/%s/metadata.txt" % (
#         self.record_directory,
#         str(self.run_number),
#     )
    fn = self.metadata_filename();
    assert os.path.exists(fn)

    os.chmod(fn, 0o644)
    with open(fn, "a") as f:
        f.write("\n%s: %s\n" % (key, value))
    os.chmod(fn, 0o444)
