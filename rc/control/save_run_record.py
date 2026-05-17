
import os
import stat
import re
import subprocess
from   subprocess import Popen
import traceback
import shutil
import string
from   inspect import currentframe, getframeinfo

from   tfm.rc.control.utilities import make_paragraph
# from   tfm.rc.control.utilities import get_commit_info
# from   tfm.rc.control.utilities import get_commit_info_filename
# from   tfm.rc.control.utilities import get_build_info
import TRACE
TRACE_NAME = "save_run_record"
#------------------------------------------------------------------------------
# Save the FHiCL documents which were used to initialize the artdaq processes
#------------------------------------------------------------------------------
def save_run_record_base(self):
#------------------------------------------------------------------------------
# Step 1: save them into a temporary directory - no need - can write directly to the permanent position
#------------------------------------------------------------------------------
    TRACE.INFO("-- START",TRACE_NAME)

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
    TRACE.INFO(f"002, record directory created",TRACE_NAME)

    for procinfo in self.procinfos:
        outf = open(outdir + "/" + procinfo.label + ".fcl", "w")
        outf.write(procinfo.fhicl_used)
        outf.close()
#------------------------------------------------------------------------------
# For good measure, let's also save the DAQ setup script
# JCF, Oct-25-2018: but save it with environment variables expanded (see Issue #21225)
# PM - why on earth using Popen when there is copy2 ?
#---v--------------------------------------------------------------------------
    new_fn = outdir + '/' + os.path.basename(self.daq_setup_script);
    try:
        shutil.copy2(self.daq_setup_script,new_fn);
    except Exception:
        raise Exception("%s::save_run_record_base:%d problem creating %s"
                        % (__file__,getframeinfo(currentframe()).lineno,new_fn))
        return

#------------------------------------------------------------------------------
# save information about ARTDAQ processes, ordered by rank 
# P.M. better to have it first ordered by the host
#------------------------------------------------------------------------------
    TRACE.INFO(f"004",TRACE_NAME)
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
    TRACE.INFO(f"005",TRACE_NAME)

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
    TRACE.INFO(f"006",TRACE_NAME)

    outf = open(outdir + "/metadata.txt", "w")

    outf.write("Config name  : %s\n"    % (" ".join(self.subconfigs_for_run)))
    outf.write("TFM directory: %s:%s\n" % (os.environ["HOSTNAME"], os.getcwd()))
    outf.write("TFM logfile  : %s:%s\n" % (os.environ["HOSTNAME"],os.environ["TFM_LOGFILE"]))

    # Now save the commit hashes / versions of the packages

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

    # buildinfo_packages = [pkg for pkg in self.package_hashes_to_save]  

#    self.print_log("d", "%s:save_record_base 0061" % (__file__),2)
#------------------------------------------------------------------------------
# this is the step which takes 12 seconds, mostly useless
# for the demo example it returns 
# {
#   'artdaq-demo': '"01-Jan-2024 22:14:44 UTC" "v3_12_07-4-g0f6d3df"', 
#   'artdaq'     : '"01-Jan-2024 22:14:33 UTC" "v3_12_07-1-g67026501"', 
#   'tfm'        : '"time from BuildInfo undetermined" "version from BuildInfo undetermined"'
# }
# P.M. it takes 12 sec even for an empty list of buildinfo_packages, which is nuts
# 2026-02-01: cleanup in progress
#------------------------------------------------------------------------------
#    package_buildinfo_dict = {} # get_build_info(buildinfo_packages, self.daq_setup_script)
    
    TRACE.INFO("00611",TRACE_NAME)

# 2026-05-15 PM    if self.manage_processes:
# 2026-05-15 PM
# 2026-05-15 PM        logtuples = [
# 2026-05-15 PM            ("process manager", self.process_manager_log_filenames),
# 2026-05-15 PM            ("boardreader"    , self.boardreader_log_filenames),
# 2026-05-15 PM            ("eventbuilder"   , self.eventbuilder_log_filenames),
# 2026-05-15 PM            ("datalogger"     , self.datalogger_log_filenames),
# 2026-05-15 PM            ("dispatcher"     , self.dispatcher_log_filenames),
# 2026-05-15 PM            ("routingmanager" , self.routingmanager_log_filenames),
# 2026-05-15 PM        ]
# 2026-05-15 PM
# 2026-05-15 PM        for logtuple in logtuples:
# 2026-05-15 PM
# 2026-05-15 PM            outf.write("\n")
# 2026-05-15 PM            outf.write("\n%s logfiles: " % logtuple[0])
# 2026-05-15 PM
# 2026-05-15 PM            for filename in logtuple[1]:
# 2026-05-15 PM                outf.write("\n" + filename)

    outf.write("\n")
    outf.close()
#------------------------------------------------------------------------------
# make the directory read-only
#------------------------------------------------------------------------------
    os.chmod(outdir, 0o555)
    TRACE.INFO(f"-- END: Saved run record in {outdir}",TRACE_NAME)

    return

#------------------------------------------------------------------------------
def save_metadata_value_base(self, key, value):

    fn = self.metadata_filename();
    assert os.path.exists(fn)

    os.chmod(fn, 0o644)
    with open(fn, "a") as f:
        f.write("\n%s: %s\n" % (key, value))
    os.chmod(fn, 0o444)
