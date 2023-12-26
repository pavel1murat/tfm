
import random, string, os, sys, subprocess, socket, time, re, copy;
# from subprocess import Popen
# import socket
# from time import sleep
# import time
# import re
# import sys
# import copy

sys.path.append(os.environ["TFM_DIR"])

import rc.control.utilities as rcu;

# from rc.control.utilities import host_is_local
# from rc.control.utilities import get_pids
# from rc.control.utilities import get_setup_commands
# from rc.control.utilities import date_and_time
# from rc.control.utilities import date_and_time_filename
# from rc.control.utilities import construct_checked_command
# from rc.control.utilities import obtain_messagefacility_fhicl
# from rc.control.utilities import make_paragraph
# from rc.control.utilities import get_short_hostname
# from rc.control.utilities import get_messagefacility_template_filename
# from rc.control.utilities import RaisingThread


def bootfile_name_to_execname(bootfile_name):

    if   "BoardReader"    in bootfile_name: execname = "boardreader"
    elif "EventBuilder"   in bootfile_name: execname = "eventbuilder"
    elif "DataLogger"     in bootfile_name: execname = "datalogger"
    elif "Dispatcher"     in bootfile_name: execname = "dispatcher"
    elif "RoutingManager" in bootfile_name: execname = "routing_manager"
    else: assert False

    return execname

#------------------------------------------------------------------------------
# assumes type(self)=FarmManager
#------------------------------------------------------------------------------
def launch_procs_on_host(self,host,
                         launch_commands_to_run_on_host,
                         launch_commands_to_run_on_host_background,
                         launch_commands_on_host_to_show_user):
    # breakpoint()
    debug_level = 2
    self.print_log("i", "Executing commands to launch processes on %s" % (host))

    # Before we try launching the processes, let's make sure there
    # aren't any pre-existing processes listening on the same ports

    self.print_log("d","Before check for existing processes on %s" % host,debug_level)
    grepped_lines    = []
    preexisting_pids = rcu.get_pids("\|".join(
        ["%s.*id:\s\+%s" % (bootfile_name_to_execname(p.name), p.port) for p in self.procinfos if p.host == host]),
                                host,grepped_lines)

    if self.attempt_existing_pid_kill and len(preexisting_pids) > 0:
        self.print_log("i", "Found existing processes on %s" % (host))

        kill_procs_on_host(self, host, kill_art=True, use_force=True)

        self.print_log("d","Before re-check for existing processes on %s" % (host),debug_level)
        grepped_lines    = []
        preexisting_pids = rcu.get_pids(
            "\|".join(
                [
                    "%s.*id:\s\+%s"
                    % (bootfile_name_to_execname(procinfo.name), procinfo.port)
                    for procinfo in self.procinfos
                    if procinfo.host == host
                ]
            ),
            host,
            grepped_lines,
        )

    if len(preexisting_pids) > 0:
        self.print_log("e",rcu.make_paragraph(
            ("On host %s, found artdaq process(es) already existing which use the ports"
             " TFM was going to use; this may be the result of an improper cleanup from"
             " a prior run: " % host))
        )
        self.print_log("e","\n" + "\n".join(grepped_lines))
        self.print_log("i",("...note that the process(es) may get automatically"
                            " cleaned up during DAQInterface recovery\n"),
        )
        raise Exception(rcu.make_paragraph(
                ("TFM found previously-existing artdaq processes using desired ports;"
                 " see error message above for details"))
        )

    self.print_log("d","After check for existing processes on %s" % host,debug_level)
#------------------------------------------------------------------------------
#   Each command already terminated by ampersand
####
    launchcmd = rcu.construct_checked_command(launch_commands_to_run_on_host)
    launchcmd += "; "
    launchcmd += " ".join(launch_commands_to_run_on_host_background)

    if not rcu.host_is_local(host):
        launchcmd = "ssh -f " + host + " '" + launchcmd + "'"

    self.print_log("d", "\nartdaq process launch commands to execute on %s (output will be in %s:%s):\n%s\n"
                   % (host,host,self.launch_attempt_files[host],"\n".join(launch_commands_on_host_to_show_user)),
                   debug_level)

    proc = subprocess.Popen(launchcmd,executable="/bin/bash",shell=True,
                            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding="utf-8")

    out, _ = proc.communicate()
    status = proc.returncode

    if status != 0:
        self.print_log("e",
                       "Status error raised in attempting to launch processes on %s, to investigate, see %s:%s for output"
                       % (host, host, self.launch_attempt_files[host]))

        self.print_log("i",rcu.make_paragraph(
            ('You can also try running again with the "debug level" in the boot file set to 4.'
             ' Otherwise, you can recreate what DAQInterface did by performing a clean login'
             ' to %s, source-ing the DAQInterface environment and executing the following:') % host)
        )
        self.print_log("i","\n" + "\n".join(launch_commands_on_host_to_show_user)+"\n")
        self.print_log("d","Output from failed command:\n" + out,debug_level)
        raise Exception("ERROR to launch processes on %s; status=%s" % (host,status))
    else:
        self.print_log("d", "...host %s done." % host,debug_level)

    return status  # end of launch_procs_on_host
#------------------------------------------------------------------------------
# JCF, Dec-18-18

# For the purposes of more helpful error reporting if DAQInterface determines that 
# launch_procs_base ultimately failed, have launch_procs_base return a dictionary 
# whose keys are the hosts on which it ran commands, and whose values are the list 
# of commands run on those hosts
# at this point assume that we know the run number
#------------------------------------------------------------------------------
def launch_procs_base(self):

    mf_fcl = rcu.obtain_messagefacility_fhicl(self.have_artdaq_mfextensions())
    self.create_setup_fhiclcpp_if_needed()

    cmds = []
    cmds.append("if [[ -z $( command -v fhicl-dump ) ]]; then %s; source %s; fi"
                % (";".join(rcu.get_setup_commands(self.productsdir, self.spackdir)),os.environ["TFM_SETUP_FHICLCPP"]))
    cmds.append("if [[ $FHICLCPP_VERSION =~ v4_1[01]|v4_0|v[0123] ]]; then dump_arg=0;else dump_arg=none;fi")
    cmds.append("fhicl-dump -l $dump_arg -c %s" % (rcu.get_messagefacility_template_filename()))

    cmd = "; ".join(cmds)
    proc = subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding="utf-8")
    proc.wait();

    if proc.returncode != 0:
        self.print_log("e","\nNonzero return value (%d) resulted when trying to run the following:\n%s\n"
                       % (status, "\n".join(cmds))
        )
        self.print_log("e","STDOUT output: \n%s" % proc.stdout)
        self.print_log("e","STDERR output: \n%s" % proc.stderr)

        self.print_log("e",rcu.make_paragraph(
            ("The FHiCL code designed to control MessageViewer, found in %s, appears to contain "
             "one or more syntax errors, or there was a problem running fhicl-dump")
            % (rcu.get_messagefacility_template_filename()))
        )

        raise Exception(
            ("The FHiCL code designed to control MessageViewer, found in %s, appears to contain "
             "one or more syntax errors (Or there was a problem running fhicl-dump)")
            % (rcu.get_messagefacility_template_filename())
        )
#------------------------------------------------------------------------------
# copy message facility FCL to each remote host
#------------------------------------------------------------------------------
    for host in set([procinfo.host for procinfo in self.procinfos]):
        if not rcu.host_is_local(host):
            cmd    = "scp -p %s %s:%s" % (mf_fcl,host,mf_fcl)
            status = subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).wait()

            if status != 0:
                raise Exception('ERROR in %s executing "%s"' % (launch_procs_base.__name__, cmd))
#------------------------------------------------------------------------------
# Need to run artdaq processes in the background so they're persistent outside of this function's Popen calls
# Don't want to clobber a pre-existing logfile or clutter the commands via "$?" checks
####
    launch_commands_to_run_on_host            = {} # a dict of pairs {host:list_of_commands}
    launch_commands_to_run_on_host_background = {}
    launch_commands_on_host_to_show_user      = {}

    # breakpoint()
    self.launch_attempt_files                 = {}

    for p in self.procinfos:
        if p.host == "localhost": p.host = rcu.get_short_hostname()
        # breakpoint()
        if not p.host in launch_commands_to_run_on_host:
#------------------------------------------------------------------------------
# form the name of the PMT log file, assume know the run number
#------------------------------------------------------------------------------
            fn_format = self.pmt_log_filename_format()
            self.launch_attempt_files[p.host] =  fn_format % (
                self.log_directory,self.run_number, p.host,self.fUser,self.partition(),rcu.date_and_time_filename())

            launch_commands_to_run_on_host           [p.host] = []
            launch_commands_to_run_on_host_background[p.host] = []
            launch_commands_on_host_to_show_user     [p.host] = []

            launch_commands_to_run_on_host[p.host].append("set +C")
            launch_commands_to_run_on_host[p.host].append("echo > %s" % (self.launch_attempt_files[p.host]))
            launch_commands_to_run_on_host[p.host] += rcu.get_setup_commands(self.productsdir, self.spackdir,self.launch_attempt_files[p.host])
            launch_commands_to_run_on_host[p.host].append("source %s for_running >> %s 2>&1 " % (
                self.daq_setup_script, self.launch_attempt_files[p.host])
            )
            launch_commands_to_run_on_host[p.host].append("export FHICL_FILE_PATH=%s"    % os.environ.get("FHICL_FILE_PATH"))
            launch_commands_to_run_on_host[p.host].append("export ARTDAQ_RUN_NUMBER=%s"  % self.run_number)
            launch_commands_to_run_on_host[p.host].append("export ARTDAQ_LOG_ROOT=%s"    % self.log_directory)
            launch_commands_to_run_on_host[p.host].append("export ARTDAQ_LOG_FHICL=%s"   % mf_fcl)
            launch_commands_to_run_on_host[p.host].append("which boardreader >> %s 2>&1 "% self.launch_attempt_files[p.host])  
#------------------------------------------------------------------------------
# Assume if this works, eventbuilder, etc. are also there
############
            launch_commands_to_run_on_host[p.host].append(
                "%s/bin/mopup_shmem.sh %d --force >> %s 2>&1" % (os.environ["TFM_DIR"],self.partition(),self.launch_attempt_files[p.host])
            )
            # launch_commands_to_run_on_host[ p.host ].append("setup valgrind v3_13_0")
            # launch_commands_to_run_on_host[ p.host ].append("export LD_PRELOAD=libasan.so")
            # launch_commands_to_run_on_host[ p.host ].append("export ASAN_OPTIONS=alloc_dealloc_mismatch=0")

            for command in launch_commands_to_run_on_host[p.host]:
                res = re.search(r"^([^>]*).*%s.*$" % (self.launch_attempt_files[p.host]),command)
                if not res:
                    launch_commands_on_host_to_show_user[p.host].append(command)
                else:
                    launch_commands_on_host_to_show_user[p.host].append(res.group(1))

        prepend = p.prepend.strip('"')
        base_launch_cmd = (
            '%s %s -c "id: %s commanderPluginType: xmlrpc rank: %s application_name: %s partition_number: %d"'
            % ( prepend,
                bootfile_name_to_execname(p.name),
                p.port,
                p.rank,
                p.label,
                self.partition())
        )
        if p.allowed_processors is not None:
            base_launch_cmd = "taskset --cpu-list %s %s" % (
                p.allowed_processors,
                base_launch_cmd,
            )
        elif self.allowed_processors is not None:
            base_launch_cmd = "taskset --cpu-list %s %s" % (
                self.allowed_processors,
                base_launch_cmd,
            )

        # base_launch_cmd = "valgrind --tool=callgrind %s" % (base_launch_cmd)
        launch_cmd = "%s >> %s 2>&1 & " % (base_launch_cmd,self.launch_attempt_files[p.host],)

        launch_commands_to_run_on_host_background[p.host].append(launch_cmd)
        launch_commands_on_host_to_show_user     [p.host].append("%s &" % (base_launch_cmd))
    # breakpoint()
    # print
    # breakpoint()
    threads = []
    for host in launch_commands_to_run_on_host:
        t = rcu.RaisingThread(
            target=launch_procs_on_host,
            args=(
                self,
                host,
                launch_commands_to_run_on_host[host],
                launch_commands_to_run_on_host_background[host],
                launch_commands_on_host_to_show_user[host],
            ),
        )
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    return launch_commands_on_host_to_show_user


def process_launch_diagnostics_base(self, procinfos_of_failed_processes):
    for host in set([procinfo.host for procinfo in procinfos_of_failed_processes]):
        self.print_log("e",
                       ("\nOutput of unsuccessful attempted process launch "
                        "on %s can be found in file %s:%s")
                       % (host, host, self.launch_attempt_files[host])
        )


def kill_procs_on_host(self, host, kill_art=False, use_force=False):

    artdaq_pids, labels_of_found_processes = get_pids_and_labels_on_host(host, self.procinfos)

    if len(artdaq_pids) > 0:
        if not use_force:
            self.print_log(
                "d",
                "%s: Found the following processes on %s, will attempt to kill them: %s"
                % (rcu.date_and_time(), host, " ".join(labels_of_found_processes)),
                2,
            )

            cmd = "kill %s" % (" ".join(artdaq_pids))
            if not rcu.host_is_local(host):
                cmd = "ssh -x " + host + " '" + cmd + "'"

            proc = subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            proc.wait()
            self.print_log(
                "d",
                "%s: Finished (attempted) kill of the following processes on %s: %s"
                % (rcu.date_and_time(), host, " ".join(labels_of_found_processes)),
                2,
            )

        else:
            self.print_log("w",rcu.make_paragraph(
                ("Despite receiving a termination signal, the following artdaq processes"
                 " on %s were not killed, so they'll be issued a SIGKILL: %s")
                % (host, " ".join(labels_of_found_processes)))
            )

            cmd = "kill -9 %s" % (" ".join(artdaq_pids))

            if not rcu.host_is_local(host): cmd = "ssh -x " + host + " '" + cmd + "'"

            proc = subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            proc.wait()
            self.print_log(
                "d",
                "%s: Finished (attempted) kill -9 of the following processes on %s: %s"
                % (rcu.date_and_time(), host, " ".join(labels_of_found_processes)),
                2,
            )
#------------------------------------------------------------------------------
# kill art processes
####
    if kill_art:
        art_pids = rcu.get_pids("art -c .*partition_%d" % self.partition(),host)

        if len(art_pids) > 0:

            cmd = "kill -9 %s" % (" ".join(art_pids))  # JCF, Dec-8-2018: the "-9" is apparently needed...

            if not rcu.host_is_local(host): 
                cmd = "ssh -x " + host + " '" + cmd + "'"

            self.print_log("d","%s: About to kill the artdaq-associated art processes on %s"
                           % (rcu.date_and_time(),host),2)

            subprocess.Popen(cmd,executable="/bin/bash",
                             shell=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL).wait()
            
            self.print_log("d","%s: Finished kill of the artdaq-associated art processes on %s"
                           % (rcu.date_and_time(), host),2)
    return

def kill_procs_base(self):

    for host in set([p.host for p in self.procinfos]):
        kill_procs_on_host(self, host, kill_art=True)

    time.sleep(1)

    for host in set([p.host for p in self.procinfos]):
        kill_procs_on_host(self, host, use_force=True)

    self.procinfos = []

    return

#------------------------------------------------------------------------------
# returns the name of the most recent PMT logfile on a given host 
#------------------------------------------------------------------------------
def get_process_manager_log_filename(self, host):

    fn_format = self.pmt_log_filename_format();
    pattern   = fn_format % (self.log_directory,self.run_number,host,self.fUser,self.partition(),"*")
    cmd       = "ls -tr1 "+pattern+" | tail -1"

    if not rcu.host_is_local(host): cmd = "ssh -f %s '%s'" % (host,cmd)

    x  = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    fn = x.stdout.readlines()[0].decode("utf-8").strip()
    return fn


def get_process_manager_log_filenames_base(self):
    output = []

    for host in set([p.host for p in self.procinfos]):
        output.append(get_process_manager_log_filename(self,host))

    return output


def find_process_manager_variable_base(self, line):
    return False


def set_process_manager_default_variables_base(self):
    pass  # There ARE no persistent variables specific to direct process management


def reset_process_manager_variables_base(self):
    pass


def process_manager_cleanup_base(self):
    pass

def get_pid_for_process_base(self, procinfo):

    assert procinfo in self.procinfos

    greptoken = (
        bootfile_name_to_execname(procinfo.name) + " -c .*" + procinfo.port + ".*"
    )

    grepped_lines = []
    pids = rcu.get_pids(greptoken, procinfo.host, grepped_lines)

    ssh_pids = rcu.get_pids("ssh .*" + greptoken, procinfo.host)

    cleaned_pids = [pid for pid in pids if pid not in ssh_pids]

    if len(cleaned_pids) == 1:
        return cleaned_pids[0]
    elif len(cleaned_pids) == 0:
        return None
    else:
        for grepped_line in grepped_lines:
            print(grepped_line)

        print("Appear to have duplicate processes for %s on %s, pids: %s"
              % (procinfo.label, procinfo.host, " ".join(pids)))

    return None


def mopup_process_base(self, procinfo):

    if not rcu.host_is_local(procinfo.host):
        on_other_node = True
    else:
        on_other_node = False

    pid = get_pid_for_process_base(self, procinfo)

    if pid is not None:
        cmd = "kill %s" % (pid)

        if on_other_node:
            cmd = "ssh -x %s '%s'" % (procinfo.host, cmd)

        status = subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL).wait()
        time.sleep(1)

        if get_pid_for_process_base(self, procinfo) is not None:
            cmd = "kill -9 %s > /dev/null 2>&1" % (pid)

            if on_other_node:
                cmd = "ssh -x %s '%s'" % (procinfo.host, cmd)

            self.print_log(
                "w",
                "A standard kill of the artdaq process %s on %s didn't work; resorting to a kill -9"
                % (procinfo.label, procinfo.host),
            )

            subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL
            ).wait()

    # Will need to perform some additional cleanup (clogged ports, zombie art
    # processes, etc.)

    ssh_mopup_ok = True
    related_process_mopup_ok = True

    # Need to deal with the lingering ssh command if the lost process is on a
    # remote host
    if on_other_node:

        # Mopup the ssh call on this side
        ssh_grepstring = "ssh.*%s.*%s -c.*%s" % (
            procinfo.host,
            bootfile_name_to_execname(procinfo.name),
            procinfo.label,
        )
        pids = rcu.get_pids(ssh_grepstring)

        if len(pids) == 1:
            subprocess.Popen("kill %s > /dev/null 2>&1" % (pids[0]),
                             executable="/bin/bash",
                             shell=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL
            ).wait()
            pids = rcu.get_pids(ssh_grepstring)
            if len(pids) == 1:
                ssh_mopup_ok = False
        elif len(pids) > 1:
            ssh_mopup_ok = False

    # And take out the process(es) associated with the artdaq process via its
    # listening port (e.g., the art processes)

    cmd = "kill %s > /dev/null 2>&1" % (
        " ".join(get_related_pids_for_process(procinfo))
    )

    if on_other_node:
        cmd = "ssh -x %s '%s'" % (procinfo.host, cmd)

    subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,
    ).wait()

    unkilled_related_pids = get_related_pids_for_process(procinfo)
    if len(unkilled_related_pids) == 0:
        related_process_mopup_ok = True
    else:
        related_process_mopup_ok = False
        self.print_log("d",rcu.make_paragraph(
            ("Warning: unable to normally kill process(es) associated with"
             " now-deceased artdaq process %s; on %s the following pid(s) remain:"
             " %s. Will now resort to kill -9 on these processes.")
            % (procinfo.label, procinfo.host, " ".join(unkilled_related_pids))),2)

        cmd = "kill -9 %s > /dev/null 2>&1 " % (" ".join(unkilled_related_pids))

        if on_other_node:
            cmd = "ssh -x %s '%s'" % (procinfo.host, cmd)

        subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
        ).wait()

    if not ssh_mopup_ok:
        self.print_log("w",rcu.make_paragraph(
            ("There was a problem killing the ssh process to %s related "
             "to the deceased artdaq process %s at %s:%s; there *may* be issues "
            "with the next run using that host and port as a result")
            % (procinfo.host, procinfo.label, procinfo.host, procinfo.port))
        )

    if not related_process_mopup_ok:
        self.print_log("w",rcu.make_paragraph(
            ("At least some of the processes on %s related to deceased artdaq process "
             "%s at %s:%s (e.g. art processes) had to be forcibly killed; there *may* be "
             "issues with the next run using that host and port as a result")
            % (procinfo.host, procinfo.label, procinfo.host, procinfo.port))
        )
#------------------------------------------------------------------------------
# If you change what this function returns, you should rename it for obvious reasons
#------------------------------------------------------------------------------
def get_pids_and_labels_on_host(host, procinfos):

    greptoken = (
        "[0-9]:[0-9][0-9]\s\+.*\(%s\).*application_name.*partition_number:\s*%s"
        % ("\|".join(set([bootfile_name_to_execname(p.name) for p in procinfos])),
            os.environ["ARTDAQ_PARTITION_NUMBER"])
    )
    sshgreptoken = (
        "[0-9]:[0-9][0-9]\s\+ssh.*\(%s\).*application_name.*partition_number:\s*%s"
        % ("\|".join(set([bootfile_name_to_execname(p.name) for p in procinfos])),
            os.environ["ARTDAQ_PARTITION_NUMBER"])
    )

    # greptoken =
    # "[0-9]:[0-9][0-9]\s\+valgrind.*\(%s\).*application_name.*partition_number:\s*%s"
    #% \
    #            ("\|".join(set([bootfile_name_to_execname(procinfo.name) for
    #            procinfo in procinfos])), \
    # os.environ["ARTDAQ_PARTITION_NUMBER"])

    grepped_lines = []
    pids = rcu.get_pids(greptoken, host, grepped_lines)

    ssh_pids = rcu.get_pids(sshgreptoken, host)

    cleaned_pids = [pid for pid in pids if pid not in ssh_pids]
    cleaned_lines = [line for line in grepped_lines if " ssh " not in line]

    labels_of_found_processes = []

    for line in cleaned_lines:
        res = re.search(r"application_name:\s+(\S+)", line)
        assert res
        labels_of_found_processes.append(res.group(1))

    return cleaned_pids, labels_of_found_processes


def get_related_pids_for_process(procinfo):
    related_pids = []

    netstat_cmd = "netstat -alpn | grep %s" % (procinfo.port)

    if not rcu.host_is_local(procinfo.host):
        netstat_cmd = "ssh -x %s '%s'" % (procinfo.host, netstat_cmd)

    proc = subprocess.Popen(netstat_cmd,executable="/bin/bash",shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
    )

    for procline in proc.stdout.readlines():
        procstring = procline.decode("utf-8")
        res = re.search(r"([0-9]+)/(.*)", procstring.split()[-1])
        if res:
            pid = res.group(1)
            pname = res.group(2)
            if "python" not in pname:  # Don't want DAQInterface to kill itself off...
                related_pids.append(res.group(1))
    return set(related_pids)


# check_proc_heartbeats_base() will check that the expected artdaq
# processes are up and running


def check_proc_heartbeats_base(self, requireSuccess=True):

    is_all_ok           = True
    procinfos_to_remove = []
    found_processes     = []

    for host in set([p.host for p in self.procinfos]):

        (pids,labels_of_found_processes) = get_pids_and_labels_on_host(host,self.procinfos)

        for procinfo in [procinfo for procinfo in self.procinfos if procinfo.host == host]:
            if procinfo.label in labels_of_found_processes:
                found_processes.append(procinfo)
            else:
                is_all_ok = False

                if requireSuccess:
                    self.print_log(
                        "e",
                        "%s: Appear to have lost process with label %s on host %s"
                        % (rcu.date_and_time(), procinfo.label, procinfo.host),
                    )
                    procinfos_to_remove.append(procinfo)

                    mopup_process_base(self, procinfo)

    if not is_all_ok and requireSuccess:
        if self.state(self.name) == "running":
            for procinfo in procinfos_to_remove:
                self.procinfos.remove(procinfo)
                self.throw_exception_if_losing_process_violates_requirements(procinfo)
            self.print_log(
                "i",
                "Processes remaining:\n%s"
                % ("\n".join([procinfo.label for procinfo in self.procinfos])),
            )
        else:
            raise Exception(
                "\nProcess(es) %s died or found in Error state"
                % (
                    ", ".join(
                        ['"' + procinfo.label + '"' for procinfo in procinfos_to_remove]
                    )
                )
            )

    if is_all_ok:
        assert len(found_processes) == len(self.procinfos)

    return found_processes

def main():

    # JCF, Dec-7-2018

    # This is a toy version of the true Procinfo class defined within
    # the DAQInterface class, meant to be used just for testing this
    # module

    class Procinfo(object):
        def __init__(self, name, rank, host, port, label):
            self.name = name
            self.rank = rank
            self.port = port
            self.host = host
            self.label = label

    launch_procs_test = True

    if launch_procs_test:

        class MockDAQInterface:
            debug_level = 3
            productsdir = "/mu2e/ups"
            daq_setup_script = "/home/jcfree/artdaq-demo_multiple_fragments_per_boardreader/setupARTDAQDEMO"

            procinfos = []
            procinfos.append(Procinfo("BoardReader" , "0", "localhost", "10100", "MockBoardReader" ))
            procinfos.append(Procinfo("EventBuilder", "1", "localhost", "10101", "MockEventBuilder"))

            def print_log(self, ignore, string_to_print, ignore2):
                print(string_to_print)

        launch_procs_base(MockDAQInterface())


if __name__ == "__main__":
    main()
