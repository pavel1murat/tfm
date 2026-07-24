#
import random, string, os, sys, subprocess, socket, time, re, copy;
import tfm.rc.control.utilities as rcu;
import tfm.rc.control.artdaq    as artdaq

import TRACE ; TRACE_NAME="manage_proc"

#------------------------------------------------------------------------------
# format (and location) of the PMT logfile - 
# includes directory, run_number, host, user, partition (in integer), and a timestamp
#------------------------------------------------------------------------------
def pmt_log_filename_format(self):
    return "%s/pmt/pmt_%06i_%s_%s_partition_%02i_%s"

#------------------------------------------------------------------------------
# P.Murat: in order to structure the code, make check_launch_results a separate function
#---v--------------------------------------------------------------------------
def check_launch_results_base(self,launch_procs_actions):

    num_launch_procs_checks = 0

    while True:
        num_launch_procs_checks += 1

        self.print_log("i","Checking that processes are up (check %d of a max of %d checks)..."
            % (num_launch_procs_checks, self.max_num_launch_procs_checks),1)
#------------------------------------------------------------------------------
# "False" here means "don't consider it an error if all processes aren't found"
#-----------v------------------------------------------------------------------
        found_processes = self.check_proc_heartbeats(False)
        self.print_log("i","found %d of %d processes." % (len(found_processes),len(self.procinfos)))

        assert type(found_processes) is list, rcu.make_paragraph(
            "check_proc_heartbeats needs to return a list of procinfos"
            " corresponding to the processes it found alive"
        )

        if len(found_processes) == len(self.procinfos):

            self.print_log("i", "All processes appear to be up")
            break
        else:
            time.sleep(self.launch_procs_wait_time / self.max_num_launch_procs_checks)
            if num_launch_procs_checks >= self.max_num_launch_procs_checks:
                missing_processes = [
                    procinfo
                    for procinfo in self.procinfos
                    if procinfo not in found_processes
                ]

                self.print_log(
                    "e",
                    "\nThe following desired artdaq processes failed to launch:\n%s"
                    % (
                        ", ".join(
                            [
                                "%s at %s:%s"
                                % (procinfo.label, procinfo.host, procinfo.port)
                                for procinfo in missing_processes
                            ]
                        )
                    ),
                )
                self.print_log("e",
                               rcu.make_paragraph(
                                ('In order to investigate what happened, you can try re-running with "debug level"'
                                 ' set to 4. If that doesn\'t help, you can directly recreate'
                                 ' what FarmManager did by doing the following:')
                               ),
                )

                for host in set([p.host for p in self.procinfos if p in missing_processes]):
                    self.print_log("i",
                                   ("\nPerform a clean login to %s, source the FarmManager environment, "
                                    "and execute the following:\n%s")
                                   % (host, "\n".join(launch_procs_actions[host])),
                    )

                self.process_launch_diagnostics(missing_processes)

                self.alert_and_recover(
                    ('Problem launching the artdaq processes; scroll above '
                    'the output from the "RECOVER" transition for more info')
                )
                return -1
    return 0

#------------------------------------------------------------------------------
# wait for the command completion 
#---v--------------------------------------------------------------------------
def wait_for_completion_base(self,timeout_ms):
    TRACE.INFO('--START:',TRACE_NAME)
    n_nodes        = len(self.artdaq.list_of_nodes)
    n_not_finished = n_nodes;
    finished       = [0] * n_nodes;
    
    wait_time_ms   = 0;
    
    while ((n_not_finished > 0) and (wait_time_ms < timeout_ms)):
        sleep_time_ms = 200.0;               # 
        time.sleep(sleep_time_ms/1000.0);
        wait_time_ms += sleep_time_ms;
        
        for i in range(n_nodes):
            if (finished[i] == 1) :                         continue
            
            node = self.artdaq.list_of_nodes[i]
            cmd_odb_path = f'/Mu2e/Commands/DAQ/Nodes/{node.name}/Artdaq'
            finished[i]  = self.client.odb_get(cmd_odb_path+'/Finished')
            TRACE.DEBUG(1,f'wait_time_ms:{wait_time_ms:5} i:{i} node:{node.name} cmd_odb_path:{cmd_odb_path} finished:{finished[i]}',TRACE_NAME)
            if (finished[i] == 1):
                node_conf_odb_path = f'/Mu2e/ActiveRunConfiguration/DAQ/Nodes/{node.name}'
                self.client.odb_set(node_conf_odb_path+'/Status',0);
                n_not_finished -= 1;

    TRACE.INFO(f'--END: n_not_finished:{n_not_finished} wait_time_ms:{wait_time_ms}',TRACE_NAME)
    return (n_not_finished, wait_time_ms)

#------------------------------------------------------------------------------
# every time it is called, it generates the job submission script (at begin run)
# so checking that before the run started, doesn't name sense...
# generate job submission script and send a command to each node
#------------------------------------------------------------------------------
def launch_procs_base(self):
    TRACE.INFO('--START:',TRACE_NAME)

    self.generate_job_submission_script();
#------------------------------------------------------------------------------
# trigger job submission
#------------------------------------------------------------------------------
    cmd_name   = 'start_processes'
    timeout_ms = 80000;               # 80 sec
    
    for node in self.artdaq.list_of_nodes:
        cmd_odb_path     = f'/Mu2e/Commands/DAQ/Nodes/{node.name}/Artdaq'
        cmd_odb_par_path = cmd_odb_path+'/'+cmd_name
        self.client.odb_set(cmd_odb_path+'/Name',cmd_name);
        self.client.odb_set(cmd_odb_path+'/ParameterPath',cmd_odb_par_path)
        self.client.odb_set(cmd_odb_path+'/logfile',f'{node.name}_artdaq');

        node_conf_odb_path = f'/Mu2e/ActiveRunConfiguration/DAQ/Nodes/{node.name}'
        self.client.odb_set(node_conf_odb_path+'/Status',1);

        self.client.odb_set(cmd_odb_path+'/timeout_ms',20000);

        self.client.odb_set(cmd_odb_path+'/Finished',0);
        self.client.odb_set(cmd_odb_path+'/Run',1);

    (n_not_finished, wait_time_ms) = self.wait_for_completion(timeout_ms)

    rc = 0;
    if (n_not_finished > 0):
        rc = -1
        for node in self.artdaq.list_of_nodes:
            cmd_odb_path = f'/Mu2e/Commands/DAQ/Nodes/{node.name}/Artdaq'
            finished     = self.client.odb_get(cmd_odb_path+'/Finished')

            if (finished == 0):
                node_conf_odb_path = f'/Mu2e/ActiveRunConfiguration/DAQ/Nodes/{node.name}'
                self.client.odb_set(node_conf_odb_path+'/Status',-1)
        
    TRACE.INFO(f'--END: n_not_finished:{n_not_finished} rc:{rc} wait_time_ms:{wait_time_ms}',TRACE_NAME)
    
    return rc;

#------------------------------------------------------------------------------
def process_launch_diagnostics_base(self, procinfos_of_failed_processes):
    for host in set([procinfo.host for procinfo in procinfos_of_failed_processes]):
        self.print_log("e",
                       ("\nOutput of unsuccessful attempted process launch "
                        "on %s can be found in file %s:%s")
                       % (host, host, self.launch_attempt_files[host])
        )

#------------------------------------------------------------------------------
def kill_procs_on_host(self, host, kill_art=False, use_force=False):

    artdaq_pids, labels_of_found_processes = get_pids_and_labels_on_host(self,host)

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
            self.print_log("d",
                "Finished (attempted) kill of the following processes on %s: %s"
                % (host, " ".join(labels_of_found_processes)),2)

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
                "d","Finished (attempted) kill -9 of the following processes on %s: %s"
                % (host, " ".join(labels_of_found_processes)),2)
#------------------------------------------------------------------------------
# kill art processes
#---v--------------------------------------------------------------------------
    if kill_art:
        art_pids = rcu.get_pids("art -c .*partition_%d" % self.partition(),host)

        if len(art_pids) > 0:

            cmd = "kill -9 %s" % (" ".join(art_pids))  # JCF, Dec-8-2018: the "-9" is apparently needed...

            if not rcu.host_is_local(host): 
                cmd = "ssh -x " + host + " '" + cmd + "'"

            self.print_log("d","About to kill the artdaq-associated art processes on %s"%(host),2)

            subprocess.Popen(cmd,executable="/bin/bash",
                             shell=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL).wait()
            
            self.print_log("d","Finished kill of the artdaq-associated art processes on %s" % (host),2)
    return

#------------------------------------------------------------------------------
def kill_procs_base(self):

    for host in set([p.host for p in self.procinfos]):
        kill_procs_on_host(self, host, kill_art=True)

    time.sleep(1)

    for host in set([p.host for p in self.procinfos]):
        kill_procs_on_host(self, host, use_force=True)

    self.procinfos = []

    return

#------------------------------------------------------------------------------
# self.log_girectory is the same on all nodes (/scratch/mu2e/mu2etrk/.../logs)
#------------------------------------------------------------------------------
def get_process_manager_log_filenames_base(self,run_number):
    output = []

    for host in set([p.host for p in self.procinfos]):
        #  fn = get_process_manager_log_filename(self,host,run_number)
        fn = artdaq.pmt_log_fn_node(host,self.log_directory,self.partition(),run_number)
        output.append(fn)

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

    greptoken = (procinfo.execname + " -c .*" + procinfo.port + ".*")

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
#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
def mopup_process_base(self, procinfo):

    if not rcu.host_is_local(procinfo.host): on_other_node = True
    else:                                    on_other_node = False

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
            procinfo.execname,
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
        " ".join(procinfo.get_related_pids())
    )

    if on_other_node:
        cmd = "ssh -x %s '%s'" % (procinfo.host, cmd)

    subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,
    ).wait()

    unkilled_related_pids = procinfo.get_related_pids()
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
    return
#---^--------------------------------------------------------------------------
# If you change what this function returns, you should rename it for obvious reasons
#------------------------------------------------------------------------------
def get_pids_and_labels_on_host(self,host):
    # breakpoint()
    greptoken = (
        "[0-9]:[0-9][0-9]\s\+.*\(%s\).*application_name.*partition_number:\s*%s"
        % ("\|".join(set([p.execname for p in self.procinfos])),
            self.partition())
    )
    sshgreptoken = (
        "[0-9]:[0-9][0-9]\s\+ssh.*\(%s\).*application_name.*partition_number:\s*%s"
        % ("\|".join(set([p.execname for p in self.procinfos])),self.partition()))

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

#------------------------------------------------------------------------------
# check_proc_heartbeats_base() checks that the expected artdaq processes are up and running
#------------------------------------------------------------------------------
def check_proc_heartbeats_base(self, requireSuccess=True):

    is_all_ok           = True
    procinfos_to_remove = []
    found_processes     = []

    for node in self.artdaq.list_of_nodes: ## set([p.host for p in self.procinfos]):

        host = node.name;
        (pids,labels_of_found_processes) = get_pids_and_labels_on_host(self,host)

        for p in node.list_of_processes: ## [procinfo for procinfo in self.procinfos if procinfo.host == host]:
            if p.label in labels_of_found_processes:
                found_processes.append(p)
                if (self.get_process_status(p) != 0):
                    self.set_process_status(p,0);
            else:
                is_all_ok = False

                if requireSuccess:
                    self.print_log("e",f"Appear to have lost process with label {p.label} on host:{host}")
                    procinfos_to_remove.append(p)

                    mopup_process_base(self,p)

    if not is_all_ok and requireSuccess:
        if self.state() == "running":
            for procinfo in procinfos_to_remove:
                self.procinfos.remove(procinfo)
                self.throw_exception_if_losing_process_violates_requirements(procinfo)

            self.print_log("i","Processes remaining:\n%s"
                           % ("\n".join([procinfo.label for procinfo in self.procinfos])))
        else:
            raise Exception(
                "\nProcess(es) %s died or found in Error state"
                % (", ".join(['"' + procinfo.label + '"' for procinfo in procinfos_to_remove]))
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
            self.name  = name
            self.rank  = rank
            self.port  = port
            self.host  = host
            self.label = label

    launch_procs_test = True

    if launch_procs_test:

        class MockDAQInterface:
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
