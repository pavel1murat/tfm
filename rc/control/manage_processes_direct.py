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

# 2026-02-19-PM #def bootfile_name_to_execname(bootfile_name):
# 2026-02-19-PM #
# 2026-02-19-PM #    if   "BoardReader"    in bootfile_name: execname = "boardreader"
# 2026-02-19-PM #    elif "EventBuilder"   in bootfile_name: execname = "eventbuilder"
# 2026-02-19-PM #    elif "DataLogger"     in bootfile_name: execname = "datalogger"
# 2026-02-19-PM #    elif "Dispatcher"     in bootfile_name: execname = "dispatcher"
# 2026-02-19-PM #    elif "RoutingManager" in bootfile_name: execname = "routing_manager"
# 2026-02-19-PM #    else: assert False
# 2026-02-19-PM #
# 2026-02-19-PM #    return execname


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

#---^--------------------------------------------------------------------------
# assumes type(self)=FarmManager
#------------------------------------------------------------------------------
def launch_procs_on_host(self,host,
                         launch_commands_to_run_on_host,
                         launch_commands_to_run_on_host_background,
                         launch_commands_on_host_to_show_user):
    oname = '"[manage_processes_direct::launch_procs_on_host]'
    
    self.print_log("d", oname+f': executing commands to launch processes on {host}',2)

#------------------------------------------------------------------------------
# if stale processes exist, start from cleaning them up
#------------------------------------------------------------------------------
    grepped_lines    = []
    preexisting_pids = rcu.get_pids("\|".join(
        ["%s.*id:\s\+%s" % (p.execname, p.port) for p in self.procinfos if p.host == host]),
                                    host,grepped_lines)

    TRACE.INFO(f':001:START len(preexisting_pids) on {host}:{len(preexisting_pids)}\n',TRACE_NAME)
    
    if self.attempt_existing_pid_kill and len(preexisting_pids) > 0:
        self.print_log("i", "Found existing processes on %s:%s" % (host,preexisting_pids))
        TRACE.INFO(f'Found existing processes on {host} pids:{preexisting_pids}')

        kill_procs_on_host(self, host, kill_art=True, use_force=True)

#------------------------------------------------------------------------------
# check if cleanup was successful, if not, raise an exception (for now)
#------------------------------------------------------------------------------
        TRACE.INFO(f'Before re-check for existing processes on {host}')
        
        grepped_lines    = []
        preexisting_pids = rcu.get_pids(
            "\|".join( ["%s.*id:\s\+%s" % (p.execname,p.port) for p in self.procinfos if p.host == host]),
            host, grepped_lines)

        TRACE.INFO(f'host:{host} preexisting_pids:{preexisting_pids}',TRACE_NAME)
        
    if (len(preexisting_pids) > 0):
        self.print_log("e",rcu.make_paragraph(
            ("On host %s, found artdaq process(es) already existing which use the ports"
             " TFM was going to use; this may be the result of an improper cleanup from"
             " a prior run: " % host))
        )
        self.print_log("e","\n" + "\n".join(grepped_lines))

        raise Exception(rcu.make_paragraph(
                ("TFM found previously-existing artdaq processes using desired ports;"
                 " see error message above for details"))
        )

    TRACE.INFO(f'host:{host} : starting launch')
#------------------------------------------------------------------------------
# each command already terminated by ampersand
#---v--------------------------------------------------------------------------
    launchcmd = rcu.construct_checked_command(launch_commands_to_run_on_host)
    launchcmd += "; "
    launchcmd += " ".join(launch_commands_to_run_on_host_background)

    if not rcu.host_is_local(host):
        launchcmd = "ssh -f " + host + " '" + launchcmd + "'"

    TRACE.INFO(f': executing on {host} (output will be in {host}:{self.launch_attempt_files[host]}',TRACE_NAME)
    self.print_log("d",'\n'+launchcmd,2)

    proc = subprocess.Popen(launchcmd,executable="/bin/bash",shell=True,
                            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding="utf-8")

    out, _ = proc.communicate()
    status = proc.returncode

    TRACE.INFO(f'after execution on host:{host}: status:{status}',TRACE_NAME)

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
        self.print_log("d","Output from failed command:\n" + out,2)
        raise Exception("ERROR to launch processes on %s; status=%s" % (host,status))
    else:
        self.print_log("d", "...host %s done." % host,2)
#    breakpoint();
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
    TRACE.INFO('--START:',TRACE_NAME)
    
# 2025-05-11 PM    mf_fcl = rcu.generate_messagefacility_fhicl(self)    # writes the file and returns its name...
# 2025-05-11 PM    self.create_setup_fhiclcpp_if_needed()            
# 2025-05-11 PM

    cmds = []
    
    cmds.append("if [[ -z $( command -v fhicl-dump ) ]]; then %s; source %s; fi"
                % (";".join(rcu.get_setup_commands(self.productsdir, self.spackdir)),os.environ["TFM_SETUP_FHICLCPP"]))
    
    cmds.append("if [[ $FHICLCPP_VERSION =~ v4_1[01]|v4_0|v[0123] ]]; then dump_arg=0;else dump_arg=none; fi")
    cmds.append(f'fhicl-dump -l $dump_arg -c {self.mf_template_fn}')

    cmd = "; ".join(cmds)

    TRACE.INFO(f'executing cmd:{cmd}',TRACE_NAME)
    start_time = time.time()
    
    proc = subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding="utf-8")
    proc.wait();

    TRACE.INFO(f'command executed in {time.time()-start_time} sec, rc={proc.returncode}',TRACE_NAME)

    if proc.returncode != 0:
        TRACE.ERROR('\nstatus:{status} when trying to run the following:\n%s\n' % ("\n".join(cmds)),TRACE_NAME)
        
# 2026-05-15 PM        self.print_log("e","STDOUT output: \n%s" % proc.stdout)
# 2026-05-15 PM        self.print_log("e","STDERR output: \n%s" % proc.stderr)
# 2026-05-15 PM
# 2026-05-15 PM        self.print_log("e",rcu.make_paragraph(
# 2026-05-15 PM            ("The FHiCL code designed to control MessageViewer, found in %s, appears to contain "
# 2026-05-15 PM             "one or more syntax errors, or there was a problem running fhicl-dump")
# 2026-05-15 PM            % (rcu.get_mf_template_fn))
# 2026-05-15 PM        )
# 2026-05-15 PM
        raise Exception(f'ERROR expanding {self.mf_template_fn}')
#------------------------------------------------------------------------------
# if the MessageFacility FCL is stored in config dir, then each frontend can copy it
# I think it is a good idea to also store the MF fcl in run_records directory
# however, for now just copy message facility FCL to each remote host - its assumed location is in /tmp/
#------------------------------------------------------------------------------
    TRACE.INFO(f'start copying MF FCL everywhere',TRACE_NAME)
    for host in set([procinfo.host for procinfo in self.procinfos]):
        if not rcu.host_is_local(host):
            # ssh to remote node:/tmp
            cmd    = f"scp -p {self.config_dir}/{self.mf_fcl_fn}  {host}:/tmp/{self.mf_fcl_fn}"
            status = subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).wait()

            if status != 0:
                raise Exception('ERROR in %s executing "%s"' % (launch_procs_base.__name__, cmd))
        else:
            # just copy to /tmp
            shutil.copy2(f'{self.config_dir}/{self.mf_fcl_fn}', f'/tmp/{self.mf_fcl_fn}')

    TRACE.INFO(f'done copying MF FCL everywhere',TRACE_NAME)
#------------------------------------------------------------------------------
# Need to run artdaq processes in the background so they're persistent outside of this function's Popen calls
# Don't want to clobber a pre-existing logfile or clutter the commands via "$?" checks
#---v--------------------------------------------------------------------------
    launch_commands_to_run_on_host            = {} # a dict of pairs {host:list_of_commands}
    launch_commands_to_run_on_host_background = {}
    launch_commands_on_host_to_show_user      = {}

    self.launch_attempt_files                 = {} # pmt logfiles

    for p in self.procinfos:
#------------------------------------------------------------------------------
# mark all processes as busy
#------------------------------------------------------------------------------
        self.set_process_status(p,1)
        
        if p.host == "localhost":
            p.host = socket.gethostname(); ## rcu.get_short_hostname()
#------------------------------------------------------------------------------
# this is a "smart" way to define env vars only once
# a normal one would do it exactly the opposite way :
# - loop over hosts enabled in the configuration,
# - define the env vars,
# - and then loop over the processes enabled on that node...
#------------------------------------------------------------------------------
        if not p.host in launch_commands_to_run_on_host:
#------------------------------------------------------------------------------
# form the name of the PMT log file, assume know the run number
# 'self.launch_attempt_files[p.host]' is the filename then ... oh, well
#------------------------------------------------------------------------------
            fn_format = self.pmt_log_filename_format()
            self.launch_attempt_files[p.host] =  fn_format % (
                self.log_directory,self.run_number, p.host,self.fUser,self.partition(),rcu.date_and_time_filename())

            launch_commands_to_run_on_host           [p.host] = []
            launch_commands_to_run_on_host_background[p.host] = []
            launch_commands_on_host_to_show_user     [p.host] = []

#------------------------------------------------------------------------------
# form commands to be executed to launch ARTDAQ processes
#------------------------------------------------------------------------------

            launch_commands_to_run_on_host[p.host].append("set +C")
            launch_commands_to_run_on_host[p.host].append("echo > %s" % (self.launch_attempt_files[p.host]))
#------------------------------------------------------------------------------
# make sure that MU2E_DAQ_DIR is defined when commands are executed on remote host
# $MIDAS_SERVER_HOST is needed for ARTDAQ processes to connect to ODB
# it is set by the $MU2E_DAQ_DIR/setup_daq.sh
#------------------------------------------------------------------------------
            launch_commands_to_run_on_host[p.host].append("export MIDAS_SERVER_HOST=%s"  % self.midas_server_host);
            launch_commands_to_run_on_host[p.host].append("export MU2E_DAQ_DIR=%s"       % self.mu2e_daq_dir)
            launch_commands_to_run_on_host[p.host] += rcu.get_setup_commands(self.productsdir, self.spackdir,self.launch_attempt_files[p.host])
#------------------------------------------------------------------------------
# make sure the jobs are setting up the same spack environment as the one they are started from
#------------------------------------------------------------------------------
            s = subprocess.run(['spack','env', 'status'],stdout=subprocess.PIPE,encoding='utf-8');
            spack_env = s.stdout.strip().split()[-1];
            TRACE.INFO(f'spack_env:{spack_env}',TRACE_NAME)
            launch_commands_to_run_on_host[p.host].append(f'source {self.daq_setup_script} {spack_env} >> {self.launch_attempt_files[p.host]} 2>&1 ')
#------------------------------------------------------------------------------
# ##TODO: minimize the use of external env vars .. a process gets flattened FHICL file,
# why would it need a path?
#------------------------------------------------------------------------------
            launch_commands_to_run_on_host[p.host].append("export FHICL_FILE_PATH=%s"    % os.environ.get("FHICL_FILE_PATH"))

            launch_commands_to_run_on_host[p.host].append("export ARTDAQ_RUN_NUMBER=%s"  % self.run_number)
            launch_commands_to_run_on_host[p.host].append("export ARTDAQ_LOG_ROOT=%s"    % self.log_directory)
            launch_commands_to_run_on_host[p.host].append("export ARTDAQ_LOG_FHICL=%s"   % self.mf_fcl_fn)
            launch_commands_to_run_on_host[p.host].append("export ARTDAQ_PARTITION_NUMBER=%s"%self.partition())
            launch_commands_to_run_on_host[p.host].append("export ARTDAQ_PORTS_PER_PARTITION=%s"%self.ports_per_partition)
            launch_commands_to_run_on_host[p.host].append("export ARTDAQ_BASE_PORT_NUMBER=%s"%self.base_port_number)

#------------------------------------------------------------------------------
# done with the env vars... why would one need to check availability of the BR?
#------------------------------------------------------------------------------
# 2025-05-09 PM            launch_commands_to_run_on_host[p.host].append("which boardreader >> %s 2>&1 "% self.launch_attempt_files[p.host])  
#------------------------------------------------------------------------------
# Assume if this works, eventbuilder, etc. are also there
# with spack, all executable commands should be available from the $PATH (mostly, $PACK_VIEW/bin)
# cleanup of the shared memory is a good thing
#-----------v------------------------------------------------------------------
            launch_commands_to_run_on_host[p.host].append(
                "%s/bin/mopup_shmem.sh %d --force >> %s 2>&1" % (os.environ["SPACK_VIEW"],self.partition(),self.launch_attempt_files[p.host])
            )

            for command in launch_commands_to_run_on_host[p.host]:
                res = re.search(r"^([^>]*).*%s.*$" % (self.launch_attempt_files[p.host]),command)
                if not res:
                    launch_commands_on_host_to_show_user[p.host].append(command)
                else:
                    launch_commands_on_host_to_show_user[p.host].append(res.group(1))

        prepend         = p.prepend.strip('"')
        base_launch_cmd = (
                        '%s %s -c "id: %s commanderPluginType: xmlrpc rank: %s application_name: %s partition_number: %d"'
                        % ( prepend,
                            p.execname,
                            p.port,
                            p.rank,
                            p.label,
                            self.partition())
                    )
        if p.allowed_processors is not None:
            base_launch_cmd = f'taskset --cpu-list {p.allowed_processors} {base_launch_cmd}'
        elif self.allowed_processors is not None:
            base_launch_cmd = f"taskset --cpu-list {self.allowed_processors} {base_launch_cmd}"

        # base_launch_cmd = "valgrind --tool=callgrind %s" % (base_launch_cmd)
        launch_cmd = f'{base_launch_cmd} >> {self.launch_attempt_files[p.host]} 2>&1 & '

        launch_commands_to_run_on_host_background[p.host].append(launch_cmd)
        launch_commands_on_host_to_show_user     [p.host].append("%s &" % (base_launch_cmd))

#------------------------------------------------------------------------------
# ok, a list of commands is formed 
# execute commands - submit jobs, one [long] ssh command  string per host
#------------------------------------------------------------------------------
    TRACE.INFO('start python-threaded ssh submission of the jobs... beware of GIL',TRACE_NAME)
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

#------------------------------------------------------------------------------
# provision for the next step: 
# generate job submission script for given configuration and save it to the config directory
# also want to copy it to the records directory
# so far, not used
#------------------------------------------------------------------------------
    self.generate_job_submission_script();

    rc = self.check_launch_results(launch_commands_on_host_to_show_user);
    
    TRACE.INFO(f'--END: submission and check finished, rc:{rc}',TRACE_NAME)
    
    return rc 

#------------------------------------------------------------------------------
# generate job submission script and send a command to each node
def launch_procs_base_new(self):
    TRACE.INFO('--START:',TRACE_NAME)

    self.generate_job_submission_script();
#------------------------------------------------------------------------------
# trigger job submission
#------------------------------------------------------------------------------
    cmd_name = 'start_processes'
    for node in self.artdaq.list_of_nodes:
        cmd_odb_path     = f'/Mu2e/Commands/DAQ/Nodes/{node.name}/Artdaq'
        cmd_odb_par_path = cmd_odb_path+'/'+cmd_name
        self.client.odb_set(cmd_odb_path+'/Name',cmd_name);
        self.client.odb_set(cmd_odb_path+'/ParameterPath',cmd_odb_par_path)
        self.client.odb_set(cmd_odb_path+'/logfile',f'{node.name}_artdaq');

        node_conf_odb_path = f'/Mu2e/ActiveRunConfiguration/DAQ/Nodes/{node.name}'
        self.client.odb_set(node_conf_odb_path+'/Status',1);

        timeout_ms = 80000;
        self.client.odb_set(cmd_odb_path+'/timeout_ms',20000);

        self.client.odb_set(cmd_odb_path+'/Finished',0);
        self.client.odb_set(cmd_odb_path+'/Run',1);

#------------------------------------------------------------------------------
# wait for completion reports
#---v--------------------------------------------------------------------------
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

    rc = 0;
    if (n_not_finished > 0):
        rc = -1
        for node in self.artdaq.list_of_nodes:
            if (finished[i] == 0):
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

# 2026-05-15 PM#------------------------------------------------------------------------------
# 2026-05-15 PM# returns the name of the most recent PMT logfile on a given host
# 2026-05-15 PM# filenames are not prepended wit the host name
# 2026-05-15 PM#------------------------------------------------------------------------------
# 2026-05-15 PMdef get_process_manager_log_filename(self, host, run_number):
# 2026-05-15 PM
# 2026-05-15 PM    fn_format = self.pmt_log_filename_format();
# 2026-05-15 PM    pattern   = fn_format % (self.log_directory, run_number, host,self.fUser,self.partition(),"*")
# 2026-05-15 PM    cmd       = "ls -tr1 "+pattern+" | tail -1"
# 2026-05-15 PM
# 2026-05-15 PM    if not rcu.host_is_local(host): cmd = "ssh -f %s '%s'" % (host,cmd)
# 2026-05-15 PM
# 2026-05-15 PM    x  = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
# 2026-05-15 PM    fn = x.stdout.readlines()[0].decode("utf-8").strip()
# 2026-05-15 PM    return fn

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
