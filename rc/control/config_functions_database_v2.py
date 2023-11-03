# JCF, Apr-20-2017

# For this module to work, you'll first need to have set up the
# artdaq-database in the shell environment

import os
import sys

sys.path.append(os.environ["ARTDAQ_DAQINTERFACE_DIR"])

dbdirs = [
    dbdir
    for dbdir in os.environ["PYTHONPATH"].split(":")
    if "/artdaq_database/" in dbdir
]
assert (
    len(dbdirs) == 1
), "More than one path in $PYTHONPATH appears to be an artdaq-database path"
sys.path.append(dbdirs[0] + "/../bin")

import subprocess
from subprocess import Popen
from rc.control.utilities import make_paragraph
from rc.control.utilities import fhiclize_document
import shutil
from shutil import copyfile

import re
import os
import string
from time import time

from rc.control.utilities import expand_environment_variable_in_string


def version_to_integer(version):
    res = re.search(r"v([0-9])_([0-9][0-9])_([0-9][0-9]).*", version)
    assert res, make_paragraph(
        'Developer error: unexpected artdaq_database version format "%s". Please contact the artdaq-developers@fnal.gov mailing list.'
        % (version)
    )
    majornum = int(res.group(1))
    minornum = int(res.group(2))
    patchnum = int(res.group(3))

    return patchnum + 100 * minornum + 10000 * majornum


if version_to_integer(os.environ["ARTDAQ_DATABASE_VERSION"]) >= version_to_integer(
    "v1_04_75"
):
    from conftool import getListOfMaskedRunConfigurations
else:
    print
    print(
        make_paragraph(
            "WARNING: you appear to be using an artdaq_database version older than v1_04_75 (%s), on the config transition DAQInterface will accept a configuration even if it's been masked off"
            % (os.environ["ARTDAQ_DATABASE_VERSION"])
        )
    )
    print

from conftool import exportConfiguration
from conftool import getListOfAvailableRunConfigurations
from conftool import archiveRunConfiguration
from conftool import updateArchivedRunConfiguration


def config_basedir(self):
    return "/tmp/database/"


def get_config_info_base(self):

    basedir = os.getcwd()

    ffp = []

    uuidgen = (
        Popen("uuidgen", shell=True, stdout=subprocess.PIPE)
        .stdout.readlines()[0]
        .strip()
        .decode("utf-8")
    )
    tmpdir = config_basedir(self) + uuidgen

    Popen("mkdir -p %s" % tmpdir, shell=True).wait()
    os.chdir(tmpdir)

    tmpflagsfile = "%s/flags.fcl" % (tmpdir)
    with open(tmpflagsfile, "w") as outf:
        outf.write("flag_inactive:true\n")

    for subconfig in self.subconfigs_for_run:

        if subconfig not in getListOfAvailableRunConfigurations(subconfig):
            raise Exception(
                make_paragraph(
                    'Error: (sub)config "%s" was not found in a call to conftool.getListOfAvailableRunConfigurations'
                    % (subconfig)
                )
            )
        else:
            try:
                if subconfig in getListOfMaskedRunConfigurations():
                    raise Exception(
                        make_paragraph(
                            'Error: (sub)config "%s" has been invalidated (i.e., it appears in a call to conftool.getListOfMaskedRunConfigurations given the flags file %s)'
                            % (subconfig, tmpflagsfile)
                        )
                    )
            except NameError:
                pass

        subconfigdir = "%s/%s" % (tmpdir, subconfig)
        os.mkdir(subconfigdir)
        os.chdir(subconfigdir)

        result = exportConfiguration(subconfig)

        if not result:
            raise Exception(
                'Error: the exportConfiguration function with the argument "%s" returned False'
                % subconfig
            )

        for dirname, dummy, dummy in os.walk(subconfigdir):
            ffp.append(dirname)

        # DAQInterface doesn't like duplicate files with the same basename
        # in the collection of subconfigurations, and schema.fcl isn't used
        # since DAQInterface just wants the FHiCL documents used to initialize
        # artdaq processes...
        for dirname, dummy, filenames in os.walk(subconfigdir):
            if "schema.fcl" in filenames:
                os.unlink("%s/schema.fcl" % (dirname))

    os.unlink(tmpflagsfile)
    os.chdir(basedir)
    return tmpdir, ffp


def put_config_info_base(self):

    self.print_log("i,", "Attempting to save config info to the database...", 1, False)

    starttime = time()

    scriptdir = os.environ["ARTDAQ_DAQINTERFACE_DIR"] + "/utils"

    if not os.path.exists(scriptdir):
        raise Exception(
            'Error in %s: unable to find script directory "%s"; should be in the base directory of the package'
            % (put_config_info_base.__name__, scriptdir)
        )

    runnum = str(self.run_number)
    runrecord = self.record_directory + "/" + runnum

    tmpdir = "/tmp/" + Popen(
        "uuidgen", shell=True, stdout=subprocess.PIPE
    ).stdout.readlines()[0].strip().decode("utf-8")

    cmds = []
    cmds.append(" scriptdir=" + scriptdir)
    cmds.append("mkdir " + tmpdir)
    cmds.append("cd " + tmpdir)
    cmds.append("cp -rp " + runrecord + " . ")
    cmds.append("chmod 777 " + runnum)
    cmds.append(
        "cat "
        + runnum
        + "/metadata.txt | awk -f $scriptdir/fhiclize_metadata_file.awk > "
        + runnum
        + "/metadata.fcl"
    )
    cmds.append(
        "cat "
        + runnum
        + "/boot.txt | awk -f $scriptdir/fhiclize_boot_file.awk > "
        + runnum
        + "/boot.fcl"
    )
    cmds.append(
        "cat "
        + runnum
        + "/known_boardreaders_list.txt | awk -f $scriptdir/fhiclize_known_boardreaders_list_file.awk > "
        + runnum
        + "/known_boardreaders_list.fcl"
    )
    cmds.append("rm -f " + runnum + "/*.txt")

    if os.getenv("ARTDAQ_DATABASE_CONFDIR") is None:
        raise Exception(
            make_paragraph(
                "Environment variable ARTDAQ_DATABASE_CONFDIR needs to be set in order for DAQInterface to determine where to find the schema.fcl file needed to archive configurations to the database; since ARTDAQ_DATABASE_CONFDIR is not set this may indicate that the version of artdaq_database you're using is old"
            )
        )

    cmds.append("cp -p %s/schema.fcl ." % os.environ["ARTDAQ_DATABASE_CONFDIR"])

    status = Popen("; ".join(cmds), shell=True).wait()

    for filename in [
        tmpdir,
        "%s/%s" % (tmpdir, runnum),
        "%s/%s/metadata.fcl" % (tmpdir, runnum),
    ]:
        assert os.path.exists(filename), "%s is unexpectedly missing" % (filename)

    if status != 0:
        raise Exception(
            "Problem during execution of the following:\n %s" % "\n".join(cmds)
        )

    with open(
        "%s/%s/DataflowConfiguration.fcl" % (tmpdir, runnum), "w"
    ) as dataflow_file:

        with open("%s/%s/boot.fcl" % (tmpdir, runnum)) as boot_file:
            ignore_until_end_array = (
                False  # flag to allow filtering multi-line fcl array
            )
            for line in boot_file.readlines():

                if line == "\n":
                    continue  # can skip/ignore all blank lines

                if ignore_until_end_array:  # check if filtering multi-line fcl array
                    if re.search(r"\]", line):
                        ignore_until_end_array = False
                    continue

                ignore_this_line = False  # need this for nested for loop:
                for keyname in ["artdaq_process_settings", "debug_level"]:
                    if re.search(r"^\s*%s\s*:" % (keyname), line):
                        ignore_this_line = True
                        if re.search(
                            r"\[[^]]*$", line
                        ):  # if it's a fcl array start "[" without an end "]" (i.e multi-line array)
                            ignore_until_end_array = True
                        break
                if ignore_this_line:
                    continue

                # at this point in the for loop, lines will be written
                if "subsystem_settings" in line:
                    line = line.replace("subsystem_settings", "subsystem_values")

                dataflow_file.write("\n" + line)

        dataflow_file.write("\nartdaq_process_values: [ ")

        for i_p, procinfo in enumerate(self.procinfos):
            dataflow_file.write(
                '{ name: "%s" label: "%s" host: "%s" port: %d subsystem: "%s" rank: %d } '
                % (
                    procinfo.name,
                    procinfo.label,
                    procinfo.host,
                    int(procinfo.port),
                    procinfo.subsystem,
                    int(procinfo.rank),
                )
            )
            if i_p < len(self.procinfos) - 1:
                dataflow_file.write(", ")

        dataflow_file.write(" ]\n")

        with open("%s/%s/metadata.fcl" % (tmpdir, runnum)) as metadata_file:
            for line in metadata_file.readlines():
                if (
                    "DAQInterface_start_time" not in line
                    and "DAQInterface_stop_time" not in line
                    and not line == ""
                ):
                    dataflow_file.write("\n" + line)

    with open("%s/%s/RunHistory.fcl" % (tmpdir, runnum), "w") as runhistory_file:
        runhistory_file.write("\nrun_number: %s" % (runnum))

        with open("%s/%s/metadata.fcl" % (tmpdir, runnum)) as metadata_file:
            for line in metadata_file.readlines():
                if "config_name" in line:
                    runhistory_file.write("\n" + line)
                elif "components" in line:
                    runhistory_file.write("\n" + line)

        if os.environ[
            "DAQINTERFACE_PROCESS_MANAGEMENT_METHOD"
        ] == "external_run_control" and os.path.exists(
            "/tmp/info_to_archive_partition%d.txt" % (self.partition_number)
        ):
            runhistory_file.write(
                fhiclize_document(
                    "/tmp/info_to_archive_partition%d.txt" % (self.partition_number)
                )
            )

    basedir = os.getcwd()
    os.chdir(tmpdir)

    subconfigs_for_run = [
        subconfig.replace("/", "_") for subconfig in self.subconfigs_for_run
    ]
    result = archiveRunConfiguration("_".join(subconfigs_for_run), runnum)

    if not result:
        raise Exception(
            make_paragraph(
                "There was an error attempting to archive the FHiCL documents (temporarily saved in %s); this may be because of an issue with the schema file, %s/schema.fcl, such as an unlisted fragment generator"
                % (tmpdir, os.environ["ARTDAQ_DATABASE_CONFDIR"])
            )
        )

    os.chdir(basedir)

    res = re.search(r"\w{8}-\w{4}-\w{4}-\w{4}-\w{12}", tmpdir)
    assert (
        res
    ), "Unable to find uuidgen-generated temporary directory, will perform no deletions"

    shutil.rmtree(tmpdir)

    endtime = time()
    self.print_log("i", "done (%.1f seconds)." % (endtime - starttime))

    return


def put_config_info_on_stop_base(self):

    self.print_log("i,", "Attempting to save config info to the database...", 1, False)

    starttime = time()

    runnum = str(self.run_number)
    tmpdir = "/tmp/" + Popen(
        "uuidgen", shell=True, stdout=subprocess.PIPE
    ).stdout.readlines()[0].strip().decode("utf-8")
    os.mkdir(tmpdir)
    os.mkdir("%s/%s" % (tmpdir, runnum))
    os.chdir(tmpdir)

    with open("%s/%s/RunHistory2.fcl" % (tmpdir, runnum), "w") as runhistory_file:

        metadata_filename = "%s/%s/metadata.txt" % (
            self.record_directory,
            str(self.run_number),
        )

        if os.path.exists(metadata_filename):
            found_start_time = False
            found_stop_time = False

            with open(metadata_filename) as metadata_file:
                for line in metadata_file:
                    res = re.search(r"^DAQInterface start time:\s+(.*)", line)
                    if res:
                        runhistory_file.write(
                            '\nDAQInterface_start_time: "%s"\n' % (res.group(1))
                        )
                        found_start_time = True
                        continue
                    res = re.search(r"^DAQInterface stop time:\s+(.*)", line)
                    if res:
                        runhistory_file.write(
                            '\nDAQInterface_stop_time: "%s"\n' % (res.group(1))
                        )
                        found_stop_time = True

            if not found_start_time:
                self.print_log(
                    "w",
                    "WARNING: unable to find DAQInterface start time in %s; will not save this info into the database"
                    % (metadata_filename),
                )
            if not found_stop_time:
                self.print_log(
                    "w",
                    "WARNING: unable to find DAQInterface stop time in %s; will not save this info into the database"
                    % (metadata_filename),
                )

        else:
            self.print_log(
                "w",
                "Expected file %s wasn't found! Will not save start/stop times of run in the database"
                % (metadata_filename),
            )

        if os.environ[
            "DAQINTERFACE_PROCESS_MANAGEMENT_METHOD"
        ] == "external_run_control" and os.path.exists(
            "/tmp/info_to_archive_partition%d.txt" % (self.partition_number)
        ):
            runhistory_file.write(
                fhiclize_document(
                    "/tmp/info_to_archive_partition%d.txt" % (self.partition_number)
                )
            )

    copyfile(
        "%s/schema.fcl" % (os.environ["ARTDAQ_DATABASE_CONFDIR"]),
        "%s/schema.fcl" % (tmpdir),
    )

    subconfigs_for_run = [
        subconfig.replace("/", "_") for subconfig in self.subconfigs_for_run
    ]
    result = updateArchivedRunConfiguration("_".join(subconfigs_for_run), runnum)

    if not result:
        raise Exception(
            make_paragraph(
                "There was an error attempting to archive the FHiCL documents (temporarily saved in %s); this may be because of an issue with the schema file, %s/schema.fcl, such as an unlisted fragment generator"
                % (tmpdir, os.environ["ARTDAQ_DATABASE_CONFDIR"])
            )
        )

    res = re.search(r"\w{8}-\w{4}-\w{4}-\w{4}-\w{12}", tmpdir)
    assert (
        res
    ), "Unable to find uuidgen-generated temporary directory, will perform no deletions"

    os.chdir("/tmp")
    shutil.rmtree(tmpdir)

    endtime = time()
    self.print_log("i", "done (%.1f seconds)." % (endtime - starttime))


def listdaqcomps_base(self):
    assert False, "%s not yet implemented" % (listdaqcomps_base.__name__)


def listconfigs_base(self):
    print
    print("Available configurations: ")

    config_cntr = 0

    with open("/tmp/listconfigs_" + os.environ["USER"] + ".txt", "w") as outf:
        for config in getListOfAvailableRunConfigurations():
            config_cntr += 1

            if config_cntr <= self.max_configurations_to_list:
                outf.write(config + "\n")
                print(config)


def main():

    listconfigs_test = False
    get_config_info_test = True
    put_config_info_test = False

    if listconfigs_test:
        print("Calling listconfigs_base")
        listconfigs_base("ignored_argument")

    if get_config_info_test:
        print("Calling get_config_info_base")

        class MockDAQInterface:
            subconfigs_for_run = ["ToyComponent_EBwriting00025"]
            debug_level = 2

        mydir, mydirs = get_config_info_base(MockDAQInterface())

        print("FHiCL directories to search: " + " ".join(mydirs))
        print("Directory where the FHiCL documents are located: " + mydir)

    if put_config_info_test:
        print("Calling put_config_info_base")

        class MockDAQInterface:
            run_number = 73
            record_directory = "/daq/artdaq/run_records/"
            config_for_run = "push_pull_testing"

        put_config_info_base(MockDAQInterface())


if __name__ == "__main__":
    main()
