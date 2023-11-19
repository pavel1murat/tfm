
import os
import stat
import re
import subprocess
from subprocess import Popen
import traceback
import shutil
import string

from rc.control.utilities import make_paragraph
from rc.control.utilities import get_commit_info
from rc.control.utilities import get_commit_info_filename
from rc.control.utilities import get_build_info
from rc.control.utilities import expand_environment_variable_in_string

def save_run_record_base(self):

    # Save the FHiCL documents which were used to initialize the
    # artdaq processes

    outdir = self.tmp_run_record

    try:
        os.makedirs(outdir)
    except Exception:
        raise Exception(
            make_paragraph("Exception raised during creation of %s" % (outdir))
        )
        return

    if not os.path.exists(outdir):
        raise Exception("Problem creating output directory %s" % (outdir))
        return

    for procinfo in self.procinfos:

        outf = open(outdir + "/" + procinfo.label + ".fcl", "w")

        outf.write(procinfo.fhicl_used)
        outf.close()
#------------------------------------------------------------------------------
# For good measure, let's also save the TFM configuration file
# JCF, Oct-25-2018: but save it with environment variables expanded (see Issue #21225)
####

    boot_fn           = self.boot_filename()
    config_saved_name = os.path.basename(boot_fn);

    with open("%s/%s" % (outdir, config_saved_name), "w") as outf:
        with open(boot_fn) as inf:
            for line in inf.readlines():
                outf.write(expand_environment_variable_in_string(line))

    out_fn = "%s/%s" % (outdir, config_saved_name)
    if not os.path.exists(out_fn):
        self.alert_and_recover("Problem creating file "+out_fn)

    # As well as the DAQ setup script

    Popen(
        "cp -p " + self.daq_setup_script + " " + outdir + "/setup.txt",
        shell=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).wait()

    if not os.path.exists(outdir + "/setup.txt"):
        self.alert_and_recover("Problem creating file %s/setup.txt" % (outdir))

    settings_fn = self.settings_filename();
    assert os.path.exists(settings_fn)

    Popen(
        "cp -p " + settings_fn + " " + outdir + "/settings.txt",
        shell=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).wait()

    if not os.path.exists(outdir + "/settings.txt"):
        self.alert_and_recover("Problem creating file " + outdir + "/settings.txt")

    ranksfilename = "%s/ranks.txt" % (outdir)

    with open(ranksfilename, "w") as ranksfile:
        ranksfile.write(
            "%-30s%-10s%-20s%-15s%-10s\n"
            % ("host", "port", "label", "subsystem", "rank")
        )
        ranksfile.write("\n")

        procinfos_sorted_by_rank = sorted(
            self.procinfos, key=lambda procinfo: procinfo.rank
        )
        for procinfo in procinfos_sorted_by_rank:
            host = procinfo.host
            if host == "localhost":
                host = os.environ["HOSTNAME"]
            ranksfile.write(
                "%-29s %-9s %-19s %-14s %-9d\n"
                % (
                    host,
                    procinfo.port,
                    procinfo.label,
                    procinfo.subsystem,
                    procinfo.rank,
                )
            )
    environfilename = "%s/environment.txt" % (outdir)

    with open(environfilename, "w") as environfile:
        for var in sorted([varname for varname in os.environ if re.search(r"^TFM_", varname)]):
            environfile.write("export %s=%s\n"% (var,expand_environment_variable_in_string(os.environ[var])))

    # JCF, 11/20/14

    # Now save "metadata" about the run in the
    # "metadata_r<run #>.txt" file. This includes the
    # selected configuration, selected components, and commit
    # hashes of lbne-artdaq and lbnerc

    # JCF, Dec-4-2016: changed to metadata.txt, as this is executed
    # before the start transition

    outf = open(outdir + "/metadata.txt", "w")

    outf.write("Config name: %s\n" % (" ".join(self.subconfigs_for_run)))

#    for i_comp, component in enumerate(sorted(self.daq_comp_list)):
#        outf.write("Component #%d: %s\n" % (i_comp, component))

    outf.write(
        "TFM directory: %s:%s\n" % (os.environ["HOSTNAME"], os.getcwd())
    )
    outf.write(
        "DAQInterface logfile: %s:%s\n"
        % (
            os.environ["HOSTNAME"],
            expand_environment_variable_in_string(os.environ["TFM_LOGFILE"]),
        )
    )

    # Now save the commit hashes / versions of the packages listed in
    # self.settings_filename() = $TFM_SETTINGS, along with the commit hash for
    # DAQInterface(if using DAQInterface from the repo) or version (if
    # using DAQInterface as a ups product)

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

    assert "TFM_DIR" in os.environ and os.path.exists(os.environ["TFM_DIR"])

    buildinfo_packages = [
        pkg for pkg in self.package_hashes_to_save
    ]  # Directly assigning would make buildinfo_packages a reference, not a copy
    buildinfo_packages.append("tfm")

    package_buildinfo_dict = get_build_info(buildinfo_packages, self.daq_setup_script)
    
    try:
        commit_info_fullpathname = "%s/%s" % (
            os.path.dirname(self.daq_setup_script),get_commit_info_filename("tfm_start")
        )
        if os.path.exists(commit_info_fullpathname):
            with open(commit_info_fullpathname) as commitfile:
                outf.write("%s" % (commitfile.read()))
        else:
            outf.write("%s" % (get_commit_info("tfm_start",os.environ["TFM_DIR"])))
    except Exception:
        # Not an exception in a bad sense as the throw just means we're using DAQInterface as a ups product
        self.fill_package_versions(["tfm"])
        outf.write(
            "tfm commit/version: %s"
            % (self.package_versions["tfm"])
        )

    outf.write(" %s\n\n" % (package_buildinfo_dict["tfm"]))

    package_commit_dict = {}
    packages_whose_versions_we_need = []

    for pkgname in self.package_hashes_to_save:

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

    for pkgname in packages_whose_versions_we_need:
        package_commit_dict[pkgname] = "%s commit/version: %s" % (
            pkgname,
            self.package_versions[pkgname.replace("-", "_")],
        )

    for pkg in sorted(package_commit_dict.keys()):
        outf.write("%s"      % (package_commit_dict[pkg]))
        outf.write(" %s\n\n" % (package_buildinfo_dict[pkg]))

    outf.write(
        "\nprocess management method: %s\n"
        % (os.environ["TFM_PROCESS_MANAGEMENT_METHOD"])
    )

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

    for (recorddir, dummy, recordfiles) in os.walk(self.tmp_run_record):
        for recordfile in recordfiles:
            os.chmod("%s/%s" % (recorddir, recordfile), 0o444)

    try:
        shutil.copytree(self.tmp_run_record, self.semipermanent_run_record)
    except:
        self.print_log("w", traceback.format_exc())
        self.print_log(
            "w",
            make_paragraph(
                ('Attempt to copy temporary run record "%s" into "%s" didn\'t work; '
                 'keep in mind that %s will be clobbered next time you run on this partition')
                % (
                    self.tmp_run_record,
                    self.semipermanent_run_record,
                    self.tmp_run_record,
                )
            ),
        )

    self.print_log(
        "d",
        make_paragraph(
            ("Saved run record in %s, will copy over to yet-to-be-created "
             "directory %s/<value of run number> on the start transition")
            % (outdir, self.record_directory)
        ),
        2,
    )

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
