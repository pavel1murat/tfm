#!/bin/env python3

import os, sys

sys.path.append(os.environ["TFM_DIR"])

if "TFM_OVERRIDES_FOR_EXPERIMENT_MODULE_DIR" in os.environ:
    sys.path.append(os.environ["TFM_OVERRIDES_FOR_EXPERIMENT_MODULE_DIR"])

import argparse
from   datetime import datetime, timezone
import glob
#------------------------------------------------------------------------------
# debugging printout
#------------------------------------------------------------------------------
from   inspect import currentframe, getframeinfo

import pathlib
import pdb
import random
import re
import shutil
# from   shutil     import copyfile
import signal
import socket
import stat
import string
import subprocess
# from   threading  import RLock
import threading
# from   time       import sleep, time
import time
import traceback

import run_control_state
#------------------------------------------------------------------------------
# for debugging printouts
#------------------------------------------------------------------------------
from inspect      import currentframe, getframeinfo
#------------------------------------------------------------------------------
# home brew
#------------------------------------------------------------------------------
from rc.control                 import subsystem
from rc.control.procinfo        import Procinfo

from rc.io.timeoutclient        import TimeoutServerProxy
from rc.control.component       import Component
from rc.control.save_run_record import save_run_record_base
from rc.control.save_run_record import save_metadata_value_base

disable_bookkeeping = os.environ.get("TFM_DISABLE_BOOKKEEPING");

if (disable_bookkeeping and (disable_bookkeeping != "false")):
    from rc.control.all_functions_noop import bookkeeping_for_fhicl_documents_artdaq_v3_base
else:
    from rc.control.bookkeeping        import bookkeeping_for_fhicl_documents_artdaq_v3_base

import rc.control.utilities as rcu 

# from rc.control.utilities import make_paragraph
# from rc.control.utilities import get_pids
# from rc.control.utilities import host_is_local
# from rc.control.utilities import is_msgviewer_running
# from rc.control.utilities import date_and_time
# from rc.control.utilities import date_and_time_more_precision
# from rc.control.utilities import construct_checked_command
# from rc.control.utilities import reformat_fhicl_documents
# from rc.control.utilities import fhicl_writes_root_file
# from rc.control.utilities import get_setup_commands
# from rc.control.utilities import kill_tail_f
# from rc.control.utilities import obtain_messagefacility_fhicl
# from rc.control.utilities import record_directory_info
# from rc.control.utilities import get_messagefacility_template_filename
# from rc.control.utilities import RaisingThread

try:
    import python_artdaq
    # from   python_artdaq import swig_artdaq

    # Here, "True" means that if python_artdaq is available, it's assumed
    # that artdaq_mfextensions is as well

    messagefacility_fhicl_filename = rcu.obtain_messagefacility_fhicl(True)
    if (not "ARTDAQ_LOG_FHICL" in os.environ):
        #or os.environ["ARTDAQ_LOG_FHICL"] != messagefacility_fhicl_filename

        raise Exception(rcu.make_paragraph(
            ("Although the python_artdaq.swig_artdaq python module is available, "
             "it needs the environment variable ARTDAQ_LOG_FHICL to point to %s"
         ) % (messagefacility_fhicl_filename)))

except ImportError:
    pass  # Users shouldn't need to worry if their installations don't yet have python_artdaq available

from rc.control.config_functions_local import get_boot_info_base
# from rc.control.config_functions_local import listdaqcomps_base

try:
    imp.find_module("daqinterface_overrides_for_experiment")
    from daqinterface_overrides_for_experiment import perform_periodic_action_base
    from daqinterface_overrides_for_experiment import start_datataking_base
    from daqinterface_overrides_for_experiment import stop_datataking_base
    from daqinterface_overrides_for_experiment import do_enable_base
    from daqinterface_overrides_for_experiment import do_disable_base
    from daqinterface_overrides_for_experiment import check_config_base
except:
    from rc.control.all_functions_noop         import perform_periodic_action_base
    from rc.control.all_functions_noop         import start_datataking_base
    from rc.control.all_functions_noop         import stop_datataking_base
    from rc.control.all_functions_noop         import do_enable_base
    from rc.control.all_functions_noop         import do_disable_base
    from rc.control.all_functions_noop         import check_config_base

# try:
#     imp.find_module("daqinterface_overrides_for_experiment")
#     from daqinterface_overrides_for_experiment import start_datataking_base
# except:
#     from rc.control.all_functions_noop         import start_datataking_base

# try:
#     imp.find_module("daqinterface_overrides_for_experiment")
#     from daqinterface_overrides_for_experiment import stop_datataking_base
# except:
#     from rc.control.all_functions_noop         import stop_datataking_base

# try:
#     imp.find_module("daqinterface_overrides_for_experiment")
#     from daqinterface_overrides_for_experiment import do_enable_base
# except:
#     from rc.control.all_functions_noop         import do_enable_base

# try:
#     imp.find_module("daqinterface_overrides_for_experiment")
#     from daqinterface_overrides_for_experiment import do_disable_base
# except:
#     from rc.control.all_functions_noop         import do_disable_base

# try:
#     imp.find_module("daqinterface_overrides_for_experiment")
#     from daqinterface_overrides_for_experiment import check_config_base
# except:
#     from rc.control.all_functions_noop         import check_config_base

process_management_methods = ["direct", "external_run_control"]

if "TFM_PROCESS_MANAGEMENT_METHOD" not in os.environ.keys():
    raise Exception(
        rcu.make_paragraph(
            ("Need to have the TFM_PROCESS_MANAGEMENT_METHOD set so TFM knows "
             "what method to use to control the artdaq processes (%s, etc.)")
            % (",".join(['"' + pmm + '"' for pmm in process_management_methods[:2]]))
        )
    )
else:
    legal_method_found = False
    for pmm in process_management_methods:
        if os.environ["TFM_PROCESS_MANAGEMENT_METHOD"] == pmm:
            legal_method_found = True

    if not legal_method_found:
        raise Exception(
            rcu.make_paragraph(
                'can\'t interpret the current value of TFM_PROCESS_MANAGEMENT_METHOD ("%s"); legal values are: %s'
                % (
                    os.environ["TFM_PROCESS_MANAGEMENT_METHOD"],
                    ",".join(['"' + pmm + '"' for pmm in process_management_methods]),
                )
            )
        )
#------------------------------------------------------------------------------
# supposed to be defined
#------------------------------------------------------------------------------
management_method = os.environ["TFM_PROCESS_MANAGEMENT_METHOD"];

if (management_method == "direct"):
    from rc.control.manage_processes_direct import launch_procs_base
    from rc.control.manage_processes_direct import kill_procs_base
    from rc.control.manage_processes_direct import check_proc_heartbeats_base
    from rc.control.manage_processes_direct import find_process_manager_variable_base
    from rc.control.manage_processes_direct import set_process_manager_default_variables_base

    from rc.control.manage_processes_direct import reset_process_manager_variables_base
    from rc.control.manage_processes_direct import get_process_manager_log_filenames_base

    from rc.control.manage_processes_direct import process_manager_cleanup_base
    from rc.control.manage_processes_direct import get_pid_for_process_base
    from rc.control.manage_processes_direct import process_launch_diagnostics_base
    from rc.control.manage_processes_direct import mopup_process_base
elif (management_method == "external_run_control"):
    from rc.control.all_functions_noop import launch_procs_base
    from rc.control.all_functions_noop import kill_procs_base
    from rc.control.all_functions_noop import check_proc_heartbeats_base
    from rc.control.all_functions_noop import set_process_manager_default_variables_base
    from rc.control.all_functions_noop import reset_process_manager_variables_base
    from rc.control.all_functions_noop import get_process_manager_log_filenames_base
    from rc.control.all_functions_noop import process_manager_cleanup_base
    from rc.control.all_functions_noop import get_pid_for_process_base
    from rc.control.all_functions_noop import process_launch_diagnostics_base
    from rc.control.all_functions_noop import mopup_process_base

    def find_process_manager_variable_base(
        self, line
    ):  # Actually used in get_boot_info() despite external_run_control
        return False


# This is the end of if-elifs of process management methods
if not "TFM_FHICL_DIRECTORY" in os.environ:
    raise Exception(rcu.make_paragraph(
        ("\nThe TFM_FHICL_DIRECTORY environment variable must be defined; "
         "if you wish to use the database rather than the local filesystem "
         "for FHiCL document retrieval, set TFM_FHICL_DIRECTORY to IGNORED"))
    )
elif os.environ["TFM_FHICL_DIRECTORY"] == "IGNORED":
    from rc.control.config_functions_database_v2 import get_config_info_base
    from rc.control.config_functions_database_v2 import put_config_info_base
    from rc.control.config_functions_database_v2 import put_config_info_on_stop_base
    from rc.control.config_functions_database_v2 import listconfigs_base

else:
    from rc.control.config_functions_local import get_config_info_base
    from rc.control.config_functions_local import put_config_info_base
    from rc.control.config_functions_local import put_config_info_on_stop_base
    from rc.control.config_functions_local import listconfigs_base

class FarmManager(Component):
    """
    FarmManager: The intermediary between Run Control, the
    configuration database, and artdaq processes

    """

    def print_log(self, severity, printstr, debuglevel=-999, newline=True):
        printstr = str(printstr)

        dummy, month, day, time, timezone, year = rcu.date_and_time().split()
        formatted_day = "%s-%s-%s" % (day, month, year)

        if self.debug_level >= debuglevel:

            # JCF, Dec-31-2019
            # The swig_artdaq instance by default writes to stdout, so no
            # explicit print call is needed
            if self.use_messagefacility and self.messageviewer_sender is not None:
                if severity == "e":
                    self.messageviewer_sender.write_error(
                        "FarmManager partition %d" % self.partition(),printstr
                    )
                elif severity == "w":
                    self.messageviewer_sender.write_warning(
                        "FarmManager partition %d" % self.partition(),printstr
                    )
                elif severity == "i":
                    self.messageviewer_sender.write_info(
                        "FarmManager partition %d" % self.partition(),printstr)
                elif severity == "d":
                    self.messageviewer_sender.write_debug(
                        "FarmManager partition %d" % self.partition(),printstr)

            else:
                with self.printlock:
                    if self.fake_messagefacility:
                        print(
                            "%%MSG-%s FarmManager %s %s %s"
                            % (severity, formatted_day, time, timezone),
                            flush=True,
                        )
                    if not newline and not self.fake_messagefacility:
                        sys.stdout.write(printstr)
                        sys.stdout.flush()
                    else:
                        print(printstr, flush=True)

                    if self.fake_messagefacility:
                        print("%MSG", flush=True)
#------------------------------------------------------------------------------
# JCF, Dec-16-2016

# The purpose of reset_variables is to reset those members that 
# (A) aren't necessarily persistent to the process (thus excluding the parameters 
#     in the settings file (self.settings_filename()) and 
# (B) won't necessarily be set explicitly during the transitions up from the "stopped" state. 
#
# E.g., you wouldn't want to return to the "stopped" state with self.exception == True 
# and then try a boot-config-start without self.exception being reset to False
####
    def reset_variables(self):

        self.in_recovery               = False
        self.heartbeat_failure         = False
        self.manage_processes          = True
        self.disable_recovery          = False
        self.bootfile_fhicl_overwrites = {}
        self.called_launch_procs       = False
        self.procs_which_already_caused_connection_refused = []
        self.daq_setup_script          = None
        self.debug_level               = 10000
        self.request_address           = None
        self.run_number                = None

        # JCF, Nov-7-2015

        # Now that we're going with a multithreaded (simultaneous)
        # approach to sending transition commands to artdaq processes,
        # when an exception is thrown a thread the main thread needs
        # to know about it somehow - thus this new exception variable

        self.exception                 = False

        self.reset_process_manager_variables()

        # "procinfos" will be an array of Procinfo structures (defined above), 
        # where Procinfo contains all the info FarmManager
        # needs to know about an individual artdaq process: name,
        # host, port, and FHiCL initialization document. Filled
        # through a combination of info in the FarmManager
        # configuration file as well as the components list

        self.procinfos = []

        # "subsystems" is an dictionary of Subsystem structures (defined above),
        # where Subsystem contains all the information FarmManager needs
        # to know about artdaq subsystems: id (dictionary key), source
        # subsystem, destination subsystem.
        # Subsystems are an optional feature that allow users to build complex
        # configurations
        # with multiple request domains and levels of filtering.

        self.subsystems = {}

#------------------------------------------------------------------------------
# want run number to be always printed with 6 digits
####
    def run_record_directory(self):
        return "%s/%06i" % (self.record_directory,self.run_number);

    def metadata_filename(self):
        return "%s/metadata.txt" % (self.run_record_directory());

#------------------------------------------------------------------------------
# format (and location) of the PMT logfile - 
# includes directory, run_number, host, user, partition (in integer), and a timestamp
####
    def pmt_log_filename_format(self):
        return "%s/pmt/pmt_%06i_%s_%s_partition_%02i_%s"

    def boardreader_port_number(self,rank):
        base_port           = int(os.environ["ARTDAQ_BASE_PORT"]);
        ports_per_partition = int(os.environ["ARTDAQ_PORTS_PER_PARTITION"])
        port                = base_port+100 + self.partition()*ports_per_partition+rank
        return port

    def settings_filename(self):
        return os.path.expandvars(self.config_dir+'/settings')

#------------------------------------------------------------------------------
# for now, it is boot.txt, the extension can change, depending on the future 
# initialization mechanism, likely to become '.py'
####
    def boot_filename(self):
        return os.path.expandvars(self.config_dir+'/boot.txt')

#------------------------------------------------------------------------------
# WK 8/31/21
# Startup msgviewer early. check on it later
#---v--------------------------------------------------------------------------
    def start_message_viewer(self):
        self.msgviewer_proc = None  # initialize
        if self.use_messageviewer:
#------------------------------------------------------------------------------
# Use messageviewer if it's available, i.e., if there's one already up 
# or if it's set up via the user-supplied setup script
#-----------v------------------------------------------------------------------
            try:

                if self.have_artdaq_mfextensions() and rcu.is_msgviewer_running():
                    self.print_log("i",rcu.make_paragraph(
                        "An instance of messageviewer already appears to be running; ",
                        "messages will be sent to the existing messageviewer")
                    )

                elif self.have_artdaq_mfextensions():
                    version, qualifiers = self.artdaq_mfextensions_info()

                    self.print_log("i",rcu.make_paragraph(
                            "artdaq_mfextensions %s, %s, appears to be available; "
                            "if windowing is supported on your host you should see the "
                            "messageviewer window pop up momentarily"
                            % (version, qualifiers)
                        ),
                    )
                    self.print_log("i","start_message_viewer:001 debug_level=%i",self.debug_level)
                    self.msgviewer_proc = self.launch_msgviewer()
                    self.print_log("i","start_message_viewer:002 debug_level=%i",self.debug_level)

                else:
                    self.print_log("i",rcu.make_paragraph(
                        "artdaq_mfextensions does not appear to be available; "
                        "unable to launch the messageviewer window. This will not affect"
                        " actual datataking, it just means you'll need to look at the"
                        " logfiles to see artdaq output.")
                    )

            except Exception:
                self.print_log("e", traceback.format_exc())
                self.alert_and_recover("Problem during messageviewer launch stage")
                return

#------------------------------------------------------------------------------
# make sure that the setup script to be executed on each node runs successfully 
####
    def validate_setup_script(self,node):

        ssh_timeout_in_seconds = 30
        starttime              = time.time()
        debug_level            = 3

        self.print_log("i",
                       ("\n%s On randomly selected node (%s), will confirm that the DAQ setup script \n"
                        "%s\ndoesn't return a nonzero value when sourced...")
                       % (rcu.date_and_time(),node, self.daq_setup_script),
                       1,
                       False,
                )

        cmd = "%s ; . %s for_running" % (
            ";".join(rcu.get_setup_commands(self.productsdir, self.spackdir)),
            self.daq_setup_script,
        )

        if not rcu.host_is_local(node):
            cmd = "timeout %d ssh %s '%s'" % (ssh_timeout_in_seconds,node,cmd)

        out = subprocess.Popen(cmd,
                               executable="/bin/bash",
                               shell=True,
                               stderr=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               encoding="utf-8")

        out_comm = out.communicate()

        if out_comm[0] is not None:
            out_stdout = out_comm[0]
            self.print_log("d","\nSTDOUT: \n%s" % (out_stdout),debug_level)

        if out_comm[1] is not None:
            out_stderr = out_comm[1]
            self.print_log("d","STDERR: \n%s"   % (out_stderr),debug_level)
        status = out.returncode

        if status != 0:
            errmsg = ('\nNonzero value (%d) returned in attempt to source script %s on host "%s"'
                      % (status, self.daq_setup_script, node))
            if status != 124:
                errmsg = "%s." % (errmsg)
            else:
                errmsg = (
                    ("%s; returned value suggests that the ssh call to %s timed out. "
                     "Perhaps a lack of public/private ssh keys resulted in ssh asking for a password?")
                    % (errmsg, node)
                )
            self.print_log("e", rcu.make_paragraph(errmsg))
            raise Exception("Problem sourcing %s on %s" % (self.daq_setup_script, node))


        endtime = time.time()
        self.print_log("i", "done (%.1f seconds)." % (endtime - starttime))

#------------------------------------------------------------------------------
# finally, the FarmManager constructor 
# P.Murat: 'config_dir' - a single directory with all configuration and FCL files
#---v--------------------------------------------------------------------------
    def __init__(self,
                 name             = "toycomponent",
                 config_dir       = None          ,
                 rpc_host         = "localhost"   ,
                 control_host     = "localhost"   ,
                 synchronous      = True          ,
#                 rpc_port         = 6659          ,
#                 partition        = 999           ,
                 debug_level      = -1
    ):

        # Initialize Component, the base class of FarmManager

        Component.__init__(self,
                           name         = name,
                           rpc_host     = rpc_host,
                           control_host = control_host,
                           synchronous  = synchronous,
#                           rpc_port     = rpc_port,
                           skip_init    = False)

        self.reset_variables()

        self.fUser            = os.environ.get("USER");
        self.fKeepRunning     = True
        self.config_dir       = config_dir
        self.transfer         = "Autodetect"
#        self._partition       = partition                # assume integer
#        self.rpc_port         = rpc_port

        self.boardreader_priorities           = None
        self.boardreader_priorities_on_config = None
        self.boardreader_priorities_on_start  = None
        self.boardreader_priorities_on_stop   = None

        self.base_dir                         = os.getcwd()

        # JCF, Nov-17-2015

        # fhicl_file_path is a sequence of directory names which will
        # be searched for any FHiCL documents #include'd by the main
        # document used to initialize each artdaq process, but not
        # given with an absolute path in the #include .

        self.fhicl_file_path        = []

        self.__do_boot              = False
        self.__do_shutdown          = False
        self.__do_config            = False
        self.__do_start_running     = False
        self.__do_stop_running      = False
        self.__do_terminate         = False
        self.__do_pause_running     = False
        self.__do_resume_running    = False
        self.__do_recover           = False
#        self.__do_enable          = False
#        self.__do_disable         = False

        self.do_trace_get_boolean   = False
        self.do_trace_set_boolean   = False

        self.messageviewer_sender   = None
        self.use_messageviewer      = True
        self.use_messagefacility    = True
        self.fake_messagefacility   = False
        self._validate_setup_script = 1

        self.printlock              = threading.RLock()

        self.subconfigs_for_run     = []         # not sure what these are 
#------------------------------------------------------------------------------
# move initialization from read_settings()
########
        self.log_directory                       = None
        self.record_directory                    = None
        self.package_hashes_to_save              = []
        self.package_versions                    = {}
        self.productsdir_for_bash_scripts        = None
        self.max_fragment_size_bytes             = None
                                                
        self.boardreader_timeout                 = 30
        self.eventbuilder_timeout                = 30
        self.datalogger_timeout                  = 30
        self.dispatcher_timeout                  = 30
        self.routingmanager_timeout              = 30

        self.advanced_memory_usage               = False
        self.strict_fragment_id_mode             = False
        self.attempt_existing_pid_kill           = False
        self.data_directory_override             = None
        self.max_configurations_to_list          = 1000000
        self.disable_unique_rootfile_labels      = False
        self.disable_private_network_bookkeeping = False
        self.allowed_processors                  = None

        self.max_num_launch_procs_checks         = 20
        self.launch_procs_wait_time              = 40

        self.productsdir                         = None
        self.spackdir                            = None

        # Here, states refers to individual artdaq process states, not the FarmManager state
        self.target_states = {
            "Init"    : "Ready",
            "Start"   : "Running",
            "Pause"   : "Paused",
            "Resume"  : "Running",
            "Stop"    : "Ready",
            "Shutdown": "Stopped",
        }

        self.verbing_to_states = {
            "Init"    : "Configuring",
            "Start"   : "Starting",
            "Pause"   : "Pausing",
            "Resume"  : "Resuming",
            "Stop"    : "Stopping",
            "Shutdown": "Shutting down",
        }
#------------------------------------------------------------------------------
# now, read settings file - should become executing python
########
        try:
            self.read_settings()
        except:
            self.print_log("e", traceback.format_exc())
            self.print_log("e",
                rcu.make_paragraph(
                    "An exception was thrown when trying to read FarmManager settings; "
                    "FarmManager will exit. Look at the messages above, make any necessary "
                    "changes, and restart.\n")
            )
            sys.exit(1)

        if self.use_messagefacility:
            try:
                config_str = "application_name: FarmManager"
                if self.debug_level > 0:
                    config_str += " debug_logging: true"
                
                self.messageviewer_sender = python_artdaq.swig_artdaq(config_str)
            except:
                pass

        if not os.access(self.record_directory, os.W_OK | os.X_OK):
            self.print_log("e",rcu.make_paragraph(
                    ("FarmManager launch failed since it's been determined that you don't have"
                     " write access to the run records directory \"%s\"")
                    % (self.record_directory)))
            sys.exit(1)

        self.print_log("i",'%s: FarmManager in partition %d launched and now in "%s" state, listening on port %d'
                       % (rcu.date_and_time(),self.partition(),self.state(self.name),self.rpc_port())
        )

        print(" >>>> FarmManager.debug_level = ",self.debug_level);
#------------------------------------------------------------------------------
# P.M. if debug_level is defined on the command line, override the config file settings
#------------------------------------------------------------------------------
        if (debug_level >= 0): self.debug_level = debug_level


    def __del__(self):
        rcu.kill_tail_f()
#------------------------------------------------------------------------------
# global actor functions
####
    get_config_info                       = get_config_info_base
    put_config_info                       = put_config_info_base
    put_config_info_on_stop               = put_config_info_on_stop_base
    get_boot_info                         = get_boot_info_base
    #    listdaqcomps                          = listdaqcomps_base
    listconfigs                           = listconfigs_base
    save_run_record                       = save_run_record_base
    save_metadata_value                   = save_metadata_value_base
    start_datataking                      = start_datataking_base
    stop_datataking                       = stop_datataking_base
    bookkeeping_for_fhicl_documents       = bookkeeping_for_fhicl_documents_artdaq_v3_base
    do_enable                             = do_enable_base
    do_disable                            = do_disable_base
    launch_procs                          = launch_procs_base
    kill_procs                            = kill_procs_base
    check_proc_heartbeats                 = check_proc_heartbeats_base
#    softlink_process_manager_logfiles     = softlink_process_manager_logfiles_base
    find_process_manager_variable         = find_process_manager_variable_base
    set_process_manager_default_variables = set_process_manager_default_variables_base
    reset_process_manager_variables       = reset_process_manager_variables_base
    get_process_manager_log_filenames     = get_process_manager_log_filenames_base
    process_manager_cleanup               = process_manager_cleanup_base
    process_launch_diagnostics            = process_launch_diagnostics_base
    mopup_process                         = mopup_process_base
    get_pid_for_process                   = get_pid_for_process_base
    perform_periodic_action               = perform_periodic_action_base
    check_config                          = check_config_base
#------------------------------------------------------------------------------
# The actual transition functions called by Run Control; note these just set booleans 
# which are tested in the runner() function, called periodically by run control
#---v--------------------------------------------------------------------------
    def boot(self):
        self.__do_boot = True

    def shutdown(self):
        self.__do_shutdown = True

    def config(self):
        self.__do_config = True

    def recover(self):
        self.__do_recover = True

    def start_running(self):
        self.__do_start_running = True

    def stop_running(self):
        self.__do_stop_running = True

    def terminate(self):
        self.__do_terminate = True

    def pause_running(self):
        self.__do_pause_running = True

    def resume_running(self):
        self.__do_resume_running = True

#    def enable(self):
#        self.__do_enable = True

#    def disable(self):
#        self.__do_disable = True

#------------------------------------------------------------------------------
# JCF, Jan-2-2020
# See Issue #23792 for more on trace_get and trace_set
# TRACE get
####
    def do_trace_get(self, name=None):
        if name is None: name = self.run_params["name"]

        self.print_log("d",'%s: do_trace_get has been called with name "%s"' % (rcu.date_and_time(), name),3)

#------------------------------------------------------------------------------
# P.Murat: 'p' is the Procinfo structure
########
        def send_trace_get_command(self, p):

            if self.exception: 
                self.print_log("w",'An exception occurred, will not send trace_get to '+p.label)
                return

            try:
                p.lastreturned = p.server.daq.trace_get(name)
            except:
                self.print_log("w","Something went wrong when trace_get was called on %s with name %s"
                               % (p.label, name),
                )
                self.exception = True
                return

            fn = "/tmp/trace_get_%s_%s_partition%d.txt" % (p.label,self.fUser,self.partition());

            with open(fn,"w",) as trace_get_output: 
                trace_get_output.write("\ntrace(s) below are as they appeared at %s:\n\n" % (rcu.date_and_time()))
                trace_get_output.write(p.lastreturned)

        threads = []
        for p in self.procinfos:
            t = rcu.RaisingThread(target=send_trace_get_command, args=(self,p))
            threads.append(t)
            t.start()

        for thread in threads:
            thread.join()
#------------------------------------------------------------------------------
# format all output into one string
########
        output = ""
        for p in self.procinfos:
            fn = "/tmp/trace_get_%s_%s_partition%d.txt" % (p.label,self.fUser,self.partition())
            with open(fn) as inf:
                output += "\n\n%s:\n" % (p.label)
                output += inf.read()

        return output
#------------------------------------------------------------------------------
# TRACE set
####
    def do_trace_set(self, name=None, masktype=None, maskval=None):

        if name is None:
            name     = self.run_params["name"    ]
            masktype = self.run_params["masktype"]
            maskval  = self.run_params["maskval" ]

        self.print_log(
            "i",
            '%s: trace_set has been called with name "%s", masktype "%s", and maskval %s'
            % (rcu.date_and_time(), name, masktype, maskval),
        )

        def send_trace_set_command(self,p):

            if self.exception: 
                self.print_log("w","An exception occurred, will not send trace_set to "+p.label)
                return

            try:
                p.lastreturned = p.server.daq.trace_set(name, masktype, maskval)
            except:
                self.print_log(
                    "w",
                    ("Something went wrong when trace_set was called on %s "
                     "with name == %s, masktype == %s, and maskval == %s")
                    % (p.label, name, masktype, maskval),
                )
                self.exception = True
                return

        threads = []
        for p in self.procinfos:
            t = rcu.RaisingThread(target=send_trace_set_command, args=(self,p))
            threads.append(t)
            t.start()

        for thread in threads:
            thread.join()

        return
#------------------------------------------------------------------------------
# 
####
    def alert_and_recover(self, extrainfo=None):
        self.do_recover()

        alertmsg = ""

        if not extrainfo is None:
            alertmsg = "\n\n" + rcu.make_paragraph('"' + extrainfo + '"')

        alertmsg += "\n" + rcu.make_paragraph(
            ('FarmManager has set the DAQ back in the "Stopped" state; '
             'you may need to scroll above the Recover transition output '
             'to find messages which could help you provide any necessary adjustments.')
        )
        self.print_log("e", alertmsg)
        print
        self.print_log("e",
            rcu.make_paragraph(
                ('Details on how to examine the artdaq process logfiles can be found '
                 'in the "Examining your output" section of the FarmManager manual, '
                 'https://cdcvs.fnal.gov/redmine/projects/artdaq-utilities/wiki/Artdaq-daqinterface#Examining-your-output')
            ),
        )
        print
        return


#------------------------------------------------------------------------------
# at one day, will go away and initialization becomes an execution of a python script
# expand env vars here, not later
####
    def read_settings(self):

        fn = self.settings_filename();

        if not os.path.exists(fn): raise Exception('Unable to find settings file %s'%fn)

        inf = open(fn)

        for line in inf.readlines():
            line = os.path.expandvars(line).strip()
            line = line.split('#')[0];
#------------------------------------------------------------------------------
# skip empty and comment-only lines
# each line is supposed to have a 'key:data' format
# try to order the keywords alphabetically - that simplifies their management
#------------------------------------------------------------------------------
            if (line == '') :                               continue

            words = line.split(':');
            key   = words[0].strip()
            data  = words[1].strip()

            if "advanced_memory_usage" in line or "advanced memory usage" in line:
                res = re.search(r"[Tt]rue",data)
                if res: self.advanced_memory_usage = True
            elif "log_directory" in line or "log directory" in line:
                self.log_directory = line.split()[-1].strip()
            elif "record_directory" in line or "record directory" in line:
                self.record_directory = line.split()[-1].strip()
            elif ("productsdir_for_bash_scripts" in line or "productsdir for bash scripts" in line):
                self.productsdir = line.split()[-1].strip()
            elif (
                "spack_root_for_bash_scripts" in line
                or "spack root for bash scripts" in line
            ):
                self.spackdir = line.split()[-1].strip()
            elif "package_hashes_to_save" in line or "package hashes to save" in line:
                res = re.search(r".*\[(.*)\].*", line)

                if not res:
                    raise Exception(rcu.make_paragraph("Unable to parse package_hashes_to_save from"+fn))

                if res.group(1).strip() == "":
                    continue

                package_hashes_to_save_unprocessed = res.group(1).split(",")

                for ip, package in enumerate(package_hashes_to_save_unprocessed):
                    package = package.replace('"', "")
                    package = package.replace(
                        " ", ""
                    )  # strip() doesn't seem to work here
                    self.package_hashes_to_save.append(package)
            elif "boardreader_timeout" in line or "boardreader timeout" in line:
                self.boardreader_timeout = int(line.split()[-1].strip())
            elif "eventbuilder_timeout" in line or "eventbuilder timeout" in line:
                self.eventbuilder_timeout = int(line.split()[-1].strip())
            elif "datalogger_timeout" in line or "datalogger timeout" in line:
                self.datalogger_timeout = int(line.split()[-1].strip())
            elif "dispatcher_timeout" in line or "dispatcher timeout" in line:
                self.dispatcher_timeout = int(line.split()[-1].strip())
            elif re.search(r"^\s*routing_?manager[ _]timeout", line):
                self.routingmanager_timeout = int(line.split()[-1].strip())
            elif "boardreader_priorities:" in line or "boardreader priorities:" in line:
                res = re.search(r"^\s*boardreader[ _]priorities\s*:\s*(.*)", line)
                if res:
                    self.boardreader_priorities = [
                        regexp.strip() for regexp in res.group(1).split()
                    ]
                else:
                    raise Exception('Incorrectly formatted line "%s" in %s'%(line.strip(),fn))
            elif ("boardreader_priorities_on_config:" in line or "boardreader priorities on config:" in line):
                res = re.search(
                    r"^\s*boardreader[ _]priorities[ _]on[ _]config:\s*(.*)", line
                )
                if res:
                    self.boardreader_priorities_on_config = [
                        regexp.strip() for regexp in res.group(1).split()
                    ]
                    # print self.boardreader_priorities_on_config
                else:
                    raise Exception('Incorrectly formatted line "%s" in %s' % (line.strip(),fn))
            elif (
                "boardreader_priorities_on_start:" in line
                or "boardreader priorities on start:" in line
            ):
                res = re.search(
                    r"^\s*boardreader[ _]priorities[ _]on[ _]start:\s*(.*)", line
                )
                if res:
                    self.boardreader_priorities_on_start = [
                        regexp.strip() for regexp in res.group(1).split()
                    ]
                    # print self.boardreader_priorities_on_start
                else:
                    raise Exception('Incorrectly formatted line "%s" in %s' % (line.strip(),fn))
            elif (
                "boardreader_priorities_on_stop:" in line
                or "boardreader priorities on stop:" in line
            ):
                res = re.search(
                    r"^\s*boardreader[ _]priorities[ _]on[ _]stop:\s*(.*)", line
                )
                if res:
                    self.boardreader_priorities_on_stop = [
                        regexp.strip() for regexp in res.group(1).split()
                    ]
                    # print self.boardreader_priorities_on_stop
                else:
                    raise Exception('Incorrectly formatted line "%s" in %s' % (line.strip(),fn))

            elif "max_fragment_size_bytes" in line or "max fragment size bytes" in line:
                max_fragment_size_bytes_token = line.split()[-1].strip()

                if max_fragment_size_bytes_token[0:2] != "0x":
                    self.max_fragment_size_bytes = int(max_fragment_size_bytes_token)
                else:
                    self.max_fragment_size_bytes = int(
                        max_fragment_size_bytes_token[2:], 16
                    )

                if self.max_fragment_size_bytes % 8 != 0:
                    raise Exception('Value of "max_fragment_size_bytes" in "%s" should be a multiple of 8' % (fn))
            elif (
                "max_configurations_to_list" in line
                or "max configurations to list" in line
            ):
                self.max_configurations_to_list = int(line.split()[-1].strip())
            elif (
                "disable_unique_rootfile_labels" in line
                or "disable unique rootfile labels" in line
            ):
                token = line.split()[-1].strip()
                if "true" in token or "True" in token:
                    self.disable_unique_rootfile_labels = True
                elif "false" in token or "False" in token:
                    self.disable_unique_rootfile_labels = False
                else:
                    raise Exception(
                        'disable_unique_rootfile_labels must be set to either [Tt]rue'
                        ' or [Ff]alse in settings file "%s"' % (fn))
            elif (
                "disable_private_network_bookkeeping" in line
                or "disable private network bookkeeping" in line
            ):
                token = line.split()[-1].strip()
                if "true" in token or "True" in token:
                    self.disable_private_network_bookkeeping = True
                elif "false" in token or "False" in token:
                    self.disable_private_network_bookkeeping = False
                else:
                    raise Exception(
                        'disable_private_network_bookkeeping must be set '
                        'to either [Tt]rue or [Ff]alse in settings file "%s"' % (fn))
            elif "use_messageviewer" in line or "use messageviewer" in line:
                token = line.split()[-1].strip()

                res = re.search(r"[Ff]alse", token)

                if res:
                    self.use_messageviewer = False
            elif "use_messagefacility" in line or "use messagefacility" in line:
                token = line.split()[-1].strip()

                res = re.search(r"[Ff]alse", token)

                if res:
                    self.use_messagefacility = False
            elif "strict_fragment_id_mode" in line or "strict fragment id mode" in line:
                token = line.split()[-1].strip()

                res = re.search(r"[Tt]rue", token)

                if res:
                    self.strict_fragment_id_mode = True
            elif "fake_messagefacility" in line or "fake messagefacility" in line:
                token = line.split()[-1].strip()

                res = re.search(r"[Tt]rue", token)

                if res:
                    self.fake_messagefacility = True
            elif "data_directory_override" in line or "data directory override" in line:
                self.data_directory_override = line.split()[-1].strip()
                if self.data_directory_override[-1] != "/":
                    self.data_directory_override = self.data_directory_override + "/"
            elif "transfer_plugin_to_use" in line or "transfer plugin to use" in line:
                self.transfer = line.split()[-1].strip()
            elif "allowed_processors" in line or "allowed processors" in line:
                self.allowed_processors = line.split()[-1].strip()
            elif "max_launch_checks" in line or "max launch checks" in line:
                self.max_num_launch_procs_checks = int(line.split()[-1].strip())
            elif "launch_procs_wait_time" in line or "launch procs wait time" in line:
                self.launch_procs_wait_time = int(line.split()[-1].strip())
            elif "kill_existing_processes" in line or "kill existing processes" in line:
                token = line.split()[-1].strip()

                res = re.search(r"[Tt]rue", token)

                if res:
                    self.attempt_existing_pid_kill = True

            elif (key == 'validate_setup_script'):
                self._validate_setup_script = int(data)
#------------------------------------------------------------------------------
# end of the input loop
# make sure all needed variables were properly initialized
#------------------------------------------------------------------------------
        missing_vars = []

        # Must wait at least one seconds between checks
        if self.launch_procs_wait_time < self.max_num_launch_procs_checks:
            self.launch_procs_wait_time = self.max_num_launch_procs_checks

        if self.log_directory is None:
            missing_vars.append("log_directory")

        if self.record_directory is None:
            missing_vars.append("record_directory")

        if self.productsdir is None and self.spackdir is None:
            missing_vars.append("productsdir_for_bash_scripts or spack_root_for_bash_scripts")

        if not self.advanced_memory_usage and self.max_fragment_size_bytes is None:
            missing_vars.append("max_fragment_size_bytes")

        if self.advanced_memory_usage and self.max_fragment_size_bytes is not None:
            raise Exception(
                rcu.make_paragraph(
                    ("Since advanced_memory_usage is set to true in the settings file (%s), "
                    "max_fragment_size_bytes must NOT be set (i.e., delete it or comment it out)")
                    % (fn)
                )
            )

        if len(missing_vars) > 0:
            missing_vars_string = ", ".join(missing_vars)
            print
            raise Exception(
                rcu.make_paragraph(
                    "Unable to parse the following variable(s) meant to be set in the "
                    "settings file, %s"
                    % (fn + ": " + missing_vars_string)
                )
            )

        if not self.advanced_memory_usage and not self.max_fragment_size_bytes:
            raise Exception(
                rcu.make_paragraph(
                    "max_fragment_size_bytes isn't set in the settings file, %s; "
                    "this needs to be set since advanced_memory_usage isn't set to true"
                    % fn
                )
            )

        if self.boardreader_priorities is not None and (
            self.boardreader_priorities_on_config is not None
            or self.boardreader_priorities_on_start is not None
            or self.boardreader_priorities_on_stop is not None
        ):
            raise Exception(
                rcu.make_paragraph(
                    ('Both "boardreader_priorities" and at least one of "boardreader_priorities_on_config",'
                     ' "boardreader_priorities_on_start", and "boardreader_priorities_on_stop" '
                     'are defined in %s; this is not allowed. For further information, '
                     'take a look at "The settings file reference" in the FarmManager Manual')
                    % (fn)
                )
            )

        if self.boardreader_priorities is not None:
            self.boardreader_priorities_on_config = self.boardreader_priorities
            self.boardreader_priorities_on_start = self.boardreader_priorities
            self.boardreader_priorities_on_stop = self.boardreader_priorities

    def check_proc_transition(self, target_state):

        is_all_ok = True

        # The following code will give artdaq processes max_retries
        # chances to return "Success", if, rather than
        # procinfo.lastreturned indicating an error condition, it
        # simply appears that it hasn't been assigned its new status
        # yet

        for p in self.procinfos:
            if (p.lastreturned != "Success") and (p.lastreturned != target_state):

                redeemed      = False
                max_retries   = 20
                retry_counter = 0

                while retry_counter < max_retries and (
                    "ARTDAQ PROCESS NOT YET CALLED" in p.lastreturned
                    or "Stopped" in p.lastreturned
                    or "Booted"  in p.lastreturned
                    or "Ready"   in p.lastreturned
                    or "Running" in p.lastreturned
                    or "Paused"  in p.lastreturned
                    or "busy"    in p.lastreturned
                ):
                    retry_counter += 1
                    time.sleep(1)
                    if (p.lastreturned == "Success" or p.lastreturned == target_state):
                        redeemed       = True
                        p.state = target_state

                if redeemed:
                    successmsg = ("After "+str(retry_counter)+" checks, process "+p.label+" at "
                                  + p.host+ ":"+ p.port+' returned "Success"')
                    self.print_log("i", successmsg)
                    continue                                # We're fine, continue on to the next process check

                errmsg = ("Unexpected status message from process "
                          +p.label+" at "+p.host+":"+p.port+': "'+p.lastreturned+'"')

                self.print_log("w", rcu.make_paragraph(errmsg))

                self.print_log("w","\nSee logfile %s for details" % (self.determine_logfilename(p)))

                if (
                    "BoardReader" in p.name
                    and target_state == "Ready"
                    and "with ParameterSet" in p.lastreturned
                ):
                    self.print_log("w",rcu.make_paragraph(
                        ("\nThis is likely because the fragment generator constructor in %s"
                         " threw an exception (see logfile %s for details).")
                        % (p.label, self.determine_logfilename(p))))

                is_all_ok = False

        if not is_all_ok:
            raise Exception("At least one artdaq process failed a transition")

    #------------------------------------------------------------------------------
    #
    #------------------------------------------------------------------------------
    def have_artdaq_mfextensions(self):

        try:
            self.artdaq_mfextensions_booleans
        except:
            self.artdaq_mfextensions_booleans = {}

        try:
            self.artdaq_mfextensions_booleans[self.daq_setup_script]
        except:
            pass
        else:
            return self.artdaq_mfextensions_booleans[self.daq_setup_script]

        cmds  = []
        cmds += rcu.get_setup_commands(self.productsdir, self.spackdir)
        cmds.append(". %s for_running" % (self.daq_setup_script))
        cmds.append('if test -n "$SETUP_ARTDAQ_MFEXTENSIONS" -o -d "$ARTDAQ_MFEXTENSIONS_DIR"; then true; else false; fi')

        checked_cmd = rcu.construct_checked_command(cmds)

        status = subprocess.Popen(
            checked_cmd,
            executable="/bin/bash",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).wait()

        ok = (status == 0);
        self.artdaq_mfextensions_booleans[self.daq_setup_script] = ok;
        return ok
#------------------------------------------------------------------------------
# P.Murat: someone really likes typing... don't go there - see above!
#------------------------------------------------------------------------------
#         if status == 0:
#             self.artdaq_mfextensions_booleans[self.daq_setup_script] = True
#         else:
#             self.artdaq_mfextensions_booleans[self.daq_setup_script] = False
# 
#        return self.artdaq_mfextensions_booleans[self.daq_setup_script]

    def artdaq_mfextensions_info(self):

        assert self.have_artdaq_mfextensions()

        cmds = []
        cmds += rcu.get_setup_commands(self.productsdir, self.spackdir)
        cmds.append(". %s for_running" % (self.daq_setup_script))
        cmds.append(
            ('if [ -n "$SETUP_ARTDAQ_MFEXTENSIONS" ]; then printenv SETUP_ARTDAQ_MFEXTENSIONS; '
             'else echo "artdaq_mfextensions $ARTDAQ_MFEXTENSIONS_VERSION $MRB_QUALS";fi ')
        )

        proc = subprocess.Popen(
            ";".join(cmds),
            executable="/bin/bash",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        proclines = proc.stdout.readlines()

        printenv_line = proclines[-1].decode("utf-8")
        version       = printenv_line.split()[1]
        qualifiers    = printenv_line.split()[-1]

        return (version, qualifiers)

    # WK 8/31/21
    # refactor out launching the message viewer into a function
    # and make that function run in the background
    # return a proc that can be polled.
    def launch_msgviewer(self):
        cmds            = []
        port_to_replace = 30000
        msgviewer_fhicl = "/tmp/msgviewer_partition%d_%s.fcl" % (self.partition(),self.fUser)
        cmds += rcu.get_setup_commands(self.productsdir, self.spackdir)
        cmds.append(". %s for_running" % (self.daq_setup_script))
        cmds.append("which msgviewer")
        cmds.append("cp $ARTDAQ_MFEXTENSIONS_DIR/fcl/msgviewer.fcl %s" % (msgviewer_fhicl))
        cmds.append('res=$( grep -l "port: %d" %s )' % (port_to_replace, msgviewer_fhicl))
        cmds.append("if [[ -n $res ]]; then true ; else false ; fi")
        cmds.append("sed -r -i 's/port: [^\s]+/port: %d/' %s" % (10005 + self.partition() * 1000, msgviewer_fhicl))
        cmds.append("msgviewer -c %s >/dev/null 2>&1 &"       % (msgviewer_fhicl))

        msgviewercmd = rcu.construct_checked_command(cmds)

        proc = subprocess.Popen(msgviewercmd,
                                executable="/bin/bash",
                                shell=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
        )

        return proc

    # JCF, 5/29/15

    # check_proc_exceptions() takes advantage of an artdaq feature
    # developed by Kurt earlier this month whereby if something goes
    # wrong in an artdaq process during running (e.g., a fragment
    # generator's getNext_() function throws an exception) then, when
    # queried, the artdaq process can return an "Error" state, as
    # opposed to the usual DAQ states ("Ready", "Running", etc.)

    # Feb-26-2017

    # Note that "exceptions" in the context of the function name
    # check_proc_exceptions() refers to an exception being thrown
    # within a fragment generator, resulting in the artdaq process
    # returning an "Error" when queried. It's not the same thing as
    # what the self.exception variable denotes, which is that a
    # literal Python exception got thrown at some point.

    def check_proc_exceptions(self):

        if self.exception:
            return

        for procinfo in self.procinfos:

            try:
                procinfo.lastreturned = procinfo.server.daq.status()
            except Exception as ex:

                self.print_log(
                    "w",
                    rcu.make_paragraph(
                        "Exception caught when querying the status of artdaq process %s at %s:%s; exception type == %s, name == %s"
                        % (
                            procinfo.label,
                            procinfo.host,
                            procinfo.port,
                            type(ex),
                            type(ex).__name__,
                        )
                    ),
                )

                if "[Errno 111] Connection refused" in traceback.format_exc():
                    self.print_log(
                        "w",
                        rcu.make_paragraph(
                            ('An "[Errno 111] Connection refused" exception was thrown when attempting '
                            'to query artdaq process %s at %s:%s; this likely means the process no longer '
                             'exists -- try checking logfile %s for details')
                            % (procinfo.label,procinfo.host,procinfo.port,self.determine_logfilename(procinfo))
                        ),
                    )
                    if (
                        procinfo.label
                        in self.procs_which_already_caused_connection_refused
                    ):
                        raise Exception(
                            rcu.make_paragraph('Error: artdaq process "%s" has repeatedly returned "[Errno 111] '
                                           'Connection refused" when queried; this most likely means it\'s died')
                        )
                    else:
                        self.procs_which_already_caused_connection_refused.append(procinfo.label)

                elif "[Errno 113] No route to host" in traceback.format_exc():
                    raise Exception(rcu.make_paragraph(
                        ('Error: an "[Errno 113] No route to host" exception was thrown '
                         'when attempting to query artdaq process %s at %s:%s; '
                         'this likely means there\'s an XML-RPC connection issue between this host and %s')
                        % (procinfo.label,procinfo.host,procinfo.port,procinfo.host))
                    )
                else:
                    raise

                continue
            else:
                procinfo.state = procinfo.lastreturned

            if procinfo.state == "Error":

                errmsg = (
                    ('%s: "Error" state found to have been returned by process %s at %s:%s; '
                     'please check MessageViewer if up and/or the process logfile, %s')
                    % (rcu.date_and_time(),procinfo.label,procinfo.host,procinfo.port,self.determine_logfilename(procinfo))
                )

                print
                self.print_log("e", rcu.make_paragraph(errmsg))
                self.print_log(
                    "i",
                    "\nWill remove %s from the list of processes" % (procinfo.label),
                )
                print
                self.mopup_process(procinfo)
                self.procinfos.remove(procinfo)
                print

                self.throw_exception_if_losing_process_violates_requirements(procinfo)

                self.print_log(
                    "i",
                    "Processes remaining:\n%s"
                    % ("\n".join([procinfo.label for procinfo in self.procinfos])),
                )

#------------------------------------------------------------------------------
#
#---v--------------------------------------------------------------------------
    def init_process_requirements(self):
        self.overriding_process_requirements = []

        def num_processes_required_by_fraction(regexp, fraction):
            absolute_count = 0
            for procinfo in self.procinfos:
                if re.search(regexp, procinfo.label):
                    absolute_count += 1
            return int(round(absolute_count * fraction + 0.499999))  # round up

        if "TFM_PROCESS_REQUIREMENTS_LIST" in os.environ:
            if not os.path.exists(os.environ["TFM_PROCESS_REQUIREMENTS_LIST"]):
                raise Exception(
                    'The file "%s" referred to by the environment variable TFM_PROCESS_REQUIREMENTS_LIST doesn\'t appear to exist'
                    % (os.environ["TFM_PROCESS_REQUIREMENTS_LIST"])
                )

            with open(os.environ["TFM_PROCESS_REQUIREMENTS_LIST"]) as inf:
                for line in inf.readlines():

                    if re.search(r"^\s*$", line) or re.search(r"^\s*#", line):
                        continue

                    possible_comment_location = line.find("#")
                    if possible_comment_location != -1:
                        line = line[:possible_comment_location]

                    res = re.search(r"^\s*(\S+)\s+([\d\.]+)\s+(\d+)\s*$", line)
                    if res:
                        regexp_to_match = res.group(1)
                        fraction_of_matching_required = float(res.group(2))
                        count_of_matching_required = int(res.group(3))

                        if (
                            num_processes_required_by_fraction(
                                regexp_to_match, fraction_of_matching_required
                            )
                            > count_of_matching_required
                        ):
                            strictest_count_of_matching_required = (
                                num_processes_required_by_fraction(
                                    regexp_to_match, fraction_of_matching_required
                                )
                            )
                        else:
                            strictest_count_of_matching_required = (
                                count_of_matching_required
                            )

                        starting_count_of_matching = num_processes_required_by_fraction(
                            regexp_to_match, 1.0
                        )

                        if (
                            starting_count_of_matching
                            < strictest_count_of_matching_required
                        ):
                            raise Exception(
                                rcu.make_paragraph(
                                    ('Logic on line "%s" of %s requires you need at least %d processes with a label'
                                     ' matching "%s", but only %d are requested for the run')
                                    % (line,
                                       os.environ["TFM_PROCESS_REQUIREMENTS_LIST"],
                                       strictest_count_of_matching_required,
                                       regexp_to_match,
                                       starting_count_of_matching)
                                )
                            )

                        self.overriding_process_requirements.append(
                            (
                                regexp_to_match,
                                starting_count_of_matching,
                                strictest_count_of_matching_required,
                                starting_count_of_matching,
                            )
                        )  # Last field will keep track of # of still-alive processes
                    else:
                        raise Exception(
                            ('Error in file %s: line "%s" does not parse as "<process label regexp> '
                             '<process fraction required> <process count required>"')
                            % (os.environ["TFM_PROCESS_REQUIREMENTS_LIST"],line))

#------------------------------------------------------------------------------
# P.Murat: here comes a really long one
#------------------------------------------------------------------------------
    def throw_exception_if_losing_process_violates_requirements(self, procinfo):

        process_matches_requirements_regexp = False  # As in, the requirements found in $TFM_PROCESS_REQUIREMENTS_LIST
        # should it exist

        for i_r, requirement_tuple in enumerate(self.overriding_process_requirements):
            regexp, original_count, minimum_count, current_count = requirement_tuple
            if re.search(regexp, procinfo.label):
                process_matches_requirements_regexp = True
                current_count -= 1
                self.overriding_process_requirements[i_r] = (
                    regexp,
                    original_count,
                    minimum_count,
                    current_count,
                )
                if (current_count < minimum_count):
                    self.print_log("e",rcu.make_paragraph(
                        ('Error: loss of process %s drops the total number of processes '
                         'whose labels match the regular expression "%s" to %d '
                         'out of an original total of %d; this violates the minimum number'
                         ' of %d required in the file "%s"')
                        % ( procinfo.label,
                            regexp,
                            current_count,
                            original_count,
                            minimum_count,
                            os.environ["TFM_PROCESS_REQUIREMENTS_LIST"]))
                    )
                    raise Exception(
                        "Loss of process %s violates at least one of the requirements in %s; scroll up for more details"
                        % (procinfo.label,os.environ["TFM_PROCESS_REQUIREMENTS_LIST"])
                    )

        if not process_matches_requirements_regexp:
            process_description = ""
            if "BoardReader" in procinfo.name:
                process_description = "BoardReader"
            elif rcu.fhicl_writes_root_file(procinfo.fhicl_used):
                process_description = "process that writes data to disk"
            elif "EventBuilder" in procinfo.name:
                is_routingmanager_used = True
                if (
                    len([pi for pi in self.procinfos if "RoutingManager" in pi.name])
                    == 0
                ):
                    is_routingmanager_used = False

                if is_routingmanager_used:
                    eventbuilder_procinfos = [
                        pi for pi in self.procinfos if "EventBuilder" in pi.name
                    ]

                    if len(eventbuilder_procinfos) == 0 or (
                        len(eventbuilder_procinfos) == 1
                        and procinfo.label == eventbuilder_procinfos[0].label
                    ):
                        process_description = "final remaining EventBuilder"
                else:
                    process_description = "EventBuilder in a run with no RoutingManager"

            if process_description != "":
                if "TFM_PROCESS_REQUIREMENTS_LIST" in os.environ:
                    self.print_log("e",rcu.make_paragraph(
                        ("Error: loss of process %s will now end the run, since it's a %s. "
                         "This is the default action because there are no special rules for it in %s. "
                         "To learn how to add rules, see the relevant section of the FarmManager manual, "
                         "https://cdcvs.fnal.gov/redmine/projects/artdaq-utilities/wiki/Defining_which_processes_are_critical_to_a_run")
                        % (procinfo.label,process_description,os.environ["TFM_PROCESS_REQUIREMENTS_LIST"]))
                    )
                else:
                    self.print_log("e",rcu.make_paragraph(
                        ("Error: loss of process %s will now end the run, since it's a %s. "
                         "This is the default action because FarmManager wasn't provided "
                         "with a file overriding its default behavior. To learn how to override, "
                         "see \"%s/docs/process_requirements_list_example\" for an example "
                         "of such a file and also read the relevant section of the FarmManager manual, "
                         "https://cdcvs.fnal.gov/redmine/projects/artdaq-utilities/wiki/Defining_which_processes_are_critical_to_a_run")
                        % (procinfo.label,process_description,os.environ["TFM_DIR"]))
                    )

                raise Exception(rcu.make_paragraph(
                    ("Loss of process %s violates one of FarmManager's default requirements; "
                     "scroll up for more details. You can override this behavior by adding a rule "
                     "to the file referred to by the TFM_PROCESS_REQUIREMENTS_LIST environment variable"
                     % (procinfo.label)))
                )

    def determine_logfilename(self, procinfo):
        loglists = [ self.boardreader_log_filenames,
                     self.eventbuilder_log_filenames,
                     self.datalogger_log_filenames,
                     self.dispatcher_log_filenames,
                     self.routingmanager_log_filenames,
        ]
        all_logfilenames = [
            logfilename for loglist in loglists for logfilename in loglist
        ]
        logfilename_in_list_form = [
            logfilename
            for logfilename in all_logfilenames
            if "/%s-" % (procinfo.label) in logfilename
        ]
        assert len(logfilename_in_list_form) <= 1, rcu.make_paragraph(
            ('Unable to locate logfile for process "%s" out of the following list of candidates: [%s]; '
            'this may be due to incorrect assumptions made by FarmManager about the format '
             'of the logfilenames. Please contact the artdaq-developers@fnal.gov mailing list')
            % (procinfo.label, ", ".join(all_logfilenames))
        )

        if len(logfilename_in_list_form) == 1:
            return logfilename_in_list_form[0]
        else:
            return "(LOGFILE UNDETERMINED)"

#------------------------------------------------------------------------------
# Check that the boot file actually contained the definitions we wanted
#---v--------------------------------------------------------------------------
    def check_boot_info(self):

        undefined_var = None

        if   self.daq_setup_script is None: undefined_var = "daq_setup_script"
        elif self.debug_level      is None: undefined_var = "debug_level"

        if undefined_var :
            raise Exception(rcu.make_paragraph('Error: "%s" undefined in FarmManager boot file' % (undefined_var)))

        if self.debug_level == 0:
            self.print_log("w",rcu.make_paragraph(
                ('"debug level" is set to %d in the boot file, %s; while this isn\'t an error '
                 'due to reasons of backwards compatibility, use of this debug level is highly discouraged')
                % (self.debug_level, self.boot_filename()))
            )

        if not os.path.exists(self.daq_setup_script):
            raise Exception(self.daq_setup_script + " script not found")

        num_requested_routingmanagers = len([p.name for p in self.procinfos if p.name == "RoutingManager" ])

        if num_requested_routingmanagers > len(self.subsystems):
            raise Exception(rcu.make_paragraph(
                ("%d RoutingManager processes defined in the boot file provided; "
                 "you can't have more than the number of subsystems (%d)")
                % (num_requested_routingmanagers, len(self.subsystems)))
            )

        for p in self.procinfos: p.print()

        if len(set([procinfo.label for procinfo in self.procinfos])) < len(self.procinfos):
            raise Exception(rcu.make_paragraph(
                    ("At least one of your desired artdaq processes has a duplicate label; "
                     "please check the boot file to ensure that each process gets a unique label"))
            )

        for ss in self.subsystems:
            dest = self.subsystems[ss].destination
            if dest is not None:
                if (self.subsystems[dest] == None or ss not in self.subsystems[dest].sources):
                    raise Exception(rcu.make_paragraph(
                        ("Inconsistent subsystem configuration detected! Subsystem %s has destination %s, "
                         "but subsystem %s doesn't have %s in its list of sources!")
                        % (ss, dest, dest, ss))
                    )

#------------------------------------------------------------------------------
# log names - this place is important
# at this point the log files are already created and the farm manager 
# just reads the last ones created... Where the log file names are defined ?
#------------------------------------------------------------------------------
    def get_artdaq_log_filenames(self):

        self.boardreader_log_filenames    = []
        self.eventbuilder_log_filenames   = []
        self.datalogger_log_filenames     = []
        self.dispatcher_log_filenames     = []
        self.routingmanager_log_filenames = []

        for host in set([procinfo.host for procinfo in self.procinfos]):

            if host != "localhost": full_hostname = host
            else                  : full_hostname = os.environ["HOSTNAME"]
#------------------------------------------------------------------------------
# processes to be running on 'host'
############
            procinfos_for_host = [ p for p in self.procinfos if p.host == host ]
            cmds      = []
            proctypes = []

            cmds.append('short_hostname=$(hostname -s)')
            for i, p in enumerate(procinfos_for_host):

                output_logdir = "%s/%s-$short_hostname-%s" % (self.log_directory,p.label,p.port)

                cmds.append("filename_%s=$( ls -tr1 %s/%s-$short_hostname-%s*.log | tail -1 )"
                    % (i, output_logdir, p.label, p.port))
                # pdb.set_trace()
                cmds.append(
                    ("if [[ -z $filename_%s ]]; then"
                     " echo No logfile found for process %s on %s after looking in %s >&2 ; exit 1; "
                     "fi") % (i, p.label, p.host, output_logdir)
                )
                cmds.append("timestamp_%s=$( stat -c %%Y $filename_%s )" % (i, i))
                cmds.append(
                    ('if (( $( echo "$timestamp_%s < %f" | bc -l ) )); then '
                     'echo Most recent logfile found in expected output directory for process %s on %s, '
                     '$filename_%s, is too old to be the logfile for the process in this run >&2 ; exit 1; fi')
                    % (i, self.launch_procs_time, p.label, p.host, i))

                cmds.append("echo Logfile for process %s on %s is $filename_%s" % (p.label, p.host, i))
                proctypes.append(p.name)

            cmd = "; ".join(cmds)

            if not rcu.host_is_local(host): cmd = "ssh -f "+host+" '"+cmd+"'"

            num_logfile_checks     = 0
            max_num_logfile_checks = 5

            while True:
                num_logfile_checks += 1
                proc = subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        encoding="utf-8",
                )
                out, err  = proc.communicate()
                proclines = out.strip().split("\n")

                if len([line for line in proclines if re.search(r"\.log$", line)]) == len(proctypes):
                    break  # Success
                else:
                    if num_logfile_checks == max_num_logfile_checks:
                        self.print_log("e",
                                       "\nProblem associating logfiles with the artdaq processes. Output is as follows:",
                        )

                        self.print_log("e",
                            ("\nSTDOUT:\n"
                             "======================================================================\n"
                             "%s\n"
                             "======================================================================\n")
                            % (out))

                        self.print_log("e",
                            ("STDERR:\n"
                             "======================================================================\n"
                             "%s\n"
                             "======================================================================\n")
                            % (err))
                        raise Exception(rcu.make_paragraph(
                            ("Error: there was a problem identifying the logfiles for at least some "
                             "of the artdaq processes. This may be the result of you not having write access "
                             "to the directories where the logfiles are meant to be written. "
                             "Please scroll up to see further output."))
                        )
                    else:
                        time.sleep(2)  # Give the logfiles a bit of time to appear before the next check
#------------------------------------------------------------------------------
# presence of oddly named processes should be checked well before this point
############
            # breakpoint()
            for i_p in range(len(proclines)):
                fn = "%s:%s"%(full_hostname,proclines[i_p].strip().split()[-1])

                if   "BoardReader"    in proctypes[i_p]: self.boardreader_log_filenames.append   (fn)
                elif "EventBuilder"   in proctypes[i_p]: self.eventbuilder_log_filenames.append  (fn)
                elif "DataLogger"     in proctypes[i_p]: self.datalogger_log_filenames.append    (fn)
                elif "Dispatcher"     in proctypes[i_p]: self.dispatcher_log_filenames.append    (fn)
                elif "RoutingManager" in proctypes[i_p]: self.routingmanager_log_filenames.append(fn)
                else:
                    assert False, "Unknown process type found in procinfos list"

        self.print_log("d", "\n", 2)
        for p in self.procinfos:
            self.print_log("d","%-20s %s"%(p.label+":",self.determine_logfilename(p)),2)

        self.print_log("d", "\n", 2)

#------------------------------------------------------------------------------
####
    def fill_package_versions(self, packages):

        cmd             = ""
        needed_packages = []

        for package in packages:
            if package in self.package_versions:
                continue
            else:
                needed_packages.append(package if self.productsdir != None else package.replace("_", "-"))

        if (len(needed_packages) == 0): return

        if "tfm" in packages:
            assert (len(packages) == 1), ("Note to developer: you'll probably need to refactor "
                                          "save_run_records.py if you want to get the version "
                                          "of other packages alongside the version of FarmManager")
                                       
            cmd = "ups active | sed -r -n 's/^artdaq_daqinterface\\s+(\\S+).*/artdaq_daqinterface \\1/p'"
        elif self.productsdir != None:
            cmd = (
                "%s ; . %s; ups active | sed -r -n 's/^(%s)\\s+(\\S+).*/\\1 \\2/p'"
                % (
                    ";".join(rcu.get_setup_commands(self.productsdir, self.spackdir)),
                    self.daq_setup_script,
                    "|".join(needed_packages),
                )
            )
        elif self.spackdir != None:
            cmd = (
                "%s ; . %s; spack find --loaded | sed -r -n 's/^(%s)@(\\S+).*/\\1 \\2/p'" % (
                    ";".join(rcu.get_setup_commands(self.productsdir, self.spackdir)),
                    self.daq_setup_script,
                    "|".join(needed_packages),                
                )
            )

        if cmd != "":
            proc = subprocess.Popen(
                cmd,
                executable="/bin/bash",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                encoding="utf-8",
            )

            out, err = proc.communicate()
            stdoutlines = out.strip().split("\n")
            stderrlines = err.strip().split("\n")

            for line in stderrlines:
                if not line or not line.strip():
                    stderrlines.remove(line)
                elif "type: unsetup: not found" in line:
                    self.print_log("w", line)
                    stderrlines.remove(line)
                elif re.search(
                    r"INFO: mrb v\d_\d\d_\d\d requires cetmodules >= \d\.\d\d\.\d\d to run: attempting to configure\.\.\.v\d_\d\d_\d\d OK",
                    line,
                ):
                    self.print_log("i", line)
                    stderrlines.remove(line)

            if len(stderrlines) > 0:
                raise Exception(
                    'Error in %s: the command "%s" yields output to stderr:\n"%s"'
                    % (
                        self.fill_package_versions.__name__,
                        cmd,
                        "".join(stderrlines),
                    )
                )

            if len(stdoutlines) == 0:
                print(traceback.format_exc())
                raise Exception(
                    'Error in %s: the command "%s" yields no output to stdout'
                    % (self.fill_package_versions.__name__, cmd)
                )

            for line in stdoutlines:
                if re.search(r"^(%s)\s+" % ("|".join(needed_packages)), line):
                    (package, version) = line.split()

                    if not re.search(r"v[0-9]+_[0-9]+_[0-9]+.*", version):
                        raise Exception(
                            rcu.make_paragraph(
                                ('Error in %s: the version of the package "%s" this function has determined, '
                                 '"%s", is not the expected v<int>_<int>_<int>optionalextension format')
                                % (self.fill_package_versions.__name__,package,version)
                            )
                        )
                    # print('package=%s type(package)=%s' % (package,type(package)))
                    self.package_versions[package.replace("-", "_")] = version

        for package in packages:
            if package not in self.package_versions:
                self.print_log("w",
                               'Warning: there was a problem trying to determine the version of package "%s"'
                               % (package)
                )
#------------------------------------------------------------------------------
#
#---v--------------------------------------------------------------------------
    def execute_trace_script(self, transition):

        if "TFM_TRACE_SCRIPT" not in os.environ:
            self.print_log("d",rcu.make_paragraph(
                ("Environment variable TFM_TRACE_SCRIPT not defined; "
                 "will not execute the would-be trace script pointed to by the variable")),3)

            return

        trace_script = os.environ["TFM_TRACE_SCRIPT"]

        if re.search(r"^%s" % (os.environ["TFM_DIR"]), trace_script):
            raise Exception(
                rcu.make_paragraph(
                    ('The trace script referred to by the TFM_TRACE_SCRIPT environment variable, "%s", '
                     'appears to be located inside the FarmManager package itself. '
                     'Please copy it somewhere else before using it, and revert any edits which may have been made to %s.')
                    % (trace_script, trace_script)
                )
            )

        if os.path.exists(trace_script):

            trace_file = ""
            with open(self.daq_setup_script) as inf:
                for line in inf.readlines():
                    res = re.search(r"^\s*export\s+TRACE_FILE=(\S+)", line)
                    if res:
                        trace_file = res.group(1)

            if trace_file == "":
                raise Exception(
                    rcu.make_paragraph(
                        'Exception in %s: unable to determine TRACE_FILE setting from "%s"'
                        % (self.execute_trace_script.__name__, self.daq_setup_script)
                    )
                )

            assert transition == "start" or transition == "stop"

            if transition == "start":
                self.procinfos_orig = list(self.procinfos)  # Deep copy, not a reference

            nodes_for_rgang = {}
            for procinfo in self.procinfos_orig:
                nodes_for_rgang[procinfo.host] = 1

            hosts_for_rgang = set()
            for key in nodes_for_rgang.keys():
                if rcu.host_is_local(key):
                    hosts_for_rgang.add("localhost")
                else:
                    hosts_for_rgang.add(key)

            cmd = '%s %s --run %d --transition %s --node-list="%s"' % (
                trace_script,
                trace_file,
                self.run_number,
                transition,
                " ".join(hosts_for_rgang),
            )
            self.print_log("d", 'Executing "%s"' % (cmd), 2)

            out = subprocess.Popen(
                cmd,
                executable="/bin/bash",
                shell=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding="utf-8",
            )

            out_stdout, out_stderr = out.communicate()

            status = out.returncode

            if status == 0:
                self.print_log("d", "\nSTDOUT from command: \n%s" % (out_stdout), 3)
                self.print_log("d", "\nSTDERR from command: \n%s" % (out_stderr), 3)
            else:
                self.print_log(
                    "e",
                    'Error: execution of "%s" yielded a nonzero return value' % (cmd),
                )
                self.print_log("e", "\nSTDOUT from command: \n%s" % (out_stdout))
                self.print_log("e", "\nSTDERR from command: \n%s" % (out_stderr))
                raise Exception(
                    '"%s" yielded a nonzero return value; scroll up for further info'
                    % (cmd)
                )

        else:  # trace script doesn't exist
            raise Exception(
                'Unable to find trace script referred to by environment variable TFM_TRACE_SCRIPT ("%s")'
                % (os.environ["TFM_TRACE_SCRIPT"])
            )

#------------------------------------------------------------------------------
# "process_command" is the function which will send a transition to a single artdaq process, 
# and be run on its own thread so that transitions to different processes can be sent simultaneously
# WHY ??? - pass it the index of the procinfo struct we want, rather than the actual procinfo struct
# 'p' here is a Procinfo         
#---
    def process_command(self, p, command):

        if self.exception:
            self.print_log("d","self.exception set to true at some point, won't send %s command to %s" 
                           % (command, p.label),2)
            return

        timeout_dict = {
            "BoardReader"   : self.boardreader_timeout,
            "EventBuilder"  : self.eventbuilder_timeout,
            "DataLogger"    : self.datalogger_timeout,
            "Dispatcher"    : self.dispatcher_timeout,
            "RoutingManager": self.routingmanager_timeout,
        }
        timeout = timeout_dict[p.name]

        p.state = self.verbing_to_states[command]

        self.print_log("d","%s: Sending transition to %s" % (rcu.date_and_time_more_precision(), p.label),3)

        try:
            if command == "Init":
                p.lastreturned = p.server.daq.init(p.fhicl_used, timeout)
            elif command == "Start":
                p.lastreturned = p.server.daq.start(self.run_number, timeout)

                # JCF, Jan-8-2019
                # Ensure FarmManager is backwards-compatible with artdaq
                # code which predates Issue #23824

                if ("The start message requires the run number as an argument" in p.lastreturned):
                    p.lastreturned = p.server.daq.start(str(self.run_number))

            elif command == "Pause":
                p.lastreturned = p.server.daq.pause(timeout)
            elif command == "Resume":
                p.lastreturned = p.server.daq.resume(timeout)
            elif command == "Stop":
                p.lastreturned = p.server.daq.stop(timeout)
            elif command == "Shutdown":
                p.lastreturned = p.server.daq.shutdown(timeout)
            else:
                assert False, "Unknown command"

            if "with ParameterSet" in p.lastreturned:
                p.lastreturned = p.lastreturned[0:200]+" // REMAINDER TRUNCATED BY TFM, SEE"
                +self.tmp_run_record+" FOR FULL FHiCL DOCUMENT"

            if (p.lastreturned == "Success") or (p.lastreturned == self.target_states[command]):
                p.state = self.target_states[command]

        except Exception:
            self.exception = True

            if "timeout: timed out" in traceback.format_exc():
                output_message = (
                    ("\n%s: Timeout sending %s transition to artdaq process %s at %s:%s; "
                     "try checking logfile %s for details\n")
                    % (
                        rcu.date_and_time(),
                        command,
                        p.label,
                        p.host,
                        p.port,
                        self.determine_logfilename(p),
                    )
                )
            elif "[Errno 111] Connection refused" in traceback.format_exc():
                output_message = (
                    ("\n%s: artdaq process %s at %s:%s appears to have died (or at least refused "
                     "the connection) when sent the %s transition; try checking logfile %s for details")
                    % (
                        rcu.date_and_time(),
                        p.label,
                        p.host,
                        p.port,
                        command,
                        self.determine_logfilename(p),
                    )
                )
            else:
                self.print_log("e", traceback.format_exc())

                output_message = (
                    ("Exception caught sending %s transition to artdaq process %s at %s:%s; "
                     "try checking logfile %s for details\n")
                    % (
                        command,
                        p.label,
                        p.host,
                        p.port,
                        self.determine_logfilename(p),
                    )
                )

            self.print_log("e", rcu.make_paragraph(output_message))

        return  # From process_command
#------------------------------------------------------------------------------
# JCF, Nov-8-2015

# The core functionality for "do_command" is that it will launch a separate thread 
# for each transition issued to an individual artdaq process; 
# for init, start, and resume it will send the command simultaneously to the aggregators, 
# wait for the threads to join, and then do the same thing for the eventbuilders and then 
# the boardreaders. For stop and pause, it will do this in reverse order of upstream/downstream.
# additional actions besides simply sending transitions to processes and waiting 
# for their response, "do_command" is not meant to be a replacement for "do_initialize",
# "do_start_running" and "do_stop_running" the way it IS meant to be a replacement 
# for "do_pause_running", etc., but rather, is meant to be called in the body of those functions. 
# Thus, for those transitions, some functionality (e.g., announding the transition is underway 
# at the beginning of the function, and calling "complete_state_change" at the end) is not applied.
#---v--------------------------------------------------------------------------
    def do_command(self, command):

        if command != "Start" and command != "Init" and command != "Stop":
            self.print_log("i", "\n%s: %s transition underway" % (rcu.date_and_time(), command.upper()))
#------------------------------------------------------------------------------
# JCF, Nov-8-2015

# In the code below, transition commands are sent simultaneously only to classes 
# of artdaq type. So, e.g., if we're stopping, first we send stop to all the boardreaders,
# next we send stop to all the eventbuilders, and finally we send stop to all the aggregators

# ELF, Jul-17-2020
# I've modified this code to do what John says above, but also in subsystem order
########
        proctypes_in_order = [
            "RoutingManager",
            "Dispatcher"    ,
            "DataLogger"    ,
            "EventBuilder"  ,
            "BoardReader"   ,
        ]

        if (command == "Stop") or (command == "Pause") or (command == "Shutdown"):
            proctypes_in_order.reverse()

        # ELF, Jul-17-2020
        # Subsystems can form a tree from many sources to one final subsystem.
        # Order from leaves to trunk to ensure that on stop, 
        # all of a given subsystem's sources are stopped first.
        subsystems_in_order = []
        while len(subsystems_in_order) < len(self.subsystems):
            for subsystem in self.subsystems:
                sources_copy = list(self.subsystems[subsystem].sources)
                for ordered_ss in subsystems_in_order:
                    if sources_copy.count(ordered_ss):
                        sources_copy.remove(ordered_ss)
                if len(sources_copy) == 0 and not subsystem in subsystems_in_order:
                    subsystems_in_order.append(subsystem)
                    break

        if command != "Stop" and command != "Pause" and command != "Shutdown":
            subsystems_in_order.reverse()

        starttime = time.time()

        self.print_log("i","\nSending %s transition to artdaq processes..." % (command.lower()),1,False)
        self.print_log("d", "", 3)

        proc_starttimes = {}
        proc_endtimes   = {}
        for subsystem in subsystems_in_order:
            for proctype in proctypes_in_order:

                priorities_used = {}

                for p in self.procinfos:
                    if proctype in p.name and p.subsystem == subsystem:
                        priorities_used[p.priority] = p

                priority_rankings = sorted(priorities_used.keys())

                for priority in priority_rankings:
                    proc_threads = {}
                    for p in self.procinfos:
                        if (proctype in p.name and priority == p.priority and p.subsystem == subsystem):
                            t = rcu.RaisingThread(
                                target=self.process_command, args=(p, command)
                            )
                            proc_threads   [p.label] = t
                            proc_starttimes[p.label] = time.time()
                            t.start()

                    for label in proc_threads:
                        proc_threads[label].join()
                        proc_endtimes[label] = time.time()

        if self.exception:
            raise Exception(rcu.make_paragraph("An exception was thrown during the %s transition." % (command)))

        time.sleep(1)

        endtime = time.time()
        self.print_log("i", "done (%.1f seconds).\n" % (endtime - starttime))

        nfailed = len([p for p in self.procinfos if p.lastreturned != "Success" ])

        if ((self.debug_level >= 2) or (nfailed > 0)):
            for p in self.procinfos:
                total_time = "%.1f" % (proc_endtimes[p.label] - proc_starttimes[p.label])
                self.print_log("i","%s at %s:%s, after %s seconds returned string was:\n%s\n"
                               % (p.label,p.host,p.port,total_time,p.lastreturned))
        else:
            slowest_process = ""
            max_time        = 0
            for p in self.procinfos:
                if (proc_endtimes[p.label] - proc_starttimes[p.label] > max_time):
                    max_time        = proc_endtimes[p.label] - proc_starttimes[p.label]
                    slowest_process = p.label

            self.print_log("i","Longest individual transition was %s, which took %.1f seconds."
                           % (slowest_process, max_time))
            self.print_log("i", 'All artdaq processes returned "Success".\n')

        try:
            self.check_proc_transition(self.target_states[command])
        except Exception:
            raise Exception(rcu.make_paragraph(
                ("An exception was thrown during the %s transition as at least one "
                 "of the artdaq processes didn't achieve its desired state.")
                % (command))
            )

        if command != "Init" and command != "Start" and command != "Stop":
            verbing = ""

            if   command == "Pause"   : verbing  =  "pausing"
            elif command == "Resume"  : verbing  =  "resuming"
            elif command == "Shutdown": verbing  =  "shutting"  # P.M. : found a bug here 
            else                      : assert False

            self.complete_state_change(verbing)
            self.print_log("i", "\n%s: %s transition complete" % (rcu.date_and_time(), command.upper()))

        return
#-------^----------------------------------------------------------------------
# not sure why this is needed - in case of failure, it is not always obvious 
# what are the recovery actions to take
#---v--------------------------------------------------------------------------
    def revert_failed_transition(self, failed_action):
        self.revert_state_change(self.name, self.state(self.name))
        self.print_log("e", (traceback.format_exc()))
        self.print_log("e",
            rcu.make_paragraph(
                'An exception was thrown when %s; exception has been caught and system remains in the "%s" state'
                % (failed_action, self.state(self.name))
            ),
        )
        return
#------------------------------------------------------------------------------
# labeled_fhicl_documents is actually a list of tuples of the form
# [ ("label", "fhicl string") ] to be saved to the process indexed
# in self.procinfos by procinfo_index via "add_config_archive_entry"
#---v--------------------------------------------------------------------------
    def archive_documents(self, labeled_fhicl_documents):

        for p in self.procinfos:
            if (("EventBuilder" in p.name) or ("DataLogger" in p.name)):
                if rcu.fhicl_writes_root_file(p.fhicl_used):
                    for label, contents in labeled_fhicl_documents:
                        self.print_log("d","Saving FHiCL for %s to %s" % (label, p.label),3)
                        try:
                            p.lastreturned = p.server.daq.add_config_archive_entry(label,contents)
                        except:
                            self.print_log("d", traceback.format_exc(), 2)
                            self.alert_and_recover(
                                rcu.make_paragraph(
                                    "An exception was thrown when attempting to add archive entry for %s to %s"
                                    % (label, p.label)
                                )
                            )
                            return

                        if p.lastreturned != "Success":
                            raise Exception(
                                rcu.make_paragraph(
                                    "Attempt to add config archive entry for %s to %s was unsuccessful"
                                    % (label, p.label)
                                )
                            )
        return

    def update_archived_metadata(self):
        fn = self.metadata_filename();
        with open(fn) as f:
            contents = f.read()
            contents = re.sub("'", '"', contents)
            contents = re.sub('"', '"', contents)

        self.archive_documents([("metadata", 'contents: "\n%s\n"\n' % (contents))])

    def add_ranks_from_ranksfile(self):

        ranksfile = "/tmp/ranks%d.txt" % self.partition()

        if not os.path.exists(ranksfile):
            raise Exception(
                ("Error: FarmManager run in external_run_control mode expects your "
                 "experiment's run control to provide it with a file named %s")
                % (ranksfile)
            )

        with open(ranksfile) as inf:
            for line in inf.readlines():
                # port and rank are 2nd and 4th entries, and both integers...
                res = re.search(r"^\s*(\S+)\s+(\d+)\s+(\S+)\s+(\d+)", line)
                if res:
                    host  = res.group(1)
                    port  = res.group(2)
                    label = res.group(3)
                    rank  = res.group(4)

                    matched = False
                    for p in self.procinfos:
                        if p.label == label:
                            matched = True
                            if host != p.host or port != p.port:
                                raise Exception(
                                    ("Error: mismatch between values for process %s in FarmManager's "
                                     "procinfo structure and the ranks file, %s")
                                    % (p.label, ranksfile)
                                )
                            p.rank = int(rank)
                    if matched == False:
                        raise Exception(
                            "Error: expected to find a process with label %s in the ranks file %s, but none was found"
                            % (p.label, ranksfile)
                        )
        return # just mark return
#------------------------------------------------------------------------------
# P.Murat: who was the one writing FORTRAN here ??? ... fixed that
#          GOSH, is it true that the priority is encoded in the name? 
#---v--------------------------------------------------------------------------
    def readjust_process_priorities(self, priority_list):

        for p in self.procinfos:
            if "BoardReader" in p.name:
                if priority_list is not None:
                    found_priority_ranking = False
                    for priority, regexp in enumerate(priority_list):
                        if re.search(regexp, p.label):
                            p.priority             = priority
                            found_priority_ranking = True
                            break
                    if not found_priority_ranking:
                        raise Exception(
                            rcu.make_paragraph(
                                ('Error: the process label "%s" didn\'t match with any of the regular expressions'
                                 ' used to rank transition priorities in the settings file, %s')
                                % (p.label,self.settings_filename())
                            )
                        )
                else:
                    p.priority = 999
        return

    def check_run_record_integrity(self):
        inode_basename = ".record_directory_info"
        inode_fullname = "%s/%s" % (self.record_directory, inode_basename)
        if os.path.exists(inode_fullname):
            with open(inode_fullname) as inf:
                if not inf.read().strip() == rcu.record_directory_info(self.record_directory):
                    preface = rcu.make_paragraph(
                        ("Contents of existing %s file and returned value of call to the %s function don't match."
                         " This suggests that since the %s file was created the run records directory has been "
                         "unexpectedly altered. PLEASE INVESTIGATE WHETHER THERE ARE ANY MISSING RUN RECORDS "
                         "AS THIS MAY RESULT IN RUN NUMBER DUPLICATION. Then replace the existing %s file by executing: ")
                        % (inode_fullname,rcu.record_directory_info.__name__,inode_fullname,inode_fullname)
                    )
                    self.print_log(
                        "e",
                        preface
                        + "\n\n"
                        + "cd %s\nrm %s\npython %s/rc/control/utilities.py record_directory_info %s > %s\ncd %s\n"
                        % (
                            self.record_directory,
                            inode_fullname,
                            os.environ["TFM_DIR"],
                            self.record_directory,
                            inode_fullname,
                            os.getcwd(),
                        ),
                    )
                    raise Exception("Problem during run records check; scroll up for details")
        else:
            with open(inode_fullname, "w") as outf:
                outf.write(rcu.record_directory_info(self.record_directory))

            for runrec in glob.glob("%s/*" % (self.record_directory)):
                if re.search(r"/?[0-9]+$", runrec):
                    message = ("A run record (%s) was found in %s. This is unexpected as no %s file was found."
                               " A %s file has just been created, so the next time you try this you won't see this error"
                               " - however, this situation suggests that the run records directory "
                               "has been unexpectedly altered."
                               " PLEASE INVESTIGATE WHETHER THERE ARE ANY MISSING RUN RECORDS"
                               " AS THIS MAY RESULT IN RUN NUMBER DUPLICATION.")
                    raise Exception(rcu.make_paragraph(message % (runrec,self.record_directory,inode_fullname,inode_fullname)))

#------------------------------------------------------------------------------
# Eric Flumerfelt, August 21, 2023: Yuck, package manager dependent stuff...
#---v--------------------------------------------------------------------------
    def create_setup_fhiclcpp_if_needed(self):
        if not os.path.exists(os.environ["TFM_SETUP_FHICLCPP"]):
            self.print_log("w",
                           rcu.make_paragraph(
                            ('File "%s", needed for formatting FHiCL configurations, does not appear to exist; '
                             'will attempt to auto-generate one...') % (os.environ["TFM_SETUP_FHICLCPP"])
                           ),
            )
            with open(os.environ["TFM_SETUP_FHICLCPP"], "w") as outf:
                outf.write("\n".join(rcu.get_setup_commands(self.productsdir, self.spackdir)))
                outf.write("\n\n")
                if self.productsdir != None:
                    lines = subprocess.Popen(
                        '%s;ups list -aK+ fhiclcpp | sort -n'
                        % (";".join(rcu.get_setup_commands(self.productsdir, self.spackdir))),
                        executable="/bin/bash",
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                    ).stdout.readlines()
                    if len(lines) > 0:
                        fhiclcpp_to_setup_line = lines[-1].decode("utf-8")
                    else:
                        os.unlink(os.environ["TFM_SETUP_FHICLCPP"])
                        raise Exception(
                            rcu.make_paragraph(
                                'Unable to find fhiclcpp ups product in products directory "%s" provided in the FarmManager settings file, "%s"'
                                % (self.productsdir, self.settings_filename())
                            )
                        )

                    outf.write(
                        "setup %s %s -q %s\n"
                        % (
                            fhiclcpp_to_setup_line.split()[0],
                            fhiclcpp_to_setup_line.split()[1],
                            fhiclcpp_to_setup_line.split()[3],
                        )
                    )
                elif self.spackdir != None:
                    outf.write("spack load --first fhicl-cpp")

            if os.path.exists(os.environ["TFM_SETUP_FHICLCPP"]):
                self.print_log(
                    "w",
                    '"%s" has been auto-generated; you may want to check to see that it correctly sets up the fhiclcpp package...'
                    % (os.environ["TFM_SETUP_FHICLCPP"]),
                )
            else:
                raise Exception(
                    rcu.make_paragraph(
                        'Error: was unable to find or create a file "%s"'
                        % (os.environ["TFM_SETUP_FHICLCPP"])
                    )
                )
#------------------------------------------------------------------------------
# P.Murat: factor out fhiclcpp stuff
#---v--------------------------------------------------------------------------
    def do_fhiclcpp_stuff(self):

        self.create_setup_fhiclcpp_if_needed()
        # breakpoint()
        rcu.obtain_messagefacility_fhicl(self.have_artdaq_mfextensions())

        self.print_log("i", "\n%s: BOOT transition 008 Pasha: after messagefacility_fhicl\n" % (rcu.date_and_time()))

        cmds = []

        cmds.append("if [[ -z $( command -v fhicl-dump ) ]]; then %s; source %s; fi"
            % (";".join(rcu.get_setup_commands(self.productsdir, self.spackdir)), 
               os.environ["TFM_SETUP_FHICLCPP"])
        )
        cmds.append("if [[ $FHICLCPP_VERSION =~ v4_1[01]|v4_0|v[0123] ]]; then dump_arg=0;else dump_arg=none; fi")
        cmds.append("fhicl-dump -l $dump_arg -c %s" % (rcu.get_messagefacility_template_filename()))

        proc = subprocess.Popen("; ".join(cmds),
                                executable="/bin/bash",
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                encoding="utf-8")

        self.print_log("i", "\n%s: BOOT transition 009 Pasha: after fhicl-dump\n" % (rcu.date_and_time()))
        out, err = proc.communicate()
        status   = proc.returncode

        if status != 0:
            self.print_log("e","\nNonzero return value (%d) resulted when trying to run the following:\n%s\n"
                           % (status, "\n".join(cmds)))
            self.print_log("e","STDOUT output: \n%s" % (out))
            self.print_log("e","STDERR output: \n%s" % (err))
            self.print_log("e",
                rcu.make_paragraph(
                    ("The FHiCL code designed to control MessageViewer, found in %s, appears to contain"
                     " one or more syntax errors (Or there was a problem running fhicl-dump)")
                    % (rcu.get_messagefacility_template_filename())
                ),
            )

            raise Exception(
                ("The FHiCL code designed to control MessageViewer, found in %s, appears to contain"
                 " one or more syntax errors (Or there was a problem running fhicl-dump)")
                % (rcu.get_messagefacility_template_filename())
            )
        return

#------------------------------------------------------------------------------
# P.Murat: in order to structure the code, make check_launch_results a separate function
#---v--------------------------------------------------------------------------
    def check_launch_results(self):

        num_launch_procs_checks = 0

        while True:
            num_launch_procs_checks += 1

            self.print_log("i","Checking that processes are up (check %d of a max of %d checks)..."
                % (num_launch_procs_checks, self.max_num_launch_procs_checks),
                1,False)

            # "False" here means "don't consider it an error if all
            # processes aren't found"

            found_processes = self.check_proc_heartbeats(False)
            self.print_log(
                "i",
                "found %d of %d processes."
                % (len(found_processes), len(self.procinfos)),
            )

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
                                     ' in your boot file set to 4. If that doesn\'t help, you can directly recreate'
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
# P.Murat: create_time_server_proxy - make it a separate function
#---v--------------------------------------------------------------------------
    def create_time_server_proxy(self):
        starttime = time.time()
        for p in self.procinfos:

            if   "BoardReader"    in p.name: timeout = self.boardreader_timeout
            elif "EventBuilder"   in p.name: timeout = self.eventbuilder_timeout
            elif "RoutingManager" in p.name: timeout = self.routingmanager_timeout
            elif "DataLogger"     in p.name: timeout = self.datalogger_timeout
            elif "Dispatcher"     in p.name: timeout = self.dispatcher_timeout

            try:
                p.server = TimeoutServerProxy(p.socketstring, timeout)
            except Exception:
                self.print_log("e", traceback.format_exc())
                self.alert_and_recover('Problem creating server with socket "%s"' % p.socketstring)
                return -1
#------------------------------------------------------------------------------
#       everything is fine
#-------v----------------------------------------------------------------------
        endtime = time.time()
        self.print_log("i", "create_time_server_proxy done (%.1f seconds)." % (endtime - starttime))
        return 0

#------------------------------------------------------------------------------
#       get_lognames : returns 0 in case of success, -1 otherwise
#---v--------------------------------------------------------------------------
    def get_lognames(self):
        starttime = time.time()
        self.print_log("i","\n%s Determining logfiles associated with the artdaq processes..." 
                       % rcu.date_and_time(),1,False)
        try:
            self.process_manager_log_filenames = self.get_process_manager_log_filenames()
            self.get_artdaq_log_filenames()

        except Exception:
            self.print_log("e", traceback.format_exc())
            self.alert_and_recover("Unable to find logfiles for at least some of the artdaq processes")
            return -1;

        endtime = time.time()
        self.print_log("i", "get_lognames done (%.1f seconds)." % (endtime - starttime))
        return 0;  # end of get_lognames

#------------------------------------------------------------------------------
# P.Murat: make_logfile_dirs is a well-defined action - make it a separate function
#          pmt is the only one left ..
#---v--------------------------------------------------------------------------
    def make_logfile_dirs(self):
        logdir_commands_to_run_on_host = []
        permissions                    = "0775"
        logdir_commands_to_run_on_host.append("mkdir -p -m %s %s" % (permissions, self.log_directory))

        for subdir in [
            "pmt",
##            "boardreader",
##            "eventbuilder",
##            "dispatcher",
##            "datalogger",
##            "routingmanager",
        ]:
            logdir_commands_to_run_on_host.append(
                "mkdir -p -m %s %s/%s" % (permissions, self.log_directory, subdir)
            )

        for host in set([p.host for p in self.procinfos]):
            logdircmd = rcu.construct_checked_command(logdir_commands_to_run_on_host)

            if not rcu.host_is_local(host):
                logdircmd = "timeout %d ssh -f %s '%s'" % (ssh_timeout_in_seconds,host,logdircmd)

            self.print_log("i", "\n%s: BOOT transition 004 Pasha: executing %s\n" % (rcu.date_and_time(),logdircmd))
            proc = subprocess.Popen(
                logdircmd,
                executable="/bin/bash",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
            )
            self.print_log("i", "\n%s: BOOT transition underway 006 Pasha done with mkdirs\n" % (rcu.date_and_time()))

            out, err = proc.communicate()
            status   = proc.returncode

            if status != 0:

                self.print_log(
                    "e",
                    "\nNonzero return value (%d) resulted when trying to run the following on host %s:\n%s\n"
                    % (status, host, "\n".join(logdir_commands_to_run_on_host)),
                )
                self.print_log("e","STDOUT output: \n%s" % (out))
                self.print_log("e","STDERR output: \n%s" % (err),
                )
                self.print_log(
                    "e",
                    rcu.make_paragraph(
                        ("Returned value of %d suggests that the ssh call to %s timed out. "
                         "Perhaps a lack of public/private ssh keys resulted in ssh asking for a password?")
                        % (status, host)
                    ),
                )
                raise Exception(
                    ("Problem running mkdir -p for the needed logfile directories on %s; "
                     "this is likely due either to an ssh issue or a directory permissions issue")
                    % (host)
                )
        return  # marks end of function

#------------------------------------------------------------------------------
# starting from this point, perform run-dependent configuration
# look at the FCL files - they need to be looked at before the processes are launched
# See Issue #20803.  Idea is that, e.g., component01.fcl and component01_hw_cfg.fcl 
# refer to the same thing
#---v--------------------------------------------------------------------------
    def check_hw_fcls(self):

        starttime = time.time()
        self.print_log("i", "\nObtaining FHiCL documents...", 1, False)

        try:
            tmpdir_for_fhicl, self.fhicl_file_path = self.get_config_info()
            assert "/tmp" == tmpdir_for_fhicl[:4]
        except:
            self.revert_failed_transition("calling get_config_info()")
            return -1
            
        rootfile_cntr = 0
        fn_dictionary = {}  # If we find a repeated *.fcl file, that's an error
        
        for dummy, dummy, filenames in os.walk(tmpdir_for_fhicl):
            for filename in filenames:
                if filename.endswith(".fcl"):
                    if filename not in fn_dictionary:
                        fn_dictionary[filename] = True
        
                        if filename.endswith("_hw_cfg.fcl"):
                            fn_dictionary[filename.replace("_hw_cfg.fcl", ".fcl")] = True
                        else:
                            fn_dictionary[filename.replace(".fcl", "_hw_cfg.fcl")] = True
                    else:
                        raise Exception(
                            rcu.make_paragraph(
                                ('Error: filename "%s" found more than once given the set'
                                ' of requested subconfigurations "%s" (see %s)')
                                % (
                                    filename,
                                    " ".join(self.subconfigs_for_run),
                                    tmpdir_for_fhicl,
                                )
                            )
                        )
#------------------------------------------------------------------------------
# it looks that here we're checking availability of the FCL files for the processes 
# which are already running ? is the idea that one would reupload the FCL files? 
#-------v------------------------------------------------------------------------------
        for p in self.procinfos:
            matching_filenames = ["%s.fcl" % p.label]

            if ("BoardReader" in p.name):  # For backwards compatibility (see Issue #20803)
                matching_filenames.append("%s_hw_cfg.fcl" % p.label)

            found_fhicl = False
            for dirname, dummy, filenames in os.walk(tmpdir_for_fhicl):
                for filename in filenames:
                    if filename in matching_filenames:
                        fcl = "%s/%s" % (dirname, filename)
                        found_fhicl = True

            if not found_fhicl:
                self.print_log("e",rcu.make_paragraph(
                    'Unable to find a FHiCL document for %s in configuration "%s"; '
                    % (p.label," ".join(self.subconfigs_for_run),p.label))
                )
                self.revert_failed_transition("looking for all needed FHiCL documents")
                return

            try:
                p.ffp = self.fhicl_file_path
                p.update_fhicl(fcl)
            except Exception:
                self.print_log("e", traceback.format_exc())
                self.alert_and_recover("An exception was thrown when creating the process "
                                       "FHiCL documents; see traceback above for more info")
                return

            if not self.disable_unique_rootfile_labels and ("EventBuilder" in p.name or "DataLogger" in p.name):
                fhicl_before_sub     = p.fhicl_used
                rootfile_cntr_prefix = "dl"
                p.fhicl_used         = re.sub(
                    r"(\n\s*[^#\s].*)\.root",
                    r"\1" + "_dl" + str(rootfile_cntr + 1) + ".root",
                    p.fhicl_used,
                )

                if p.fhicl_used != fhicl_before_sub:
                    rootfile_cntr += 1

        endtime = time.time()
        self.print_log("i", "done (%.1f seconds)." % (endtime - starttime))
        self.print_log("i", "\n%s: CONFIG transition 002 Pasha" % (rcu.date_and_time()))

        for p in self.procinfos:
            assert not p.fhicl is None and not p.fhicl_used is None

        assert "/tmp" == tmpdir_for_fhicl[:4] and len(tmpdir_for_fhicl) > 4
        shutil.rmtree(tmpdir_for_fhicl)

        return 0  # end of function

#------------------------------------------------------------------------------
# do_boot(), do_config(), do_start_running(), etc., are the functions 
# which get called by the runner() function when a transition is requested
# boot just once, at the initialization stage, 
# everything else goes into config
####
    def do_boot(self):
#------------------------------------------------------------------------------
# P.Murat: why a nested function? - hiding the name
#-------v----------------------------------------------------------------------
        def revert_failed_boot(failed_action):
            self.reset_variables()
            self.revert_failed_transition(failed_action)

        self.print_log("i", "%s: BOOT transition underway" % (rcu.date_and_time()))
        self.print_log("i", "%s: BOOT, self.debug_level=%i" % (rcu.date_and_time(),self.debug_level))

        self.reset_variables()
        self.print_log("i", "%s: BOOT transition 0001 after reset_variables debug_level:%i" 
                       % (rcu.date_and_time(),self.debug_level))

        self.fState = run_control_state.transition("init");
        self.fState.set_completed(0);

        os.chdir(self.base_dir)
        boot_fn = self.boot_filename();

        self.print_log("i", "%s: BOOT transition 0002 boot_fn: %s, debug_level:%i" 
                       % (rcu.date_and_time(),boot_fn,self.debug_level))

        if not os.path.exists(boot_fn):
            raise Exception('ERROR: boot file %s does not exist' % boot_fn)
#------------------------------------------------------------------------------
# P.Murat : it looks that a boot file name could have a .fcl extension... wow!
#           we're not using that ....
#-------v----------------------------------------------------------------------
        dummy, file_extension = os.path.splitext(boot_fn)

        if file_extension == ".fcl":
            try:
                self.create_setup_fhiclcpp_if_needed()
                self.print_log("i", "%s: BOOT transition 00021 debug_level:%i" % (rcu.date_and_time(),self.debug_level))
            except:
                raise

            self.boot_filename = "/tmp/boot_%s_partition%d.txt" % (self.fUser,self.partition())

            if os.path.exists(self.boot_filename):
                os.unlink(self.boot_filename)

            assert os.path.exists("%s/bin/defhiclize_boot_file.sh" % (self.fUser))

            cmd    = "%s/bin/defhiclize_boot_file.sh %s > %s" % (os.environ["TFM_DIR"],boot_filename,self.boot_filename)
            status = subprocess.Popen(cmd,executable="/bin/bash",shell=True,
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL).wait()
            if status != 0:
                raise Exception('Error: the command "%s" returned nonzero' % cmd)
#------------------------------------------------------------------------------
# P.Murat: here the boot.txt file is being read and parsed
#-------v----------------------------------------------------------------------
        try:
            self.print_log("i", "%s: BOOT transition 00022 debug_level:%i" % (rcu.date_and_time(),self.debug_level))
            self.get_boot_info(self.boot_filename())
            self.print_log("i", "%s: BOOT transition 0003 debug_level:%i" % (rcu.date_and_time(),self.debug_level))
            self.check_boot_info()
            self.print_log("i", "%s: BOOT transition 0004 debug_level:%i" % (rcu.date_and_time(),self.debug_level))
        except Exception:
            revert_failed_boot('when trying to read the TFM boot file "%s"' % (self.boot_filename()))
            return

#------------------------------------------------------------------------------
# See the Procinfo.__lt__ function for details on sorting
#-------v----------------------------------------------------------------------
        self.procinfos.sort()
        self.print_log("i", "%s: BOOT transition 0005 debug_level:%i" % (rcu.date_and_time(),self.debug_level))

        for ss in sorted(self.subsystems):

            subsystem_line = "\nSubsystem %s: " % (ss)

            if len(self.subsystems[ss].sources) == 0:
                subsystem_line += "subsystem source(s): None"
            else:
                subsystem_line += "subsystem source(s): %s" % (
                    [", ".join(self.subsystems[ss].sources)] 
                )

            if self.subsystems[ss].destination is None:
                subsystem_line += ", subsystem destination: None"
            else:
                subsystem_line += ", subsystem destination: %s" % (
                    self.subsystems[ss].destination
                )

            self.print_log("d", subsystem_line + "\n", 2)

        for ss in sorted(self.subsystems):
            for p in self.procinfos:
                if p.subsystem == ss:
                    self.print_log("d","%-20s at %s:%s, part of subsystem %s, has rank %d" 
                                   % (p.label,p.host,p.port,p.subsystem,p.rank),2)
#------------------------------------------------------------------------------
# -- P.Murat: this also need to be done just once (in case it is needed at all :) )
#-------v----------------------------------------------------------------------
        self.print_log("i", "%s: BOOT transition 001 Pasha: start msg viewer" % (rcu.date_and_time()))
        self.print_log("i", "%s: BOOT transition 001 debug_level:%i" % (rcu.date_and_time(),self.debug_level))
        self.start_message_viewer()
        self.print_log("i", "%s: BOOT transition 002 Pasha: done with msg viewer" % (rcu.date_and_time()))
        self.print_log("i", "%s: BOOT transition 002 debug_level:%i" % (rcu.date_and_time(),self.debug_level))

        self.fState.set_completed(30);
#------------------------------------------------------------------------------
# here we come if not self.manage_processes - is the sequence important ?
#-------v----------------------------------------------------------------------
        if self.msgviewer_proc is not None:
            # now wait/check status from msgviewer
            if self.msgviewer_proc.wait() != 0:
                self.alert_and_recover(
                    ('Status error raised in msgviewer call within subprocess.Popen; '
                     'tried the following commands: \n\n"%s"') % " ;\n".join(cmds)
                )
                return
#------------------------------------------------------------------------------
# JCF, Oct-18-2017

# After a discussion with Ron about how trace commands need to be run on the host 
# that the artdaq process is running on, we agreed it would be a good idea to do a pass 
# in which the setup script was sourced on all hosts which artdaq processes ran on 
# in case the setup script contained trace commands...
#
# JCF, Jan-17-2018
#
# It turns out that sourcing the setup script on hosts for runs which use lots of nodes 
# takes an onerously long time. What we'll do now is source the script on just ONE node, 
# to make sure it's not broken. Note that this means you may need to perform a second run 
# after adding TRACE functionality to your setup script; 
# while a cost, the benefit here seems to outweight the cost.
#
# -- P.Murat: validation of the setup script needs to be done just once
########
        if self.manage_processes:
            hosts        = [procinfo.host for procinfo in self.procinfos]
            random_host  = random.choice(hosts)

            if (self._validate_setup_script):
                self.validate_setup_script(random_host)

            self.print_log("i", "%s: BOOT transition 003 Pasha: done checking setup script" % (rcu.date_and_time()))
            self.print_log("i", "%s: BOOT transition 003 debug_level:%i" % (rcu.date_and_time(),self.debug_level))
#------------------------------------------------------------------------------
# creating directories for log files - the names don't change,
# -- enought to do just once
#-----------v------------------------------------------------------------------
            self.make_logfile_dirs();
            self.fState.set_completed(50);
#------------------------------------------------------------------------------
# done creating directories for logfiles,
# deal with message facility. 
# -- also OK to do just once
#-----------v------------------------------------------------------------------
            self.print_log("i", "%s: BOOT transition 004 Pasha: before init_process_requirements\n" % (rcu.date_and_time()))
            self.print_log("i", "%s: BOOT transition 004 debug_level:%i" % (rcu.date_and_time(),self.debug_level))
            self.init_process_requirements()
            self.fState.set_completed(60);
#------------------------------------------------------------------------------
# now do something with fhiclcpp - need to figure out what it is. OK to do just once
#-----------v------------------------------------------------------------------
            self.do_fhiclcpp_stuff();
            self.fState.set_completed(90);
#------------------------------------------------------------------------------
#  former end of DO_BOOT
#-------v-----------------------------------------------------------------------
        self.complete_state_change("booting")
        self.print_log("i", "%s: BOOT transition complete" % (rcu.date_and_time()))
        self.print_log("i", "%s: BOOT transition complete debug_level:%i" % (rcu.date_and_time(),self.debug_level))
#------------------------------------------------------------------------------
# to preserve formal logic: transition completes, then the state changes
#-------v----------------------------------------------------------------------
        self.fState.set_completed(100);
        time.sleep(1);
        self.fState = run_control_state.state("stopped")
        return

#------------------------------------------------------------------------------
# CONFIG transition : 1) at this point the run number is known, don't need to pass
#---v--------------------------------------------------------------------------
    def do_config(self, subconfigs_for_run=[], run_number=None):
        # breakpoint()

        self.fState = run_control_state.transition("configure")

        self.print_log("i", "%s: CONFIG transition underway" % (rcu.date_and_time()))
        os.chdir(self.base_dir)
#------------------------------------------------------------------------------
# check subconfigs for this run - what they are? 
# could this be done before launching the jobs ?
# last segment of the self.config_dir is the config name
#-------v----------------------------------------------------------------------
        if subconfigs_for_run: 
            self.subconfigs_for_run = subconfigs_for_run
        else:
            self.subconfigs_for_run.append(os.path.basename(self.config_dir))

        self.subconfigs_for_run.sort()

        self.print_log("d", "Config name: %s" % (" ".join(self.subconfigs_for_run)),1)

        if not run_number: self.run_number = self.run_params["run_number"]
        else             : self.run_number = run_number
#------------------------------------------------------------------------------
# starting from this point, perform run-dependent configuration
# look at the FCL files - they need to be looked at before the processes are launched
# See Issue #20803.  Idea is that, e.g., component01.fcl and component01_hw_cfg.fcl 
# refer to the same thing P.Murat: checks in check_hw_fcl look like nonsense - it costs nothing to keel the fcl files unique
#-------v------------------------------------------------------------------------------
        self.print_log("i", "\n%s: CONFIG transition run_number:%d 001 Pasha" 
                       % (rcu.date_and_time(),self.run_number))

        rc = self.check_hw_fcls();
        if (rc != 0): return 

        starttime = time.time()
        self.print_log("i", "Reformatting the FHiCL documents...", 1, False)

        try:
            self.create_setup_fhiclcpp_if_needed()
        except:
            raise
#------------------------------------------------------------------------------
# P.Murat: TODO
# is this an assumption that reformatted FCL's and processes make two parallel lists,
# so one could use the same common index to iterate ?
#-------v----------------------------------------------------------------------
        # breakpoint()
        rcu.reformat_fhicl_documents(os.environ["TFM_SETUP_FHICLCPP"], self.procinfos)

        self.print_log("i", "done (%.1f seconds)." % (time.time() - starttime))

        starttime = time.time()
        self.print_log("i", "Bookkeeping the FHiCL documents...", 1, False)

        try:
            self.bookkeeping_for_fhicl_documents()
        except Exception:
            self.print_log("e", traceback.format_exc())
            self.alert_and_recover(
                "An exception was thrown when performing bookkeeping on the process "
                "FHiCL documents; see traceback above for more info"
            )
            return

        self.print_log("i", "done (%.1f seconds)." % (time.time() - starttime))
#------------------------------------------------------------------------------
# P.Murat: it doesn't make sense to submit the jobs before FCL's are reformatted, does it ?
#          now, with the info on hand about the processes contained in procinfos, actually launch them
#          this needs to be done every time
############
        self.print_log("i", "\n%s: CONFIG transition 010 Pasha: before launching artdaq processes\n" % (rcu.date_and_time()))

        self.print_log("i", "\n%s Launching the artdaq processes" % rcu.date_and_time())
        self.called_launch_procs = True
        self.launch_procs_time   = time.time()  # Will be used when checking logfile's timestamps

        try:
#------------------------------------------------------------------------------
# this is where the processes are launched - 
############
            # breakpoint()
            launch_procs_actions = self.launch_procs()

            assert type(launch_procs_actions) is dict, rcu.make_paragraph(
                ("The launch_procs function needs to return a dictionary whose keys are the names of the hosts"
                 " on which it ran commands, and whose values are those commands"))

        except Exception:
            self.print_log("e", traceback.format_exc())
            self.alert_and_recover("An exception was thrown in launch_procs(), see traceback above for more info")
            return

        self.print_log("i", "\n%s: CONFIG transition 011 Pasha : done launching\n" % (rcu.date_and_time()))
#------------------------------------------------------------------------------
# start checking if the launch was successful
#-------v----------------------------------------------------------------------
        # breakpoint()
        rc = self.check_launch_results();
        if (rc != 0): return;

        self.print_log("i", "\n%s: CONFIG transition 012 Pasha : before create_time_server_proxy\n" % (rcu.date_and_time()))

        rc = self.create_time_server_proxy();
        if (rc != 0): return;

        self.print_log("i", "\n%s: CONFIG transition 013 Pasha : before self.manage_processes\n" % (rcu.date_and_time()))
#------------------------------------------------------------------------------
# define names of all logfiles 
############
        rc = self.get_lognames();
        if (rc != 0): return;
#------------------------------------------------------------------------------
#  former end of DO_BOOT
#------------------------------------------------------------------------------
        if (os.environ["TFM_PROCESS_MANAGEMENT_METHOD"] == "external_run_control"):
            self.add_ranks_from_ranksfile()
#------------------------------------------------------------------------------
# dealing with the run records, probably, after the submittion
########
        self.tmp_run_record = "/tmp/run_record_attempted_%s/%d" % (self.fUser,self.partition())

        self.print_log("i", "\n%s: CONFIG transition 013 Pasha" % (rcu.date_and_time()))

        self.semipermanent_run_record = "/tmp/run_record_attempted_%s/%s" % (
            self.fUser,
            subprocess.Popen("date +%a_%b_%d_%H:%M:%S.%N",
                             executable="/bin/bash",
                             shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             encoding="utf8",
                         ).stdout.readlines()[0].strip(),
        )

        assert not os.path.exists(self.semipermanent_run_record)

        if os.path.exists(self.tmp_run_record): shutil.rmtree(self.tmp_run_record)

        starttime = time.time()
        self.print_log("i", "Saving the run record...", 1, False)

        try:
            self.save_run_record()
        except Exception:
            self.print_log("w", traceback.format_exc())
            self.print_log("w",
                           rcu.make_paragraph(
                               ("WARNING: an exception was thrown when attempting to save the run record. "
                                "While datataking may be able to proceed, this may also indicate a serious problem")
                           ),
            )

        self.print_log("i", "done (%.1f seconds)." % (time.time() - starttime))

        try:
            self.check_config()
        except Exception:
            self.print_log("w", traceback.format_exc())
            self.revert_failed_transition("calling experiment-defined function check_config()")
            return

        self.print_log("i", "\n%s: CONFIG transition 015 Pasha" % (rcu.date_and_time()))
#------------------------------------------------------------------------------
# sending 'Init' command to artdaq processes - at this point they should be already submitted
# insert the last part of former do_boot right above
#------------------------------------------------------------------------------
        if self.manage_processes:
            self.readjust_process_priorities(self.boardreader_priorities_on_config)

            try:
                self.do_command("Init")
            except Exception:
                self.print_log("d", traceback.format_exc(), 2)
                self.alert_and_recover(
                    ('An exception was thrown when attempting to send the "init" transition '
                     'to the artdaq processes; see messages above for more info'))
                return

            starttime = time.time()

            self.print_log("i","Ensuring FHiCL documents will be archived in the output *.root files",1,False)
            self.print_log("d", "\n", 3)

            labeled_fhicl_documents = []

            for p in self.procinfos:
                labeled_fhicl_documents.append((p.label,re.sub("'", '"', p.fhicl_used)))
#------------------------------------------------------------------------------
# at this point, metadata.txt shall exist in self.tmp_run_record
#------------------------------------------------------------------------------
            for filestub in ["metadata", "boot"]:
                with open("%s/%s.txt" % (self.tmp_run_record, filestub)) as inf:
                    contents = inf.read()
                    contents = re.sub("'", '"', contents)
                    contents = re.sub('"', '"', contents)
                    labeled_fhicl_documents.append((filestub, 'contents: "\n%s\n"\n' % (contents)))

            self.archive_documents(labeled_fhicl_documents)

            endtime = time.time()
            self.print_log("i", "done (%.1f seconds)." % (endtime - starttime))

        self.complete_state_change("configuring")
        self.fState.set_completed(90);

        self.print_log("i", "\n%s: CONFIG transition 016 Pasha" % (rcu.date_and_time()))

        if self.manage_processes:
            self.print_log("i", 
                           ("\nProcess manager logfiles (if applicable):\n%s" 
                            % (", ".join(self.process_manager_log_filenames))),
            )
#------------------------------------------------------------------------------
# -- it loooks, that at this point all book-keeping and checks are done and one can submit 
#    the jobs and name the log files
#    and this is the end of the config step - run number is known ! 
#------------------------------------------------------------------------------
        self.fState.set_completed(99);
        time.sleep(1)
        self.fState = run_control_state.state("configured")

        self.print_log("i", "\n%s: CONFIG transition complete" % (rcu.date_and_time()))
        return


#------------------------------------------------------------------------------
# START transition
# self.run_number already defined at the config step
####
    def do_start_running(self):

        self.print_log("i","\n%s: START transition underway for run %d" % 
                       (rcu.date_and_time(), self.run_number))

        self.fState = run_control_state.transition("start")

        self.check_run_record_integrity()
#------------------------------------------------------------------------------
# make sure run numbers could be encoded into directory names with leading zeroes
########
        for subdir in glob.glob("%s/[0-9]*" % (self.record_directory)): 
            rn_string = subdir.split("/")[-1]
            rn        = int(rn_string)
            if (self.run_number == rn):
                raise Exception(
                    rcu.make_paragraph(
                        ('Error: requested run number "%i" is found to already exist '
                         'in the run records directory "%s"; run duplicates are not allowed.')
                        % (self.run_number, subdir)))
#------------------------------------------------------------------------------
# Mu2e run numbers take up to 6 digits
########
        rr_dir = self.run_record_directory();
        if os.path.exists(self.tmp_run_record):

            try:
                shutil.copytree(self.tmp_run_record, rr_dir)
            except:
                self.print_log("e", traceback.format_exc())
                self.alert_and_recover(
                    rcu.make_paragraph(
                        ('Error: Attempt to copy temporary run record "%s" into permanent run record'
                         ' "%s" didn\'t work; most likely reason is that you don\'t have write permission'
                         ' to %s, but it may also mean that your experiment\'s reusing a run number.'
                         ' Scroll up past the Recover transition output for further troubleshooting information.')
                        % (self.tmp_run_record,rr_dir,self.record_directory))
                )
                return
#------------------------------------------------------------------------------
# P.Murat: it looks that the run_record_directory is always local 
############
            pathlib.Path(rr_dir).touch();
            os.chmod(rr_dir, 0o555)

            assert re.search(r"^/tmp/\S", self.semipermanent_run_record)
            if os.path.exists(self.semipermanent_run_record):
                shutil.rmtree(self.semipermanent_run_record)

        else:
            self.alert_and_recover(
                "Error in FarmManager: unable to find temporary run records directory %s"
                % self.tmp_run_record
            )
            return
#------------------------------------------------------------------------------
# step X) put_config_info
########
        self.print_log("i", "\n%s: START transition 001 Pasha : before put_config_info\n" % (rcu.date_and_time()))

        try:
            self.put_config_info()
        except Exception:
            self.print_log("e", traceback.format_exc())
            self.alert_and_recover(
                "An exception was thrown when trying to save configuration info; see traceback above for more info"
            )
            return

        if os.environ["TFM_PROCESS_MANAGEMENT_METHOD"] == "external_run_control" and \
           os.path.exists("/tmp/info_to_archive_partition%d.txt" % self.partition()):

            os.chmod(rr_dir, 0o755)
            shutil.copyfile("/tmp/info_to_archive_partition%d.txt" % self.partition(),
                     "%s/rc_info_start.txt" % (rr_dir)
            )
            os.chmod(rr_dir, 0o555)

            if not os.path.exists("%s/rc_info_start.txt" % (rr_dir)):
                self.alert_and_recover(
                    rcu.make_paragraph(
                        ("Problem copying /tmp/info_to_archive_partition%d.txt into %s/rc_info_start.txt;"
                         " does original file exist?")
                        % (self.partition(), rr_dir)
                    )
                )
#------------------------------------------------------------------------------
# start TRACE ???
########
        self.print_log("i", "\n%s: START transition underway 002 Pasha : before execute_trace_script\n" % (rcu.date_and_time()))
        self.execute_trace_script("start")

        self.print_log("i", "\n%s: START transition underway 003 Pasha : self.manage_processes=%i\n" 
                       % (rcu.date_and_time(),self.manage_processes))
        if self.manage_processes:

            self.readjust_process_priorities(self.boardreader_priorities_on_start)

            try:
                self.do_command("Start")
            except Exception:
                self.print_log("d", traceback.format_exc(), 2)
                self.alert_and_recover(
                    ('An exception was thrown when attempting to send the "start" transition '
                     'to the artdaq processes; see messages above for more info'))
                return

        self.start_datataking()
#------------------------------------------------------------------------------
# P.Murat: one more example of how not to program in Python
#------------------------------------------------------------------------------
        start_time = datetime.now(timezone.utc).strftime("%a %b  %-d %H:%M:%S %Z %Y");

        self.print_log("i", "\n%s: START transition underway 003 Pasha :record_directory:%s run_number: %i [%s]\n" 
                       % (rcu.date_and_time(),self.record_directory,self.run_number,start_time))

        self.save_metadata_value("FarmManager start time",start_time);
#------------------------------------------------------------------------------
# run processes have started softlinks to the logfiles of this run
# this should go away
########
##        if self.manage_processes:
##            starttime = time.time()
##            self.print_log("i","\nAttempting to provide run-numbered softlinks to the logfiles...",1,False)
##            self.print_log("d", "", 2)
##            self.softlink_logfiles()
##            endtime = time.time()
##            self.print_log("i", "softlinks done (%.1f seconds)." % (endtime - starttime))

        self.print_log("i", "\nRun info can be found locally at %s\n" % (self.run_record_directory()))

        self.complete_state_change("starting")
#------------------------------------------------------------------------------
# to preserve formal logic: transition completes, then the state changes
#-------v----------------------------------------------------------------------
        self.fState.set_completed(100);
        time.sleep(1);
        self.fState = run_control_state.state("running")

        self.print_log("i","\n%s: START transition complete for run %d" % (rcu.date_and_time(), self.run_number))
        return


#------------------------------------------------------------------------------
# STOP the run
#---v--------------------------------------------------------------------------
    def do_stop_running(self):

        self.print_log("i","\n%s: STOP transition underway for run %d"%(rcu.date_and_time(),self.run_number))

        self.fState = run_control_state.transition("stop")
        self.fState.set_completed(0);
        run_stop_time = datetime.now(timezone.utc).strftime("%a %b  %-d %H:%M:%S %Z %Y");
        self.save_metadata_value("FarmManager stop time",run_stop_time);

        try:
            self.put_config_info_on_stop()
        except Exception:
            self.print_log("e", traceback.format_exc())
            self.alert_and_recover(
                ("An exception was thrown when trying to save configuration info; "
                 "see traceback above for more info")
            )
            return

        self.stop_datataking()

        if os.environ["TFM_PROCESS_MANAGEMENT_METHOD"] == "external_run_control" and \
           os.path.exists("/tmp/info_to_archive_partition%d.txt" % (self.partition())):
            run_record_directory = "%s/%s" % (self.record_directory,str(self.run_number))
            os.chmod(run_record_directory, 0o755)

            shutil.copyfile(
                "/tmp/info_to_archive_partition%d.txt" % self.partition(),
                "%s/rc_info_stop.txt" % (run_record_directory),
            )
            os.chmod(run_record_directory, 0o555)

            if not os.path.exists("%s/rc_info_stop.txt" % (run_record_directory)):
                self.alert_and_recover(rcu.make_paragraph(
                    ("Problem copying /tmp/info_to_archive_partition%d.txt into %s/rc_info_stop.txt; "
                     "does original file exist?") % (self.partition(), run_record_directory))
                )

        if self.manage_processes:
            self.readjust_process_priorities(self.boardreader_priorities_on_stop)

            try:
                self.do_command("Stop")
            except Exception:
                self.print_log("d", traceback.format_exc(), 2)
                self.alert_and_recover(
                    ('An exception was thrown when attempting to send the "stop" transition '
                     'to the artdaq processes; see messages above for more info'))
                return

        self.execute_trace_script("stop")
        self.complete_state_change("stopping")
        self.fState.set_completed(50);
#------------------------------------------------------------------------------
# P.M. moved from the runner loop
#-------v----------------------------------------------------------------------
        self.do_command("Shutdown")
#------------------------------------------------------------------------------
# to preserve formal logic: transition completes, then the state changes
#-------v----------------------------------------------------------------------
        self.fState.set_completed(100);
        time.sleep(1);
        self.fState = run_control_state.state("stopped")

        self.print_log("i","\n%s: STOP transition complete for run %d"%(rcu.date_and_time(),self.run_number))
        return

#------------------------------------------------------------------------------
#  SHUTDOWN transition - complete everything and exit
#---v--------------------------------------------------------------------------
    def do_shutdown(self):
        print("FarmManager::do_shutdown: state=",self.fState.get_name())

        if (self.fState.get_name() == "stopped"):
            self.fKeepRunning = False
        else:
            print("FarmManager::do_shutdown: ERROR: state=%s\n",self.fState.get_name())
        return

#------------------------------------------------------------------------------
#  TERMINATE transition - what does it really do ?
#---v--------------------------------------------------------------------------
    def do_terminate(self):

        self.print_log("i", "\n%s: TERMINATE transition underway\n" % (rcu.date_and_time()))

        if self.manage_processes:

            self.process_manager_cleanup()

            starttime = time.time()
            self.print_log("i", "Sending shutdown transition to artdaq processes...", 1, False)

            proc_starttimes = {}
            proc_endtimes   = {}

            for procinfo in self.procinfos:
                procinfo.state = self.verbing_to_states["Shutdown"]

                try:
                    proc_starttimes[procinfo.label] = time.time()
                    procinfo.lastreturned           = procinfo.server.daq.shutdown()
                    proc_endtimes[procinfo.label]   = time.time()
                except Exception:
                    self.print_log(
                        "e",
                        "An exception was thrown when shutdown was issued to %s"
                        % (procinfo.label),
                    )
                    self.print_log("e", traceback.format_exc())

                    self.alert_and_recover(
                        "An exception was thrown during the terminate transition"
                    )
                    return
                else:
                    if (
                        procinfo.lastreturned == "Success"
                        or procinfo.lastreturned == self.target_states["Shutdown"]
                    ):
                        procinfo.state = self.target_states["Shutdown"]

            endtime = time.time()
            self.print_log("i", "done (%.1f seconds)." % (endtime - starttime))

            if self.debug_level >= 2 or len(
                [
                    dummy
                    for procinfo in self.procinfos
                    if procinfo.lastreturned != "Success"
                ]
            ):
                for procinfo in self.procinfos:
                    total_time = (
                        proc_endtimes[procinfo.label] - proc_starttimes[procinfo.label]
                    )
                    self.print_log(
                        "i",
                        "%s at %s:%s, after %.1f seconds returned string was:\n%s\n"
                        % (
                            procinfo.label,
                            procinfo.host,
                            procinfo.port,
                            total_time,
                            procinfo.lastreturned,
                        ),
                    )
            else:
                self.print_log("i", '\nAll artdaq processes returned "Success".\n')

            try:
                self.kill_procs()
            except Exception:
                self.print_log("e", "FarmManager caught an exception in " "do_terminate()")
                self.print_log("e", traceback.format_exc())
                self.alert_and_recover("An exception was thrown " "within kill_procs()")
                return

        self.complete_state_change("terminating")

        if self.manage_processes:
            self.print_log("i","Process manager logfiles (if applicable): %s"
                           % (",".join(self.process_manager_log_filenames)))
#------------------------------------------------------------------------------
# to preserve formal logic: transition completes, then the state changes
#-------v----------------------------------------------------------------------
        self.fState.set_completed(100);
        time.sleep(1);
        self.fState = run_control_state.state("stopped")

        self.print_log("i", "\n%s: TERMINATE transition complete" % (rcu.date_and_time()))
        return

#------------------------------------------------------------------------------
# RECOVER transition
#---v--------------------------------------------------------------------------
    def do_recover(self):
        run_number_string = f" for run {self.run_number}" if self.run_number else ""
        self.print_log("w","\n%s: RECOVER transition underway%s"%(rcu.date_and_time(),run_number_string))

        self.in_recovery = True

        if not self.called_launch_procs:
            self.print_log("i","FarmManager does not appear to have gotten to the point of launching the artdaq processes")

        if self.disable_recovery or not self.called_launch_procs:
            self.print_log("i","Skipping cleanup of artdaq processes, this recover step is effectively a no-op")

            self.in_recovery = False
            self.complete_state_change("recovering")
            self.print_log("i","\n%s: RECOVER transition complete %s"%(rcu.date_and_time(),run_number_string))
            return

        if self.state(self.name) == "running" or self.state(self.name) == "stopping":
            try:
                self.execute_trace_script("stop")
            except Exception:
                pass

        def attempted_stop(self, procinfo):

            pid = self.get_pid_for_process(procinfo)

            if pid is None:
                if self.debug_level >= 2 or not self.heartbeat_failure:
                    self.print_log(
                        "d",
                        "Didn't find PID for %s at %s:%s"
                        % (procinfo.label, procinfo.host, procinfo.port),
                        2,
                    )
                return

            def send_recover_command(command):

                procinfo.state = self.verbing_to_states[command]
                try:
                    transition_starttime = time.time()
                    if   command == "Stop"    : procinfo.lastreturned = procinfo.server.daq.stop()
                    elif command == "Shutdown": procinfo.lastreturned = procinfo.server.daq.shutdown()
                    else:
                        assert False
                    transition_endtime = time.time()

                    self.print_log(
                        "d",
                        'Called %s on %s at %s:%s without an exception; after %.1f seconds returned string was "%s"'
                        % (
                            command,
                            procinfo.label,
                            procinfo.host,
                            procinfo.port,
                            transition_endtime - transition_starttime,
                            procinfo.lastreturned,
                        ),
                        2,
                    )
                except Exception:
                    raise

                if (
                    procinfo.lastreturned == "Success"
                    or procinfo.lastreturned == self.target_states[command]
                ):
                    self.print_log(
                        "d",
                        "Successful %s sent to %s at %s"
                        % (command, procinfo.label, procinfo.rpc_server()),
                        2,
                    )
                    procinfo.state = self.target_states[command]
                else:
                    raise Exception(
                        rcu.make_paragraph(
                            "Attempted %s sent to artdaq process %s "
                            % (command, procinfo.label)
                            + "at %s during recovery procedure"
                            % (procinfo.rpc_server())
                            + ' returned "%s"' % (procinfo.lastreturned)
                        )
                    )

            try:
                procinfo.lastreturned = procinfo.server.daq.status()
            except Exception:
                msg = (
                    ("Unable to determine state of artdaq process %s at %s; "
                     "will not be able to complete its stop-and-shutdown")
                    % (procinfo.label, procinfo.rpc_server())
                )
                if (self.state(self.name) != "stopped" and 
                    self.state(self.name) != "booting" and 
                    self.state(self.name) != "terminating"): self.print_log("e", rcu.make_paragraph(msg))
                else                                       : self.print_log("d", rcu.make_paragraph(msg), 2)

                return
            else:
                procinfo.state = procinfo.lastreturned

            if procinfo.state == "Running":

                try:
                    send_recover_command("Stop")
                except Exception:
                    if "ProtocolError" not in traceback.format_exc():
                        self.print_log("e", traceback.format_exc())
                    self.print_log("e", rcu.make_paragraph(
                        "Exception caught during stop transition sent to artdaq process %s " % (procinfo.label)
                        + "at %s:%s during recovery procedure; " % (procinfo.host, procinfo.port)
                        + "it's possible the process no longer existed\n"),
                    )
                    return
                try:
                    procinfo.lastreturned = procinfo.server.daq.status()
                except Exception:
                    self.print_log(
                        "e",
                        ("Unable to determine state of artdaq process %s at %s:%s; "
                         "will not be able to complete its stop-and-shutdown")
                        % (procinfo.label, procinfo.host, procinfo.port),
                    )
                    return
                else:
                    procinfo.state = procinfo.lastreturned

            if procinfo.state == "Ready":

                try:
                    send_recover_command("Shutdown")
                except Exception:
                    if "ProtocolError" not in traceback.format_exc():
                        self.print_log("e", traceback.format_exc())
                    self.print_log("e",rcu.make_paragraph(
                        "Exception caught during shutdown transition sent to artdaq process %s " % (procinfo.label)
                        + "at %s:%s during recovery procedure;" % (procinfo.host, procinfo.port)
                        + " it's possible the process no longer existed\n")
                    )
                    return
            return

        if self.manage_processes:

            # JCF, Feb-1-2017

            # If an artdaq process has died, the others might follow
            # soon after - if this is the case, then wait a few
            # seconds to give them a chance to die before trying to
            # send them transitions (i.e., so they don't die AFTER a
            # transition is sent, causing more errors)

            if self.heartbeat_failure:
                sleep_on_heartbeat_failure = 0

                self.print_log(
                    "d",
                    rcu.make_paragraph(
                        "A process previously was found to be missing; "
                        + "therefore will wait %d seconds before attempting to send the normal transitions as part of recovery\n"
                        % (sleep_on_heartbeat_failure)
                    ),
                    2,
                )
                time.sleep(sleep_on_heartbeat_failure)

            for name in ["BoardReader","EventBuilder","DataLogger","Dispatcher","RoutingManager"]:
                self.print_log("i","%s: Attempting to cleanly wind down the %ss if they (still) exist"%(rcu.date_and_time(), name))

                threads = []
                priorities_used = {}

                for procinfo in self.procinfos:
                    if name in procinfo.name:
                        priorities_used[
                            procinfo.priority
                        ] = "We only care about the key in the dict"

                for priority in sorted(priorities_used.keys(), reverse=True):
                    for procinfo in self.procinfos:
                        if name in procinfo.name and priority == procinfo.priority:
                            t = rcu.RaisingThread(target=attempted_stop, args=(self, procinfo))
                            threads.append(t)
                            t.start()

                    for thread in threads:
                        thread.join()

        if self.manage_processes:
            print
            self.print_log("i","%s: Attempting to kill off the artdaq processes from this run if they still exist"
                           % (rcu.date_and_time()))
            try:
                self.kill_procs()
            except Exception:
                self.print_log("e", traceback.format_exc())
                self.print_log("e",rcu.make_paragraph(
                        ("An exception was thrown "
                         "within kill_procs(); artdaq processes may not all have been killed"))
                )

        self.in_recovery = False

        # JCF, Oct-15-2019

        # Make sure that the runner function won't just proceed with a transition "in the queue" 
        # despite FarmManager being in the Stopped state after we've finished this recover

        self.__do_boot            = False
        self.__do_shutdown        = False
        self.__do_config          = False
        self.__do_recover         = False
        self.__do_start_running   = False
        self.__do_stop_running    = False
        self.__do_terminate       = False
        self.__do_pause_running   = False
        self.__do_resume_running  = False
#        self.__do_enable          = False
#        self.__do_disable         = False

        self.do_trace_get_boolean = False
        self.do_trace_set_boolean = False

        self.complete_state_change("recovering")
#------------------------------------------------------------------------------
# after that, do_boot to get into the idle (booted) state
#-------v----------------------------------------------------------------------
        self.__do_boot = False
        self.do_boot()
#------------------------------------------------------------------------------
# to preserve formal logic: transition completes, then the state changes
#-------v----------------------------------------------------------------------
        self.fState.set_completed(100);
        time.sleep(1);
        self.fState = run_control_state.state("stopped")
#------------------------------------------------------------------------------
# marking the end of function
#-------v----------------------------------------------------------------------
        self.print_log("i","\n%s: RECOVER transition complete%s"%(rcu.date_and_time(),run_number_string))
        return

#------------------------------------------------------------------------------
# tfm::artdaq_process_info
#---v--------------------------------------------------------------------------
    def artdaq_process_info(self, name):

        try:
            self.procinfos
        except:
            return self.state(name)  # OK if we haven't yet created the list of Procinfo structures
        else:
            tmpfile = "/tmp/artdaq_process_info_%s_partition_%d" % (self.fUser,self.partition())
            infostring = ""
            for procinfo in self.procinfos:
                host = procinfo.host
                if host == "localhost":
                    host = os.environ["HOSTNAME"]
                infostring += "%s at %s:%s (subsystem %s, rank %s): %s\n" % (
                    procinfo.label,
                    host,
                    procinfo.port,
                    procinfo.subsystem,
                    procinfo.rank,
                    procinfo.state,
                )

            with open(tmpfile, "w") as outf:
                outf.write(infostring)

            self.print_log("d", infostring, 5)

        return infostring
#------------------------------------------------------------------------------
# tfm::runner
# Override of the parent class Component's runner function. 
# As of 5/30/14, called every 1s by ??? control.py
#------------------------------------------------------------------------------
    def runner(self):

        """
        Component "ops" loop.  Called at threading hearbeat frequency, currently 1/sec.
        """

        try:

            if self.in_recovery:
                pass

            if self.exception:
                raise Exception("ERROR: an exception was raised")

            elif self.__do_boot:
                self.__do_boot = False
                self.do_boot()

            elif self.__do_config:
                self.__do_config = False
                self.do_config()

            elif self.__do_recover:
                self.__do_recover = False
                self.do_recover()

            elif self.__do_start_running:
                self.__do_start_running = False
                self.do_start_running()

            elif self.__do_stop_running:
                self.__do_stop_running = False
                self.do_stop_running()

            elif self.__do_shutdown:
                self.__do_shutdown = False
                self.do_shutdown()

            elif self.__do_terminate:
                self.__do_terminate = False
                self.do_terminate()

            elif self.__do_pause_running:
                self.__do_pause_running = False
                self.do_command("Pause")

            elif self.__do_resume_running:
                self.__do_resume_running = False
                self.do_command("Resume")

#             elif self.__do_enable:
#                 self.__do_enable = False
#                 self.do_enable()
# 
#             elif self.__do_disable:
#                 self.__do_disable = False
#                 self.do_disable()

            elif self.do_trace_get_boolean:
                self.do_trace_get_boolean = False
                self.do_trace_get()

            elif self.do_trace_set_boolean:
                self.do_trace_set_boolean = False
                self.do_trace_set()

            elif (
                self.manage_processes
                and self.state(self.name) != "stopped"
                and self.state(self.name) != "booted"
                and self.state(self.name) != "configuring"
                and self.state(self.name) != "terminating"
            ):
                # breakpoint()
                self.check_proc_heartbeats()
                self.check_proc_exceptions()
                self.perform_periodic_action()

        except Exception:
            self.in_recovery = True
            self.alert_and_recover(traceback.format_exc())
            self.in_recovery = False
            self.exception   = False

#------------------------------------------------------------------------------
# the environment overrides the code defaults, the command line overrides both
# start from figuring the artdaq partition number
# parameters are passed to the FarmManager constructor
#------------------------------------------------------------------------------
def get_args():  # no-coverage

    pn = None;
    x = os.environ.get("ARTDAQ_PARTITION_NUMBER");
    if (x) : pn = int(x);
    
    parser = argparse.ArgumentParser(description="FarmManager")

    parser.add_argument("-n","--name"        ,type=str,dest="name"        ,default="daqint"   ,help="Component name")
#    parser.add_argument("-p","--partition"   ,type=int,dest="partition"   ,default=pn         ,help="Partition number")
#    parser.add_argument("-r","--rpc-port"    ,type=int,dest="rpc_port"    ,default=5570       ,help="RPC port")
    parser.add_argument("-H","--rpc-host"    ,type=str,dest="rpc_host"    ,default="localhost",help="this hostname/IP addr")
    parser.add_argument("-c","--control-host",type=str,dest="control_host",default="localhost",help="Control host")
    parser.add_argument("-d","--debug-level" ,type=int,dest="debug_level" ,default=-1         ,help="debug level, default=-1")
    parser.add_argument("-D","--config-dir"  ,type=str,dest="config_dir"  ,default=None       ,help="config dir"  )

    return parser.parse_args()

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
def main():  # no-coverage

#    if "TFM_STANDARD_SOURCEFILE_SOURCED" not in os.environ.keys():
#        print(rcu.make_paragraph('Won\'t launch FarmManager; first run "source $TFM_DIR/source_me\n"'))
#        return

    process_management_methods = ["direct", "pmt", "external_run_control"]
    if "TFM_PROCESS_MANAGEMENT_METHOD" not in os.environ.keys():
        raise Exception(rcu.make_paragraph(
            ("Need to have the TFM_PROCESS_MANAGEMENT_METHOD set so TFM knows "
             "what method to use to control the artdaq processes (%s, etc.)")
            % (",".join(['"' + pmm + '"' for pmm in process_management_methods])))
        )
    else:
        legal_method_found = False
        for pmm in process_management_methods:
            if os.environ["TFM_PROCESS_MANAGEMENT_METHOD"] == pmm:
                legal_method_found = True

        if not legal_method_found:
            raise Exception(
                rcu.make_paragraph(
                    ('TFM can\'t interpret the current value of the TFM_PROCESS_MANAGEMENT_METHOD '
                    'environment variable ("%s"); legal values include %s')
                    % (os.environ["TFM_PROCESS_MANAGEMENT_METHOD"],
                       ",".join(['"' + pmm + '"' for pmm in process_management_methods]),
                   )
                )
            )

    if (os.environ.get("HOSTNAME") == None) :
        print(rcu.make_paragraph(('\nWARNING: os.environ.get("HOSTNAME") returns None'
                              'Will internally set HOSTNAME using socket.gethostname\n')))
        os.environ["HOSTNAME"] = socket.gethostname();
#------------------------------------------------------------------------------
# KILL signal handler - Ctrl-C, for example
#---v--------------------------------------------------------------------------
    def handle_kill_signal(signum, stack):
        tfm.print_log(
            "e",
            "%s: FarmManager on partition %s caught kill signal %d"
            % (rcu.date_and_time(), tfm.partition, signum),
        )
        tfm.recover()

        timeout   = 180  # Because the recover() call above is non-blocking
        starttime = time.time()
        while tfm.state(tfm.name) != "stopped":
            if int(time.time() - starttime) > timeout:
                tfm.print_log(
                    "e",
                    ("FarmManager signal handler recovery attempt timed out after %d seconds; "
                    "FarmManager is in the %s state rather than the stopped state")
                    % (timeout,tfm.state(tfm.name)),
                )
                break

            time.sleep(10)

        line = "%s: exiting..." % (rcu.date_and_time())
        print(line)

        tfm.__del__()

        if   signum == signal.SIGTERM: default_sigterm_handler
        elif signum == signal.SIGHUP : default_sighup_handler
        elif signum == signal.SIGINT : default_sigint_handler
        else                         : assert False

        # JCF, Mar-25-2019
        # os._exit is harder than sys.exit; see
        # https://stackoverflow.com/questions/9591350/what-is-difference-between-sys-exit0-and-os-exit
        os._exit(1)

    default_sigterm_handler = signal.signal(signal.SIGTERM, handle_kill_signal)
    default_sighup_handler  = signal.signal(signal.SIGHUP , handle_kill_signal)
    default_sigint_handler  = signal.signal(signal.SIGINT , handle_kill_signal)
#------------------------------------------------------------------------------
# parse command line, then 'boot' once and enter a daemon mode listening to commands
#---v--------------------------------------------------------------------------
    args = get_args()

    with FarmManager(**vars(args)) as tfm:
        tfm.__do_boot = False
        tfm.do_boot()

        while (tfm.fKeepRunning):
#------------------------------------------------------------------------------
# P.M. there is something odd happening when self.debug_level=0 - the MRB environment 
#      seems to get corrupted
#      for the moment, keep debug_level=1 and work around
#------------------------------------------------------------------------------
#            if (tfm.debug_level > 1):
#                print("... FarmManager sleeping for 6 sec, keeprunning=",tfm.fKeepRunning,
#                      " debug_level=",tfm.debug_level);
            time.sleep(5)
#------------------------------------------------------------------------------
# done, exit
#-------v----------------------------------------------------------------------
        tfm.__del__()
    return

#------------------------------------------------------------------------------
# this is where the main starts
#------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
