#!/bin/env python3
#------------------------------------------------------------------------------
# this code forks from artdaq_daqinterface: https://github.com/art-daq/artdaq_daqinterface
# the aim of fork is to :
# -----------------------
# a) make it work with MIDAS
# b) simplify the code and make it maintainable
# c) streamline the initialization
# d) allow artdaq clients to message back, handle client messages
#
#------------------------------------------------------------------------------
import os, sys, argparse, glob, inspect, re
from   datetime import datetime, timezone
from   operator import attrgetter
import pathlib, pdb, random, re, shutil, signal, socket, stat, string, subprocess
import threading, time, traceback

import  TRACE
TRACE_NAME="farm_manager"

import midas.client
#------------------------------------------------------------------------------
# debugging printout
#------------------------------------------------------------------------------
from   inspect import currentframe, getframeinfo

sys.path.append(os.environ["TFM_DIR"])

if "TFM_OVERRIDES_FOR_EXPERIMENT_MODULE_DIR" in os.environ:
    sys.path.append(os.environ["TFM_OVERRIDES_FOR_EXPERIMENT_MODULE_DIR"])
#------------------------------------------------------------------------------
# home brew
#------------------------------------------------------------------------------
import tfm.rc.control.run_control_state as     run_control_state
from   tfm.rc.control.subsystem         import Subsystem
from   tfm.rc.control.procinfo          import Procinfo, BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ;

from   tfm.rc.io.timeoutclient          import TimeoutServerProxy
from   tfm.rc.control.component         import Component
from   tfm.rc.control.save_run_record   import save_run_record_base
from   tfm.rc.control.save_run_record   import save_metadata_value_base

disable_bookkeeping = os.environ.get("TFM_DISABLE_BOOKKEEPING");

if (disable_bookkeeping and (disable_bookkeeping != "false")):
    from tfm.rc.control.all_functions_noop import bookkeeping_for_fhicl_documents_artdaq_v3_base
else:
    from tfm.rc.control.bookkeeping        import bookkeeping_for_fhicl_documents_artdaq_v3_base

import tfm.rc.control.utilities as rcu
import tfm.rc.control.artdaq    as artdaq

try:
    imp.find_module("daqinterface_overrides_for_experiment")
    from daqinterface_overrides_for_experiment import perform_periodic_action_base
    from daqinterface_overrides_for_experiment import start_datataking_base
    from daqinterface_overrides_for_experiment import stop_datataking_base
    from daqinterface_overrides_for_experiment import do_enable_base
    from daqinterface_overrides_for_experiment import do_disable_base
    from daqinterface_overrides_for_experiment import check_config_base
except:
    from tfm.rc.control.all_functions_noop     import perform_periodic_action_base
    from tfm.rc.control.all_functions_noop     import start_datataking_base
    from tfm.rc.control.all_functions_noop     import stop_datataking_base
    from tfm.rc.control.all_functions_noop     import do_enable_base
    from tfm.rc.control.all_functions_noop     import do_disable_base
    from tfm.rc.control.all_functions_noop     import check_config_base

from tfm.rc.control.manage_processes_direct import launch_procs_base
from tfm.rc.control.manage_processes_direct import kill_procs_base
from tfm.rc.control.manage_processes_direct import check_proc_heartbeats_base
from tfm.rc.control.manage_processes_direct import find_process_manager_variable_base
from tfm.rc.control.manage_processes_direct import set_process_manager_default_variables_base

from tfm.rc.control.manage_processes_direct import reset_process_manager_variables_base
from tfm.rc.control.manage_processes_direct import get_process_manager_log_filenames_base

from tfm.rc.control.manage_processes_direct import process_manager_cleanup_base
from tfm.rc.control.manage_processes_direct import get_pid_for_process_base
from tfm.rc.control.manage_processes_direct import process_launch_diagnostics_base
from tfm.rc.control.manage_processes_direct import mopup_process_base

#------------------------------------------------------------------------------   
class FarmManager(Component):
    """
    FarmManager: The intermediary between Run Control, the
    configuration database, and artdaq processes

    """

    def print_log(self, severity, printstr, debuglevel=-999, newline=True):
        level = {'e':'ERR', 'w':'WRN', 'd':'DBG', 'i':'INF'};
        if self.debug_level < debuglevel:   return
#------------------------------------------------------------------------------
# JCF, Dec-31-2019
# The swig_artdaq instance by default writes to stdout, so no explicit print call is needed
#-----------v-------------------------------------------------------------------
        printstr      = str(printstr)
        date_time     = rcu.date_and_time()
        formatted_day = date_time.split()[0] # "%s-%s-%s" % (day, month, year)

        if self.use_messagefacility and self.messageviewer_sender is not None:
            if severity == "e":
                self.messageviewer_sender.write_error(
                    "FarmManager partition %d" % self.partition(),printstr)
            elif severity == "w":
                self.messageviewer_sender.write_warning(
                    "FarmManager partition %d" % self.partition(),printstr)
            elif severity == "i":
                self.messageviewer_sender.write_info(
                    "FarmManager partition %d" % self.partition(),printstr)
            elif severity == "d":
                self.messageviewer_sender.write_debug(
                    "FarmManager partition %d" % self.partition(),printstr)
        else:
            with self.printlock:
                if self.fake_messagefacility:
                    print(f'%%MSG-{severity} FarmManager {formatted_day} {time} timezone',flush=True)
                    print(printstr, flush=True)
                    print('%MSG', flush=True)
                else:
                    frame = inspect.stack()[1];
                    fn    = frame.filename.split('/')[-1];
                    fun   = frame.function
                    ln    = frame.lineno
                    fn_ln = fn+f':{ln}'
                    
                    if not newline:
                        sys.stdout.write("%s %3s %-25s %s %s" % (date_time, level[severity], fn_ln, fun, printstr))
                        sys.stdout.flush()
                    else:
                        print("%s %3s %-25s %s" % (date_time,level[severity],fn_ln,fun), printstr, flush=True)
        return;
#------------------------------------------------------------------------------
# JCF, Dec-16-2016

# The purpose of reset_variables is to reset those members that 
# (A) aren't necessarily persistent to the process and
# (B) won't necessarily be set explicitly during the transitions up from the "stopped" state. 
#
# E.g., you wouldn't want to return to the "stopped" state with self.exception == True 
# and then try a boot-config-start without self.exception being reset to False
#---v--------------------------------------------------------------------------
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
        return
#------^-----------------------------------------------------------------------
# want run number to be always printed with 6 digits
# called from get_config_info_base (config_functions_local.py)
#---v--------------------------------------------------------------------------
    def get_config_parentdir(self):
        self.print_log("w","%s::get_config_parentdir: WHY IS IT CALLED ????" %(sys.modules[__name__]),2)
        return self.artdaq_config_dir; ## os.environ["TFM_FHICL_DIRECTORY"]

    def run_record_directory(self):
        return "%s/%06i" % (self.record_directory,self.run_number);

    def metadata_filename(self):
        return "%s/metadata.txt" % (self.run_record_directory());
#------------------------------------------------------------------------------
# default artdaq port numbering: 10000+1000*partition+rank
# for Mu2e, assume that the first boardreader (br01) has its rank = 101
#------------------------------------------------------------------------------
    def xmlrpc_port_number(self,rank):
        port = self.base_port_number+self.partition()*self.ports_per_partition+rank
        return port

    def find_process(self,label):
        for p in self.procinfos:
            if (p.label == label):
                return p;

        return None
#------------------------------------------------------------------------------
# format (and location) of the PMT logfile - 
# includes directory, run_number, host, user, partition (in integer), and a timestamp
#---v--------------------------------------------------------------------------
    def pmt_log_filename_format(self):
        return "%s/pmt/pmt_%06i_%s_%s_partition_%02i_%s"

    def odb_cmd_path(self):
        return self._cmd_path;
    
#------------------------------------------------------------------------------
# WK 8/31/21
# Startup msgviewer early. check on it later
#---v--------------------------------------------------------------------------
    def start_message_viewer(self):
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
        return;
#-------^----------------------------------------------------------------------
# make sure that the setup script to be executed on each node runs successfully 
#---v--------------------------------------------------------------------------
    def validate_setup_script(self,node):

        starttime              = time.time()

        self.print_log("i",
                       ("\n%s On randomly selected node (%s), will confirm that the DAQ setup script \n"
                        "%s\ndoesn't return a nonzero value when sourced...")
                       % (rcu.date_and_time(),node, self.daq_setup_script),
                       1,
                       False,
                )

        spack_env = os.getenv('SPACK_ENV').split('/')[-1];
        cmd = "%s ; . %s %s" % (";".join(rcu.get_setup_commands(self.productsdir, self.spackdir)),
                                self.daq_setup_script,spack_env)

        self.print_log("i",f'cmd:"{cmd}"\n',1,False);

        if not rcu.host_is_local(node):
            cmd = "timeout %d ssh %s '%s'" % (self.ssh_timeout_in_seconds,node,cmd)

        out = subprocess.Popen(cmd,
                               executable="/bin/bash",
                               shell=True,
                               stderr=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               encoding="utf-8")

        out_comm = out.communicate()

        if out_comm[0] is not None:
            out_stdout = out_comm[0]
            self.print_log("d","\nSTDOUT: \n%s" % (out_stdout),2)

        if out_comm[1] is not None:
            out_stderr = out_comm[1]
            self.print_log("d","STDERR: \n%s"   % (out_stderr),2)
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
#        self.print_log("i", "%s::validate_setup_script done (%.1f seconds)." % (__file__,endtime - starttime),2)
        self.print_log("i", "validate_setup_script done (%.1f seconds)." % (endtime - starttime),2)

#------------------------------------------------------------------------------
# ODB help functions
#------------------------------------------------------------------------------
    def odb_get_int(self,path,default=None):
        if (self.client.odb_exists(path)):
            return int(self.client.odb_get(path));
        else:
            return default;

    def odb_get_bool(self,path,default=False):
        if (self.client.odb_exists(path)):
            return bool(self.client.odb_get(path));
        else:
            return default;

    def odb_get_string(self,path,default=None):
        if (self.client.odb_exists(path)):
            return str(self.client.odb_get(path));
        else:
            return default;


#------------------------------------------------------------------------------
# 'public names' = short names , i.e. 'mu2edaq22'
# TODO : this is a kludge, reimplement via :
# ifconfig -a | grep 10.226.9 | awk '{print $2}' | nslookup | head -n 1 | awk '{print $4}' | awk -F . '{print $1}'
#------------------------------------------------------------------------------
    def hostname_on_private_subnet(self,public_hostname):
        self.print_log('i',f'--- {sys._getframe(0).f_code.co_name} START ',3)
        hname = 'undefined'
        if (self.private_subnet == '192.168.157'):
            hname = public_hostname+'-ctrl'
        elif (self.private_subnet == '131.225.237'):
            hname = public_hostname
        elif (self.private_subnet == '131.225.38'):
            hname = public_hostname
        elif (self.private_subnet == '10.226.9'):
            hname = public_hostname+'-data'

        self.print_log('i',f'public_hostname:{public_hostname} self.private_subnet:{self.private_subnet} hname:{hname}',3)

        self.print_log('i',f'--- END',3)
        
        return hname;

#------------------------------------------------------------------------------
# PM: create self.procinfo's
#------------------------------------------------------------------------------
    def init_artdaq_processes(self):

        self.print_log('i',f'{sys._getframe(0).f_code.co_name} START',3)
        nodes_path = "/Mu2e/ActiveRunConfiguration/DAQ/Nodes"
        nodes_dir  = self.client.odb_get(nodes_path);
        TRACE.INFO(f'-- START nodes_path:{nodes_path}',TRACE_NAME)
#------------------------------------------------------------------------------
# in this directory, expect only nodes (labels)
#-------v----------------------------------------------------------------------
        for short_node_name in nodes_dir.keys():
            node_path    = nodes_path+'/'+short_node_name;
            node_enabled = self.client.odb_get(node_path+'/Enabled')
            TRACE.DEBUG(1,f'node_path:{node_path} node_enabled:{node_enabled}',TRACE_NAME)
            if (node_enabled == 0) : continue;
            
            node_artdaq_path = nodes_path+'/'+short_node_name+'/Artdaq';
            
            TRACE.DEBUG(0,f'node_artdaq_path:{node_artdaq_path}',TRACE_NAME)
            enabled = self.client.odb_get(node_artdaq_path+'/Enabled')
            TRACE.DEBUG(0,f'short_node_name:{short_node_name} node_artdaq_path:{node_artdaq_path} enabled:{enabled}')
            if (enabled == 0):  continue ;

            node_artdaq_dir = self.client.odb_get(node_artdaq_path)
            for key_name,key_value in node_artdaq_dir.items():        # loop over processes on this node
                TRACE.DEBUG(0,f'key_name:{key_name} key_value:{key_value}',TRACE_NAME)
                if (key_name == 'Enabled') or (key_name == 'Status') : continue;
                process_path = f'{node_artdaq_path}/{key_name}'
                TRACE.DEBUG(0,f'process_path:{process_path}',TRACE_NAME)
#------------------------------------------------------------------------------
# at this point, expect 'key_name; to be a process label and skip disabled processes
#---------------v--------------------------------------------------------------
                enabled = self.client.odb_get(process_path+'/Enabled')
                if (enabled == 0) : continue;
                # subdir2 is a dict , subdir2['max_fragment_size_bytes] 
                subdir2 = self.client.odb_get(process_path)
                TRACE.DEBUG(0,f'subdir2 process_path:{process_path}',TRACE_NAME)
                for name,value in subdir2.items():
                    if (name == "Rank"):              rank      = int(value)
                    # if (name == "XmlrpcPort"):        port      = str(value)
                    if (name == "Subsystem" ):        subsystem = str(value)
                    if (name == "AllowedProcessors"): allowed_processors = str(value)
                    if (name == "Target"):            target    = str(value)                        
                    if (name == "Prepend"):           prepend   = str(value)

                timeout = 30;                 # seconds
                pname   = 'undefined';
#------------------------------------------------------------------------------
# PM: this naming is something to get rid of - a Procinfo thing has a type, so a
# name is an overkill
#------------------------------------------------------------------------------
                if   (key_name[0:2] == 'br') :
                    pname       = 'BoardReader'
                    timeout     = self.boardreader_timeout;
                    if ('DTC' in subdir2.keys()):
                        dtc_enabled = self.client.odb_get(process_path+'/DTC/Enabled')
                        if (dtc_enabled == 0) :
#------------------------------------------------------------------------------
# a boardreader may read a DTC. If the DTC present but disabled, don't start the boardreader
# also, disable the boardreader
#------------------------------------------------------------------------------
                            self.client.odb_set(process_path+'/Enabled',0) ##
                            continue
                elif (key_name[0:2] == 'dl') :
                    pname   = 'DataLogger'
                    timeout = self.datalogger_timeout;
                elif (key_name[0:2] == 'ds') :
                    pname   = 'Dispatcher'
                    timeout = self.dispatcher_timeout;
                elif (key_name[0:2] == 'eb') :
                    pname   = 'EventBuilder'
                    timeout = self.eventbuilder_timeout;
                elif (key_name[0:2] == 'rm') :
                    pname   = 'RoutingManager'
                    timeout = self.routingmanager_timeout;
                else:
                    raise Exception(f'ERROR: undefined process type:{label} for {host}')

                host = self.hostname_on_private_subnet(short_node_name)

                # to not hide 100000+1000*partition_id_rank in procinfo
                xmlrpc_port = self.xmlrpc_port_number(rank);
                fcl_fn      = f'{self.config_dir}/{key_name}.fcl';
                
                TRACE.DEBUG(0,f'name:{pname} label:{key_name} rank:{rank} port:{xmlrpc_port}')
                p = Procinfo(name               = pname,
                             rank               = rank ,
                             host               = host ,          # at this point, store long (with '-ctrl' names)
                             port               = str(xmlrpc_port),
                             timeout            = timeout,
                             label              = key_name  ,
                             subsystem          = subsystem,
                             allowed_processors = None,
                             target             = "none",
                             fhicl              = fcl_fn,
                             prepend            = ""
                             )
                if (p.type() == BOARD_READER):
                    # for a BR, fragment and event are the same, for all other processes, event size is calculated
                    p.max_fragment_size_bytes = subdir2['max_fragment_size_bytes']
                    p.max_event_size_bytes    = p.max_fragment_size_bytes;
                
                if (p.server == None):
                    self.alert_and_recover(f'ERROR: failed to create an XMLRPC server for process:{key_name} and socket:{host}:{port}')
                else:
                    p.print();
                    self.procinfos.append(p)

        self.procinfos.sort(key=lambda x: x.rank)
#-------^-----------^----------------------------------------------------------
# an exersize: print host map, sort procinfos by rank anyway
#-------v----------------------------------------------------------------------
               
        TRACE.INFO('-- END',TRACE_NAME)
        return;

#-------^----------------------------------------------------------------------
# there should be at least one subsystem defined
# in a configuration, subsystems are described under "DAQ/Subsystems" 
#---v--------------------------------------------------------------------------
    def init_artdaq_subsystems(self):

        self.subsystems = {}
        
        self.print_log('i','---START')

        path     = self.daq_conf_path + "/Subsystems"

        self.print_log('i',f'path:{path}');
#------------------------------------------------------------------------------
# expect only subsystem definitions in this subdirectory
#------------------------------------------------------------------------------
        dir      = self.client.odb_get(path)
        for (ss_id,data) in dir.items():
            
            self.print_log('i',f'subsystem_id:{ss_id} data:{data}',3)
            if (data['Enabled'] == 0): continue ;
            
            subdir_path=path+f'/{ss_id}'
            self.print_log('i',f'subdir_path:{subdir_path}')
            
            s     = Subsystem(ss_id);
            # assume sources to be a comma-separated list
            if ('sources' in data.keys()): 
                for x in data['sources'].split(','):
                    s.sources.append(x)
                    
            if ('destination'   in data.keys()):
                if (data['destination'] == 'none'): s.destination = None;
                else                              : s.destination = data['destination'];

            if ('fragment_mode' in data.keys()): s.fragmentMode = data['fragmentmode'];
#------------------------------------------------------------------------------
# associative array - a dict, so subsystem ID is a string !
#------------------------------------------------------------------------------
            s.print()
            self.subsystems[s.id] = s
#-----------^------------------------------------------------------------------
# associative array - a dict, so subsystem ID is a string !
#-------v----------------------------------------------------------------------
        self.print_log('i',f'N subsystems:{len(self.subsystems.keys())}')
        
        for k in self.subsystems.keys():
#            print('k,type  = ',k,type(k))
#            print('v,type  = ',v,type(v))
            self.subsystems[k].print();

        self.print_log('i','--- END')
        
        return

#------------------------------------------------------------------------------
# define processes this p.type = BOARD_READER, BR is talking to destinations only
#------------------------------------------------------------------------------
    def init_br_connections(self,p):
        
        s = self.subsystems[p.subsystem]; # subsystem which a given process belongs to
        if (s.max_type >= EVENT_BUILDER):
            list_of_ebs = s.list_of_procinfos[EVENT_BUILDER]
            for eb in list_of_ebs:
                p.list_of_destinations.append(eb);
                eb.list_of_sources.append(p);
        else:
            # check subsystem destination
            print(f'-- [init_br_connections] p.label:{p.label} s.destination:{s.destination}')
            if (s.destination != None):
                # subsystem has a destination, that has to have event builders
                sd = self.subsystems[s.destination];
                list_of_ebs = sd.list_of_procinfos[EVENT_BUILDER]
                print(f'-- [init_br_connections] sd.id:{sd.id} len(list_of_ebs):{len(list_of_ebs)}')
                
                for eb in list_of_ebs:
                    print(f'-- [init_br_connections] append {eb.label} to the destinations of {p.label}')
                    p.list_of_destinations.append(eb);
                    eb.list_of_sources.append(p);
        return;

#------------------------------------------------------------------------------
# define processes for p.type = EVENT_BUILDER,
# event builder should have some connections
#------------------------------------------------------------------------------
    def init_eb_connections(self,p):
        print(f'--------------------------- init_ib_connections:{p.label}')
        # EB has to have inputs - either from own BRs or from other subsystems or EBs from other subcyctems
        # start from checking inputs
        s = self.subsystems[p.subsystem]; # subsystem which a given process belongs to
        # BRs should already be covered, check for input from other EBs

        p.max_fragment_size_bytes = 0;
        p.max_event_size_bytes    = 0;

        print(f's.sources:{s.sources}');
        print(f'p.list_of_sources:{p.list_of_sources}');

        if (len(s.sources) > 0):
            for source in s.sources:
                ss = self.subsystems[source]
                # there should be no DLs in the source subsystem, it should end in EB
                if (ss.max_type == EVENT_BUILDER):
                    list_of_ebs = ss.list_of_procinfos[EVENT_BUILDER]
                    for eb in list_of_ebs:
                        p.max_event_size_bytes += eb.max_event_size_bytes;
                        # avoid double counting
                        if (not eb in p.list_of_sources):
                            p.list_of_sources.append(eb);
                            eb.list_of_destinations.append(p);

                elif (ss.max_type == BOARD_READER):
                    list_of_brs = ss.list_of_procinfos[BOARD_READER]
                    for br in list_of_brs:
                        p.max_event_size_bytes   += br.max_fragment_size_bytes;
                        if (br.max_fragment_size_bytes > p.max_fragment_size_bytes):
                            p.max_fragment_size_bytes = br.max_fragment_size_bytes;
                        # avoid double counting
                        if (not br in p.list_of_sources):
                            p.list_of_sources.append(eb);
                            eb.list_of_destinations.append(p);

        else:
#-------^----------------------------------------------------------------------
# subsystem doesn't have inputs, look at local BRs - those are already in the list
# of inputs
#-----------v------------------------------------------------------------------
            for br in p.list_of_sources:
                print(f'br.label:{br.label} br.max_fragment_size_bytes:{br.max_fragment_size_bytes}')
                p.max_event_size_bytes += br.max_fragment_size_bytes
                if (br.max_fragment_size_bytes > p.max_fragment_size_bytes):
                    p.max_fragment_size_bytes = br.max_fragment_size_bytes;

                print(f'p.max_event_size_bytes:{p.max_event_size_bytes} p.max_fragment_size_bytes:{p.max_fragment_size_bytes}')
#---------------------------^--------------------------------------------------
# - an EB should also have destinations - either DL's or other EB's
#-------v----------------------------------------------------------------------

        list_of_dls = s.list_of_procinfos[DATA_LOGGER]
        if (len(list_of_dls) > 0):
            for dl in list_of_dls:
                dl.list_of_sources.append(p);
                p.list_of_destinations.append(dl);
                    
        else:
            # subsystem has no own data loggers, should have a destination
            if (s.destination != None):
                # subsystem has a destination, that has to start with EB level
                sd = self.subsystems[s.destination]
                if (sd.min_type < EVENT_BUILDER):
                    # a problem, throw an exception
                    raise Exception('EB: trouble');
                else:
                    # first check EBs in the destination subsystem
                    list_of_ebs = sd.list_of_procinfos[EVENT_BUILDER]
                    if (len(list_of_ebs) > 0):
                        for eb in list_of_ebs:
                            p.list_of_destinations.append(eb);
                            eb.list_of_sources.append(p);
                    else:
                        # no EBs, look for DLs
                        list_of_dls = sd.list_of_procinfos[DATA_LOGGER]
                        if (len(list_of_dls) > 0):
                            for dl in list_of_dls:
                                p.list_of_destinations.append(dl);
                                dl.list_of_sources.append(p);
                        else:
                            # a problem , throw
                            raise Exception('EB: no EBs/DLs in the DEST');
        return;
#------------------------------------------------------------------------------
# define processes for p.type = DATA_LOGGER
#------------------------------------------------------------------------------
    def init_dl_connections(self,p):

        print(f'--- p.label:{p.label} p.subsystem:{p.subsystem}');
        # DL has to have inputs from either own EBs or from EBs other subsystems
        # start from checking inputs
        s = self.subsystems[p.subsystem]; # subsystem which a given process belongs to
        s.print();
        # EBs should already be covered

        p.max_event_size_bytes = 0;
        p.init_fragment_count  = 0;

        if (len(s.sources) > 0):
            for source in s.sources:
                ss = self.subsystems[source]
                # there should be no DLs in the source subsystem, it should end in EB
                list_of_ebs = ss.list_of_event_builders()
                for eb in list_of_ebs:
                    p.init_fragment_count += 1;
                    
                    if (eb.max_event_size_bytes > p.max_event_size_bytes):
                        p.max_event_size_bytes =  eb.max_event_size_bytes

                    # avoid double counting
                    if (not eb in p.list_of_sources):
                        p.list_of_sources.append(eb);
                        eb.list_of_destinations.append(p);
#---------------------------^--------------------------------------------------
# done with the sources
# an EB should also have destinations - either DL's or other EB's
#-------v----------------------------------------------------------------------
        else:
            # subsystem has no official sources, there should be local EB's
            list_of_ebs = s.list_of_event_builders()
            if (len(list_of_ebs) > 0):
                for eb in list_of_ebs:
                    p.init_fragment_count += 1;
                    if (eb.max_event_size_bytes > p.max_event_size_bytes):
                        p.max_event_size_bytes =  eb.max_event_size_bytes
                        
                    if (not eb in p.list_of_sources):
                        p.list_of_sources.append(eb);
                        eb.list_of_destinations.append(p);
                    
            else:
                # subsystem has no own EB's : trouble
                raise Exception('DL: no EBs in the subsystem');
        return;
#------------------------------------------------------------------------------
# define processes for p.type = DISPATCHER - yet to be debugged - will need fixes!
#------------------------------------------------------------------------------
    def init_ds_connections(self,p):
        # DS only has inputs ..DLs ?
        # start from checking inputs
        s = self.subsystems[p.subsystem]; # subsystem which a given process belongs to

        if (s.sources != None):
            # THERE ARE INPUT SUBSYSTEMS, there should not be local inputs
            for source in s.sources:
                ss = self.subsystems[source]
                # there should be DLs in the source subsystem
                if (ss.max_type >= DATA_LOGGER):
                    # it might make sense to allow a DL to send events to DSs anywhere,
                    # although need to check the logic
                    plist = ss.list_of_data_loggers()
                    for x in plist:
                        # avoid double counting - just in case
                        if (not x in p.list_of_sources):
                            p.list_of_sources.append(x);
                            x.list_of_destinations.append(p);
                else:
                    # ss has no DLs, check EBs 
                    plist = ss.list_of_event_builders();
                    for x in plist:
                        # avoid double counting - just in case
                        if (not x in p.list_of_sources):
                            p.list_of_sources.append(x);
                            x.list_of_destinations.append(p);
#---------------------------^--------------------------------------------------
# no input sources , check local ones
#-------v----------------------------------------------------------------------
        else:
            plist = s.list_of_data_loggers()
            if (len(plist) > 0):
                # DLs available, local EBs should be talking to them
                for x in plist:
                    p.list_of_sources.append(x);
                    x.list_of_destinations.append(p);
                    
            else:
                # subsystem has no own data loggers, look for event builders
                plist = s.list_of_event_builders()
                if (len(plist) > 0):
                    # DLs available, local EBs should be talking to them
                    for x in plist:
                        if (not x in dl.list_of_sources):
                            p.list_of_sources.append(x);
                            x.list_of_destinations.append(p);
                else:
                    # a problem , throw
                    raise Exception('DS: no local DLs or EBs');
        return;
#------------------------------------------------------------------------------
# define processes for p.type = ROUTINE_MANAGER
#------------------------------------------------------------------------------
    def init_rm_connections(self,p):
        raise Exception('inti_rm_connection: not implemented yet');
#-------^----------------------------------------------------------------------
# finally, the FarmManager constructor 
# P.Murat: 'config_dir' - a single directory with all configuration and FCL files
#---v--------------------------------------------------------------------------
    def __init__(self,
                 name              = "toycomponent",
                 artdaq_config_dir = None          ,
                 odb_client        = None          , 
                 rpc_host          = "localhost"   ,
                 control_host      = "localhost"   ,
                 synchronous       = True          ,
                 debug_level       = -1
    ):
#------------------------------------------------------------------------------
# Initialize Component, the base class of FarmManager
# P.M.not sur why the base class is needed at all - nothing else inherits from it
#------------------------------------------------------------------------------
        Component.__init__(self,
                           name         = name,
                           odb_client   = odb_client,
                           rpc_host     = rpc_host,
                           control_host = control_host,
                           synchronous  = synchronous,
                           skip_init    = False)

        self.reset_variables()

        self.fUser                   = os.environ.get("USER");
        self.mu2e_daq_dir            = os.path.expandvars(self.client.odb_get('/Mu2e/MU2E_DAQ_DIR'));
        self.spackdir                = self.mu2e_daq_dir + '/spack'
        self.daq_setup_script        = os.path.expandvars(self.client.odb_get('/Mu2e/DaqSetupScript'))

        self.midas_server_host       = os.path.expandvars(self.client.odb_get("/Mu2e/ActiveRunConfiguration/DAQ/MIDAS_SERVER_HOST"));
        self.top_output_dir          = os.path.expandvars(self.client.odb_get("/Mu2e/OutputDir"));

        TRACE.TRACE(7,f'top_output_dir:{self.top_output_dir}',TRACE_NAME);
        self.log_directory           = self.top_output_dir+'/logs'        # None
        self.record_directory        = self.top_output_dir+'/run_records' # None
        self.data_directory_override = self.top_output_dir+'/data'        # None
        self.productsdir             = None

        self.fKeepRunning            = True
        self.transfer                = "Autodetect"
                                     
        self.config_name             = odb_client.odb_get("/Mu2e/ActiveRunConfiguration/Name")
        self.artdaq_config_dir       = artdaq_config_dir;
        self.config_dir              = artdaq_config_dir+'/'+self.config_name;

        
        self.daq_conf_path           = '/Mu2e/ActiveRunConfiguration/DAQ';
        self.tfm_conf_path           = '/Mu2e/ActiveRunConfiguration/DAQ/Tfm';
        self._cmd_path               = '/Mu2e/Commands/DAQ/Tfm';
        self.public_subnet           = odb_client.odb_get(self.daq_conf_path+'/PublicSubnet' )
        self.private_subnet          = odb_client.odb_get(self.daq_conf_path+'/PrivateSubnet')

        self.ports_per_partition     = 1000
        if (odb_client.odb_exists(self.tfm_conf_path+"/ports_per_partition")):
            self.ports_per_partition = odb_client.odb_get(self.tfm_conf_path+"/ports_per_partition");

        self.base_port_number        = 10000
        if (odb_client.odb_exists(self.tfm_conf_path+"/base_port_number")):
            self.base_port_number = odb_client.odb_get(self.tfm_conf_path+"/base_port_number");
              

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
        self.printlock              = threading.RLock()
        self.subconfigs_for_run     = []         # not sure what these are 

        self.messageviewer_sender   = None
        self.use_messageviewer      = bool(odb_client.odb_get(self.tfm_conf_path+"/use_messageviewer"))
        self.use_messagefacility    = bool(odb_client.odb_get(self.tfm_conf_path+"/use_messagefacility"))
        self.fake_messagefacility   = False
        self._validate_setup_script = odb_client.odb_get(self.tfm_conf_path+"/validate_setup_script")
#------------------------------------------------------------------------------
# move initialization from read_settings()
#-------v----------------------------------------------------------------------
        self.package_hashes_to_save              = []
        self.package_versions                    = {}
        self.productsdir_for_bash_scripts        = None
        self.max_fragment_size_bytes             = None

        self.ssh_timeout_in_seconds              = odb_client.odb_get(self.tfm_conf_path+"/ssh_timeout_in_seconds")# 30  ## was a local var somewhere
                                                
        self.boardreader_timeout                 = odb_client.odb_get(self.tfm_conf_path+"/boardreader_timeout")
        self.eventbuilder_timeout                = odb_client.odb_get(self.tfm_conf_path+"/eventbuilder_timeout")
        self.datalogger_timeout                  = odb_client.odb_get(self.tfm_conf_path+"/datalogger_timeout")
        self.dispatcher_timeout                  = odb_client.odb_get(self.tfm_conf_path+"/dispatcher_timeout")
        self.routingmanager_timeout              = odb_client.odb_get(self.tfm_conf_path+"/routingmanager_timeout")

        self.advanced_memory_usage               = bool(odb_client.odb_get(self.tfm_conf_path+"/advanced_memory_usage"))
        self.strict_fragment_id_mode             = bool(odb_client.odb_get(self.tfm_conf_path+"/strict_fragment_id_mode"))
        self.attempt_existing_pid_kill           = bool(odb_client.odb_get(self.tfm_conf_path+"/kill_existing_processes"))
        self.max_configurations_to_list          = 1000000
        self.disable_unique_rootfile_labels      = bool(odb_client.odb_get(self.tfm_conf_path+"/disable_unique_rootfile_labels"))
        self.disable_private_network_bookkeeping = bool(odb_client.odb_get(self.tfm_conf_path+"/disable_pn_bookkeeping"))
        self.allowed_processors                  = None

        self.max_num_launch_procs_checks         = odb_client.odb_get(self.tfm_conf_path+"/max_num_launch_procs_checks")
        self.launch_procs_wait_time              = odb_client.odb_get(self.tfm_conf_path+"/launch_procs_wait_time")
        self.debug_level                         = odb_client.odb_get(self.tfm_conf_path+"/debug_level")
        self.transfer                            = odb_client.odb_get(self.tfm_conf_path+"/transfer_plugin_to_use")
#------------------------------------------------------------------------------
# initialize artfaq subsystems and processes
#-------v----------------------------------------------------------------------
        self.init_artdaq_subsystems()
        self.init_artdaq_processes()
#------------------------------------------------------------------------------
# associate processes and subsystems
#-------v----------------------------------------------------------------------
        print('-------------------------- append processes to subsystems')
        for p in self.procinfos:
            print (f'p.rank:{p.rank} p.name:{p.name} p.type():{p.type()} p.subsystem:{p.subsystem}')
            s = self.subsystems[p.subsystem]
            s.print()
            # print('sss',s.list_of_procinfos);
            s.list_of_procinfos[p.type()].append(p);
            if (s.max_type < p.type()): s.max_type = p.type();
            if (s.min_type > p.type()): s.min_type = p.type();

        print('-------------------------- subsystems supposedly initialized')
        for s in self.subsystems.values():
            s.print()
#------------------------------------------------------------------------------
# for each process create lists of sources and destinations
# BR --> EB
#               lowest in the subsystem
# EB --> EB
# EB --> DL
#
# DL --> DS
#------------------------------------------------------------------------------
        print('-------------------------- init_process_connections')
        for p in self.procinfos:
            if (p.type() == BOARD_READER):
                self.init_br_connections(p);
            elif (p.type() == EVENT_BUILDER):
                self.init_eb_connections(p);
            elif (p.type() == DATA_LOGGER):
                self.init_dl_connections(p);
            elif (p.type() == DISPATCHER):
                self.init_ds_connections(p);
            elif (p.type() == ROUTING_MANAGER):    # shouldn't happen to us
                self.init_rm_connections(p);
#-------^----------------------------------------------------------------------
# at this point, each process knows about its sources and destinations
# so we can update the FCL file
# replaced should be lines with
# -- BR:
#         daq.fragment_receiver.destinations
# -- EB:
#         daq.event_builder.sources
#         art.outputs.*.destinations
#         art.outputs.*.host_map
# -- DL:
#         daq.aggregator.sources
#         art.outputs.*.destinations
#         art.outputs.*.host_map
# -- DS:
#         daq.aggregator.sources
#
# don't forget about smth max_fragment_size_bytes....
# want to print what we got
#-------v----------------------------------------------------------------------
        print(f'----------- AAA processed self.procinfos: print sources and destinations')
        for p in self.procinfos:
            print(f'p.subsystem:{p.subsystem} p.rank:{p.rank} p.label:{p.label}')
            if (p.list_of_sources == None):
                print('  -- sources: None');
            else:
                print('  -- sources:')
                for p1 in p.list_of_sources:
                    p1.print();

            if (p.list_of_destinations == None):
                print('  -- destinations: None');
            else:
                print('  -- destinations:')
                for p1 in p.list_of_destinations:
                    p1.print();

        print(f'----------- excersize printing the host_map')
        s = artdaq.host_map_string(self.procinfos,'')
        print(f'{s}')
#------------------------------------------------------------------------------
# now update fcls - to decouple that code, need to pass the transfer plugin
# and the output directory name
#------------------------------------------------------------------------------
        tmp_dir = f'/tmp/partition_{self.partition()}/{self.config_name}'
        for p in self.procinfos:
#            self.update_fhicl(p);
            artdaq.update_fhicl(p,self.transfer,tmp_dir);
        
#------------------------------------------------------------------------------
# P.M. so far, intentionally, handle only one source and one destination - haven't 
#      seen any configuration with a subsystem having two sources. 
#      however, 'sources is an array, so this may need to be changed
#------------------------------------------------------------------------------            
              
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
#-------v----------------------------------------------------------------------
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
            TRACE.TRACE(7,f"An exception was thrown when trying to read FarmManager settings;","FarmManager")
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

        self.print_log("i",'FarmManager lanched in partition %d and now in "%s" state, listening on port %d'
                       % (self.partition(),self.state(),self.rpc_port())
        )
#------------------------------------------------------------------------------
# P.M. if debug_level is defined on the command line, override the config file settings
#------------------------------------------------------------------------------
        if (debug_level >= 0): self.debug_level = debug_level


    def __del__(self):
        Component.__del__(self);
        # rcu.kill_tail_f()
        
#------------------------------------------------------------------------------
# global actor functions
#---v--------------------------------------------------------------------------
#    get_config_info                       = get_config_info_base
#    put_config_info                       = put_config_info_base
#    put_config_info_on_stop               = put_config_info_on_stop_base
#    listconfigs                           = listconfigs_base
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
#---v--------------------------------------------------------------------------
    def do_trace_get(self, name=None):
        if name is None: name = self.run_params["name"]

        self.print_log("d",'%s: do_trace_get has been called with name "%s"' % (rcu.date_and_time(), name),3)

#------------------------------------------------------------------------------
# P.Murat: 'p' is the Procinfo structure
#-------v----------------------------------------------------------------------
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
#-------v----------------------------------------------------------------------
        output = ""
        for p in self.procinfos:
            fn = "/tmp/trace_get_%s_%s_partition%d.txt" % (p.label,self.fUser,self.partition())
            with open(fn) as inf:
                output += "\n\n%s:\n" % (p.label)
                output += inf.read()

        return output
#------------------------------------------------------------------------------
# TRACE set
#---v--------------------------------------------------------------------------
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
#---v--------------------------------------------------------------------------
    def alert_and_recover(self, extrainfo=None):
        self.print_log('i','-- START');
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
        self.print_log('i','-- END');
        return
#------------------------------------------------------------------------------
# one day, this will go away and the initialization will become an execution 
# of a python script. Expand env vars right away
# 2024-12-23 P.Murat: start using ODB
#   there is no practical need to have a freedom of placing different kinds
#   of output directories in random places
#---v--------------------------------------------------------------------------
    def read_settings(self):

        for subdir in [self.log_directory, self.record_directory, self.data_directory_override]:
            if (not os.path.exists(subdir)): os.makedirs(subdir)
            if (subdir == self.record_directory):
#------------------------------------------------------------------------------
# P.M. as a matter of some kind of [inherited] safety, add the dot file.. 
#      ... not sure what kind of safety that is
#      the dot file, '.record_directory_info', contains the number of the first 
#      directory inode 
#------------------------------------------------------------------------------
                inode = os.stat(subdir).st_ino
                fn    = subdir+'/.record_directory_info'
                with open(fn,"w") as f: f.write("inode: %s" % inode);
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
                    ("Since advanced_memory_usage is set to true "
                    "max_fragment_size_bytes must NOT be set (i.e., delete it or comment it out)")
                )
            )

        if len(missing_vars) > 0:
            missing_vars_string = ", ".join(missing_vars)
            print
            raise Exception(
                rcu.make_paragraph(
                    "Unable to parse the following variable(s) meant to be set in the "
                    % (": " + missing_vars_string)
                )
            )

        if not self.advanced_memory_usage and not self.max_fragment_size_bytes:
            raise Exception(
                rcu.make_paragraph(
                    "max_fragment_size_bytes isn't set."
                    "It needs to be set since advanced_memory_usage isn't set to true"
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
                     'are defined in %s; this is not allowed. For further information, ')
                )
            )

        if self.boardreader_priorities is not None:
            self.boardreader_priorities_on_config = self.boardreader_priorities
            self.boardreader_priorities_on_start = self.boardreader_priorities
            self.boardreader_priorities_on_stop = self.boardreader_priorities

#-------v----------------------------------------------------------------------
        TRACE.TRACE(7,":002: before check_boot_info",TRACE_NAME)
        self.check_boot_info()
        return
#------------------------------------------------------------------------------
#
#---v--------------------------------------------------------------------------
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
#---v------------------------------------------------------------------------------
    def artdaq_mfextensions_info(self):

        assert self.have_artdaq_mfextensions()

        cmds = []
        cmds += rcu.get_setup_commands(self.productsdir, self.spackdir)
        cmds.append(". %s for_running" % (self.daq_setup_script))
        cmds.append(
            ('if [ -n "$SETUP_ARTDAQ_MFEXTENSIONS" ]; then printenv SETUP_ARTDAQ_MFEXTENSIONS; '
             'else echo "artdaq_mfextensions $ARTDAQ_MFEXTENSIONS_VERSION $MRB_QUALS";fi ')
        )

        proc = subprocess.Popen(";".join(cmds),executable="/bin/bash",shell=True,
                                stdout=subprocess.PIPE,stderr=subprocess.STDOUT)

        proclines     = proc.stdout.readlines()

        printenv_line = proclines[-1].decode("utf-8")
        version       = printenv_line.split()[ 1]
        qualifiers    = printenv_line.split()[-1]

        return (version, qualifiers)
#------------------------------------------------------------------------------
# WK 8/31/21
# refactor out launching the message viewer into a function
# and make that function run in the background
# return a proc that can be polled.
#---v--------------------------------------------------------------------------
    def launch_msgviewer(self):
        cmds            = []
        port_to_replace = 30000
        msgviewer_fhicl = "/tmp/msgviewer_partition%d_%s.fcl" % (self.partition(),self.fUser)
        cmds           += rcu.get_setup_commands(self.productsdir, self.spackdir)
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

        if self.exception: return

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

        if self.daq_setup_script is None: 
            raise Exception(rcu.make_paragraph('Error: self.daq_setup_script undefined'))

        if self.debug_level == 0:
            self.print_log("w",rcu.make_paragraph(
                ('"debug_level" is set to 0; while this isn\'t an error '
                 'due to reasons of backwards compatibility, use of this debug level is highly discouraged')
                )
            )

        if not os.path.exists(self.daq_setup_script):
            raise Exception(self.daq_setup_script + " script not found")

        num_requested_routingmanagers = len([p.name for p in self.procinfos if p.name == "RoutingManager" ])

        if num_requested_routingmanagers > len(self.subsystems):
            raise Exception(rcu.make_paragraph(
                ("%d RoutingManager processes defined ; "
                 "you can't have more than the number of subsystems (%d)")
                % (num_requested_routingmanagers, len(self.subsystems)))
            )
#------------------------------------------------------------------------------
# print procinfos if debug level >= 2
#------------------------------------------------------------------------------
        if (self.debug_level >= 2):
            for p in self.procinfos: p.print()

        if len(set([procinfo.label for procinfo in self.procinfos])) < len(self.procinfos):
            raise Exception(rcu.make_paragraph(
                    ("At least one of your desired artdaq processes has a duplicate label; "
                     "please ensure that each process gets a unique label"))
            )

#------------------------------------------------------------------------------
# print subsystems if debug level >= 2
#------------------------------------------------------------------------------
        if (self.debug_level >= 2):
            for key in self.subsystems.keys(): self.subsystems[key].print()

        for ss in self.subsystems:                       # ss is a string (key)
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
#-----------v------------------------------------------------------------------
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
#-----------v------------------------------------------------------------------
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
#
#---v--------------------------------------------------------------------------
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
#---v--------------------------------------------------------------------------
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

        self.print_log("d","Sending transition %s to %s" % (command, p.label),3)

        try:
            if command == "Init":
                # breakpoint()
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

            self.print_log("d",f"farm_manager::process_command p.pastreturned:\n{p.lastreturned}",3)
                
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

        self.print_log("d",f"returning from process_command {command} for {p.label}",3)
        
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
        func_name = 'do_command'

###        self.print_log('d',f'-- {func_name} START: command:{command}')

        if command != "Start" and command != "Init" and command != "Stop":
            self.print_log("i", "%s transition underway" % (command.upper()))
#------------------------------------------------------------------------------
# JCF, Nov-8-2015

# In the code below, transition commands are sent simultaneously only to classes 
# of artdaq type. So, e.g., if we're stopping, first we send stop to all the boardreaders,
# next we send stop to all the eventbuilders, and finally we send stop to all the aggregators

# ELF, Jul-17-2020
# I've modified this code to do what John says above, but also in subsystem order
#-------v----------------------------------------------------------------------
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
#------------------------------------------------------------------------------
# which leaves 'Init', 'Start', 
#-----------v------------------------------------------------------------------
            subsystems_in_order.reverse()
        
        starttime = time.time()
        # self.print_log("i","[farm_manager::do_command(%s)]: sending transition to artdaq processes" % (command.upper()),1)
        TRACE.INFO(f'sending command:{command.upper()} to ARTDAQ processes',TRACE_NAME);

        proc_starttimes = {}
        proc_endtimes   = {}
        for subsystem in subsystems_in_order:
            TRACE.DEBUG(0,f'subsystem:{subsystem}',TRACE_NAME);
            for proctype in proctypes_in_order:
                TRACE.DEBUG(0,f'proctype:{proctype}',TRACE_NAME);
                priorities_used = {}

                for p in self.procinfos:
                    TRACE.DEBUG(0,f'  p.name:{p.name} p.label:{p.label} p.priority:{p.priority} p.subsystem:{p.subsystem}',TRACE_NAME);
                    if proctype in p.name and p.subsystem == subsystem:
                        priorities_used[p.priority] = p

                priority_rankings = sorted(priorities_used.keys())
                TRACE.DEBUG(0,f'priority_rankings:{priority_rankings}',TRACE_NAME);

                for priority in priority_rankings:
                    proc_threads = {}
                    for p in self.procinfos:
                        TRACE.DEBUG(0,f'p:{p.name}',TRACE_NAME);
                        if (proctype in p.name and priority == p.priority and p.subsystem == subsystem):
                            t = rcu.RaisingThread(target=self.process_command, args=(p,command))
                            proc_threads   [p.label] = t
                            proc_starttimes[p.label] = time.time()
                            t.start()

                    TRACE.DEBUG(0,'printing proc_threads',TRACE_NAME)
                    print(f'proc_threads:{proc_threads}')
                    
                    for label in proc_threads:
                        proc_threads[label].join()
                        proc_endtimes[label] = time.time()

        if self.exception:
            raise Exception(rcu.make_paragraph("An exception was thrown during the %s transition." % (command)))

        # time.sleep(1)  # PM : is sleep really needed ? - try to turn it off

        endtime = time.time()
        self.print_log("i", "[farm_manager::do_command(%s)]: done in %.1f seconds." 
                       % (command.upper(),endtime - starttime))

        nfailed = len([p for p in self.procinfos if p.lastreturned != "Success" ])

        TRACE.DEBUG(0,f'nfailed:{nfailed} self.debug_level:{self.debug_level}',TRACE_NAME)
        if ((self.debug_level >= 2) or (nfailed > 0)):
            
            for p in self.procinfos:
                if (self.debug_level > 0): p.print()
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

            self.print_log("i","Longest individual transition: %s, %.1f seconds." % (slowest_process, max_time))
            self.print_log("i",'All artdaq processes returned SUCCESS.')

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
            self.print_log("i", "farm_manager::do_command: %s transition complete" % (command.upper()))

        return
#-------^----------------------------------------------------------------------
# not sure why this is needed - in case of failure, it is not always obvious 
# what are the recovery actions to take
#---v--------------------------------------------------------------------------
    def revert_failed_transition(self, failed_action):
        self.revert_state_change(self.name, self.state())
        self.print_log("e", (traceback.format_exc()))
        self.print_log("e",
            rcu.make_paragraph(
                'An exception was thrown when %s; exception has been caught and system remains in the "%s" state'
                % (failed_action, self.state())
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
                                 ' used to rank transition priorities'
                                 )
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
                if (not inf.read().strip() == rcu.record_directory_info(self.record_directory)):
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
        return
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
                                'Unable to find fhiclcpp ups product in products directory "%s" '
                                % (self.productsdir)
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
        rcu.obtain_messagefacility_fhicl(self)

        self.print_log("i", "%s::do_fhiclcpp_stuff 001" %(__file__),2)

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

        self.print_log("d", "%s:do_fhiclcpp_stuff 002" % (__file__),2)
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
#       get_lognames : returns 0 in case of success, -1 otherwise
#---v--------------------------------------------------------------------------
    def get_lognames(self):
        starttime = time.time()
        self.print_log("i","[farm_manager::get_lognames]: determining logfiles associated with the artdaq processes",1) 
        try:
            self.process_manager_log_filenames = self.get_process_manager_log_filenames()
            self.get_artdaq_log_filenames()

        except Exception:
            self.print_log("e", traceback.format_exc())
            self.alert_and_recover("Unable to find logfiles for at least some of the artdaq processes")
            return -1;

        endtime = time.time()
        self.print_log("i", "[farm_manager::get_lognames]: done (%.1f seconds)." % (endtime - starttime))
        return 0;  # end of get_lognames

#------------------------------------------------------------------------------
# P.Murat: make_logfile_dirs is a well-defined action - make it a separate function
#          pmt is the only one left ..
#---v--------------------------------------------------------------------------
    def make_logfile_dirs(self):
        logdir_commands_to_run_on_host = []
        permissions                    = "0775"
        logdir_commands_to_run_on_host.append("mkdir -p -m %s %s" % (permissions, self.log_directory))

        for subdir in ["pmt"]:
            logdir_commands_to_run_on_host.append(
                "mkdir -p -m %s %s/%s" % (permissions, self.log_directory, subdir)
            )

        for host in set([p.host for p in self.procinfos]):
            logdircmd = rcu.construct_checked_command(logdir_commands_to_run_on_host)

            if not rcu.host_is_local(host):
                logdircmd = "timeout %d ssh -K -f %s '%s'" % (self.ssh_timeout_in_seconds,host,logdircmd)

            self.print_log("i", "farm_manager::make_logfile_dirs 004")
            self.print_log("d", "farm_manager::make_logfile_dirs executing:\n%s" % (logdircmd),2)

            proc = subprocess.Popen(
                logdircmd,
                executable="/bin/bash",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
            )
            self.print_log("i", "farm_manager::make_logfile_dirs: done with mkdirs",2)

            out, err = proc.communicate()
            status   = proc.returncode

            if status != 0:

                self.print_log(
                    "e",
                    "\nNonzero return value (%d) resulted when trying to run the following on host %s:\n%s\n"
                    % (status, host, "\n".join(logdir_commands_to_run_on_host)),
                )
                self.print_log("e","farm_manager::make_logfile_dirs: STDOUT output: \n%s" % (out))
                self.print_log("e","farm_manager::make_logfile_dirs: STDERR output: \n%s" % (err),
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

#-------^----------------------------------------------------------------------
# may be needed ???
#---v--------------------------------------------------------------------------
    def listconfigs(self):
        subdirs = next(os.walk(self.get_config_parentdir()))[1]
        configs = [subdir for subdir in subdirs if subdir != "common_code"]
    
        listconfigs_file = "/tmp/listconfigs_" + os.environ["USER"] + ".txt"
    
        outf = open(listconfigs_file, "w")
    
        print("\nAvailable configurations: ")
        for config in sorted(configs):
            print(config)
            outf.write("%s\n" % config)
    
        print('\nSee file "%s" for saved record of the above configurations' % (listconfigs_file))
        print(rcu.make_paragraph(
            "Please note that for the time being, the optional max_configurations_to_list variable "
            "is only applicable when working with the database")
        )
    
        # print(flush=True)
        sys.stdout.flush()

#-------^----------------------------------------------------------------------
# starting from this point, perform run-dependent configuration
# look at the FCL files - they need to be looked at before the processes are launched
# See Issue #20803.
# the idea is that, e.g., component01.fcl and component01_hw_cfg.fcl refer to the same thing
# P.M. it looks that it takes all fcl files from the config directory and checks them....
#---v--------------------------------------------------------------------------
    def check_hw_fcls(self):

        starttime = time.time()
            
        rootfile_cntr = 0
        
        TRACE.INFO(f'-- START',TRACE_NAME)
#------------------------------------------------------------------------------
# it looks that here we're checking availability of the FCL files for the processes 
# which are already running ? is the idea that one would re-upload the FCL files?
# self.config_dir contains only FCL files 
#-------v------------------------------------------------------------------------------
        for p in self.procinfos:
            if not self.disable_unique_rootfile_labels and ("EventBuilder" in p.name or "DataLogger" in p.name):
                fhicl_before_sub     = p.fhicl_used
                rootfile_cntr_prefix = "dl"
                p.fhicl_used         = re.sub(r"(\n\s*[^#\s].*)\.root",r"\1" + "_dl" + str(rootfile_cntr + 1) + ".root",p.fhicl_used)

                if p.fhicl_used != fhicl_before_sub:
                    rootfile_cntr += 1

        endtime = time.time()
        self.print_log("i", "CONFIG transition 002: step lasted (%.1f seconds)." % (endtime - starttime))

        return 0  # end of function

#------------------------------------------------------------------------------
# do_boot(), do_config(), do_start_running(), etc., are the functions 
# which get called by the runner() function when a transition is requested
# boot just once, at the initialization stage, 
# everything else goes into config
#---v--------------------------------------------------------------------------
    def do_boot(self):
#------------------------------------------------------------------------------
# P.Murat: why a nested function - to hide the name ?
#-------v----------------------------------------------------------------------
        def revert_failed_boot(failed_action):
            self.reset_variables()
            self.revert_failed_transition(failed_action)

        self.print_log("i", "do_boot: BOOT transition underway, debug_level=%i" % (self.debug_level))

        self.fState = run_control_state.transition("init");
        self.fState.set_completed(0);
#------------------------------------------------------------------------------
# See the Procinfo.__lt__ function for details on sorting
#-------v----------------------------------------------------------------------
        self.procinfos.sort()

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
        self.print_log("i", "BOOT transition 001 : start msg viewer")

        self.msgviewer_proc = None  # initialize
        if self.use_messageviewer:
            self.start_message_viewer()

        self.print_log("i", "BOOT transition 002 : done with msg viewer")

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
# P.Murat: it is ok to validate the setup script once in a while,
#          however doing that every time could be an overkill:
#          on a scale of transition times, the check is rather time consuming
#-------v----------------------------------------------------------------------
        if self.manage_processes:
            hosts        = [procinfo.host for procinfo in self.procinfos]
            random_host  = random.choice(hosts)

            if (self._validate_setup_script):
                self.validate_setup_script(random_host)

            self.print_log("i", "BOOT transition 003 : done checking setup script")
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
            self.print_log("i", "BOOT transition 004: before init_process_requirements",2)
            self.init_process_requirements()
            self.print_log("i", "BOOT transition 005: after init_process_requirements" ,2)
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
        self.print_log("i", "BOOT transition complete")
#------------------------------------------------------------------------------
# to preserve formal logic: transition completes, then the state changes
#-------v----------------------------------------------------------------------
        self.fState.set_completed(100);
        time.sleep(1);
        self.fState = run_control_state.state("stopped")
        return

#------------------------------------------------------------------------------
# CONFIG transition : 1) at this point the run number is already known, don't need to pass
#---v--------------------------------------------------------------------------
    def do_config(self, subconfigs_for_run=[], run_number=None):

        self.fState = run_control_state.transition("configure")

#------------------------------------------------------------------------------
# check subconfigs for this run - what they are? 
# could this be done before launching the jobs ?
# last segment of the self.config_dir is the config name
# not sure what it is used for...
#-------v----------------------------------------------------------------------
        if subconfigs_for_run: 
            self.subconfigs_for_run = subconfigs_for_run
        else:
            self.subconfigs_for_run = [ os.path.basename(self.config_dir) ]

        # self.subconfigs_for_run.sort()

        if not run_number: self.run_number = self.run_params["run_number"]
        else             : self.run_number = run_number

        self.print_log("i", "CONFIG transition underway run_number:%06d config name: %s" % 
                       (self.run_number," ".join(self.subconfigs_for_run)))
        msg = f'CONFIG transition underway: run_number:{self.run_number} config_name:{" ".join(self.subconfigs_for_run)}'
        TRACE.INFO(msg,TRACE_NAME)             
#------------------------------------------------------------------------------
# what this is needed for ? - to ensure that check_hw_fcls operates in a known directory ?
#------------------------------------------------------------------------------
        os.chdir(self.base_dir)
#------------------------------------------------------------------------------
# starting from this point, perform run-dependent configuration
# look at the FCL files - they need to be looked at before the processes are launched
# See Issue #20803.  Idea is that, e.g., component01.fcl and component01_hw_cfg.fcl 
# refer to the same thing P.Murat: checks in check_hw_fcls look like nonsense - it costs nothing to keep the fcl files unique
#-------v------------------------------------------------------------------------------
        rc = self.check_hw_fcls();
        if (rc != 0): return 

        starttime = time.time()
        TRACE.INFO("Reformatting FHiCL documents...", TRACE_NAME)
        # breakpoint()
        try:
            self.create_setup_fhiclcpp_if_needed()
        except:
            raise
#------------------------------------------------------------------------------
# P.Murat: TODO
# is this an assumption that reformatted FCL's and processes make two parallel lists,
# so one could use the same common index to iterate ?
# doesn't seem to be needed...
#-------v----------------------------------------------------------------------
        rcu.reformat_fhicl_documents(os.environ["TFM_SETUP_FHICLCPP"], self.procinfos)

        self.print_log("i", "CONFIG transition 007: reformatting FHICL done (%.1f seconds)." % (time.time() - starttime),2)

        starttime = time.time()
        self.print_log("i", "CONFIG transition 008: bookkeeping the FHiCL documents...", 2)

        try:
            self.bookkeeping_for_fhicl_documents()
        except Exception:
            self.print_log("e", traceback.format_exc())
            self.alert_and_recover(
                "An exception was thrown when performing bookkeeping on the process "
                "FHiCL documents; see traceback above for more info"
            )
            return

        self.print_log("i", "CONFIG transition 009: bookkeeping done (%.1f seconds)." % (time.time() - starttime))
#------------------------------------------------------------------------------
# P.Murat: it doesn't make sense to submit the jobs before FCL's are reformatted, does it ?
#          now, with the info on hand about the processes contained in procinfos, actually launch them
#          this needs to be done every time
#-------v----------------------------------------------------------------------
        TRACE.INFO("CONFIG transition 010: before self.launch_procs",TRACE_NAME)
        self.called_launch_procs = True
        self.launch_procs_time   = time.time()  # Will be used when checking logfile's timestamps

        start_time = time.time();
        try:
#------------------------------------------------------------------------------
# this is where the processes are launched - 
#-----------v------------------------------------------------------------------
            # breakpoint()
            launch_procs_actions = self.launch_procs()

            assert type(launch_procs_actions) is dict, rcu.make_paragraph(
                ("The launch_procs function needs to return a dictionary whose keys are the names of the hosts"
                 " on which it ran commands, and whose values are those commands"))

        except Exception:
            self.print_log("e", traceback.format_exc())
            self.alert_and_recover("An exception was thrown in launch_procs(), see traceback above for more info")
            return

        self.print_log("i", "CONFIG transition 011 : done, launching processes took %f sec" % 
                       (time.time()-start_time))
#------------------------------------------------------------------------------
# start checking if the launch was successful
#-------v----------------------------------------------------------------------
        rc = self.check_launch_results();
        if (rc != 0): return;

#         self.print_log("i", "CONFIG transition 012: before create_time_server_proxy")
# 
#         rc = self.create_time_server_proxy();
#         if (rc != 0): return;

        self.print_log("i", "CONFIG transition 013: before self.manage_processes")
#------------------------------------------------------------------------------
# define names of all logfiles
#-------v----------------------------------------------------------------------
        rc = self.get_lognames();
        if (rc != 0): return;
#------------------------------------------------------------------------------
# dealing with the run records, probably, after the submission
#-------v----------------------------------------------------------------------
        self.tmp_run_record = "/tmp/run_record_attempted_%s/%d" % (self.fUser,self.partition())

        self.print_log("i", f"CONFIG transition 014: self.tmp_run_record={self.tmp_run_record}")

        self.semipermanent_run_record = "/tmp/run_record_attempted_%s/%s" % (self.fUser,
                                                                             datetime.now().strftime("%Y-%m-%d-%H:%M:%S.%f"))
        assert not os.path.exists(self.semipermanent_run_record)

        if os.path.exists(self.tmp_run_record): shutil.rmtree(self.tmp_run_record)

        self.print_log("i", "CONFIG transition 015: saving the run record", 1)
        starttime = time.time()

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

        self.print_log("i", "CONFIG transition 0151: save_run_record() done in %.1f seconds" % (time.time() - starttime))

        try:
            self.check_config()
        except Exception:
            self.print_log("w", traceback.format_exc())
            self.revert_failed_transition("calling experiment-defined function check_config()")
            return

        self.print_log("i", "CONFIG transition 016")
#------------------------------------------------------------------------------
# sending 'Init' command to artdaq processes - at this point they should be already submitted
# insert the last part of former do_boot right above
#-------v----------------------------------------------------------------------
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

            self.print_log("i","Ensuring FHiCL documents will be archived in the output *.root files",2)

            labeled_fhicl_documents = []

            for p in self.procinfos:
                labeled_fhicl_documents.append((p.label,re.sub("'", '"', p.fhicl_used)))
#------------------------------------------------------------------------------
# at this point, metadata.txt shall exist in self.tmp_run_record
#------------------------------------------------------------------------------
            self.archive_documents(labeled_fhicl_documents)

            endtime = time.time()
            self.print_log("i", "CONFIG transition: archiving documents done (%.1f seconds)." % (endtime - starttime))

        self.complete_state_change("configuring")
        self.fState.set_completed(90);

        self.print_log("i", "CONFIG transition 017",2)

        if self.manage_processes:
            self.print_log("i", ("Process manager logfiles:\n%s" 
                                 % (", ".join(self.process_manager_log_filenames))),2)
#------------------------------------------------------------------------------
# -- it loooks, that at this point all book-keeping and checks are done and one can submit 
#    the jobs and name the log files
#    and this is the end of the config step - run number is known ! 
#-------v----------------------------------------------------------------------
        self.fState.set_completed(99);
        # time.sleep(1)
        self.fState = run_control_state.state("configured")

        self.print_log("i", "CONFIG transition 018: completed")
        return

#------------------------------------------------------------------------------
# START transition
# self.run_number already defined at the config step
#---v--------------------------------------------------------------------------
    def do_start_running(self):

        self.print_log("i","START transition underway for run %06d" % (self.run_number))
        # breakpoint()
        self.fState = run_control_state.transition("start")

        self.check_run_record_integrity()
        self.set_stop_requested(False);
#------------------------------------------------------------------------------
# step X) put_config_info - this does nothing
#-------v------------------------------------------------------------------------------
#         self.print_log("i", "START transition 001: before put_config_info")
# 
#         try:
#             self.put_config_info()
#         except Exception:
#             self.print_log("e", traceback.format_exc())
#             self.alert_and_recover(
#                 "An exception was thrown when trying to save configuration info; see traceback above for more info"
#             )
#             return
#------------------------------------------------------------------------------
# start TRACE ??? (__file__)
#-------v----------------------------------------------------------------------
        self.print_log("i","START transition 002: [farm_manager::do_start_running]: before execute_trace_script")

        self.execute_trace_script("start")

        self.print_log("i","START transition 003: [farm_manager::do_start_running] self.manage_processes=%i" % 
                       (self.manage_processes))

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
# P.Murat: the original gave one more example of how not to program in Python
#------------------------------------------------------------------------------
        start_time = datetime.now(timezone.utc).strftime("%a %b  %-d %H:%M:%S %Z %Y");

        self.print_log("i", "START transition 004: record_directory:%s run_number: %06d" 
                       % (self.record_directory,self.run_number))

        self.save_metadata_value("FarmManager start time",start_time);
        self.print_log("i", "Run info can be found locally at %s" % (self.run_record_directory()))

        self.complete_state_change("starting")
#------------------------------------------------------------------------------
# to preserve formal logic: transition completes, then the state changes
#-------v----------------------------------------------------------------------
        self.fState.set_completed(100);
        # time.sleep(1);   # PM : I inserted that, was that really needed ? 
        self.fState = run_control_state.state("running")

        self.print_log("i","START transition 005: complete, run=%d" % (self.run_number))
        return
#------------------------------------------------------------------------------
# STOP the run
#---v--------------------------------------------------------------------------
    def do_stop_running(self):
        self.print_log('i',f'-- START: STOP transition run:{self.run_number}')

        self.fState = run_control_state.transition("stop")
        self.fState.set_completed(0);
        run_stop_time = datetime.now(timezone.utc).strftime("%a %b  %-d %H:%M:%S %Z %Y");
        self.save_metadata_value("FarmManager stop time",run_stop_time);

        self.stop_datataking()

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

        self.print_log('i','after do_command("Stop")')
        self.execute_trace_script ("stop"    )
        self.complete_state_change("stopping")
        self.fState.set_completed(50);
#------------------------------------------------------------------------------
# ARTDAQ processes stopped, query the number of events in the run, start from the data logger(s)
#------------------------------------------------------------------------------
        
#------------------------------------------------------------------------------
# P.M. moved from the runner loop
#-------v----------------------------------------------------------------------
        self.print_log('i','before do_command("Shutdown")')
        self.do_command("Shutdown")
        self.print_log('i','after do_command("Shutdown")')
#------------------------------------------------------------------------------
# to preserve formal logic: transition completes, then the state changes
#-------v----------------------------------------------------------------------
        self.fState.set_completed(100);
        time.sleep(1);
        self.fState = run_control_state.state("stopped")

        self.print_log("i","-- END: STOP transition run=%06d" % (self.run_number))
        return
#------------------------------------------------------------------------------
#  SHUTDOWN transition - complete everything and exit
#---v--------------------------------------------------------------------------
    def do_shutdown(self):
        self.print_log("i",f'-- START: run:{self.run_number:06d}')

        if (self.fState.get_name() == "stopped"):
            self.fKeepRunning = False
        else:
            self.print_log('i',f'ERROR: state:{self.fState.get_name()}')

        self.print_log("i",f'-- END: run:{self.run_number:06d}')
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
            self.print_log("i", "%s::do_terminate: done (%.1f seconds)." % (_-file,endtime - starttime),2)

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
                self.print_log("i", 'All artdaq processes returned "Success".')

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
#-------^----------------------------------------------------------------------
# RECOVER transition
#---v--------------------------------------------------------------------------
    def do_recover(self):
        run_number_string = f" for run {self.run_number}" if self.run_number else ""
        self.print_log('i',f'{rcu.date_and_time()}: -- START: RECOVER transition, run:{run_number_string}')

        self.in_recovery = True

        if not self.called_launch_procs:
            self.print_log("i","FarmManager does not appear to have gotten to the point of launching the artdaq processes")

        if self.disable_recovery or not self.called_launch_procs:
            self.print_log("i","Skipping cleanup of artdaq processes, this recover step is effectively a no-op")

            self.in_recovery = False
            self.complete_state_change("recovering")
            self.print_log("i","\n%s: RECOVER transition complete %s"%(rcu.date_and_time(),run_number_string))
            return

        if self.state() == "running" or self.state() == "stopping":
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
                if (self.state() != "stopped" and 
                    self.state() != "booting" and 
                    self.state() != "terminating"): self.print_log("e", rcu.make_paragraph(msg))
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
                self.print_log("i","Attempting to cleanly wind down the %ss if they (still) exist"%(name))

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
            self.print_log("i","Attempting to kill off the artdaq processes from this run if they still exist")
            try:
                self.kill_procs()
            except Exception:
                self.print_log("e", traceback.format_exc())
                self.print_log("e",rcu.make_paragraph(
                        ("An exception was thrown within kill_procs(); artdaq processes may not all have been killed"))
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
        self.print_log("i","%s: RECOVER transition complete%s"%(rcu.date_and_time(),run_number_string))
        return

#------------------------------------------------------------------------------
# tfm::artdaq_process_info
#---v--------------------------------------------------------------------------
    def artdaq_process_info(self, name):

        try:
            self.procinfos
        except:
            return self.state()  # OK if we haven't yet created the list of Procinfo structures
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
                and self.state() != "stopped"
                and self.state() != "booted"
                and self.state() != "configuring"
                and self.state() != "terminating"
            ):
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

    parser = argparse.ArgumentParser(description="FarmManager")

    parser.add_argument("-n","--name"        ,type=str,dest="name"        ,default="daqint"   ,help="Component name")
    parser.add_argument("-H","--rpc-host"    ,type=str,dest="rpc_host"    ,default="localhost",help="this hostname/IP addr")
    parser.add_argument("-c","--control-host",type=str,dest="control_host",default="localhost",help="Control host")
    parser.add_argument("-d","--debug-level" ,type=int,dest="debug_level" ,default=-1         ,help="debug level, default=-1")
    parser.add_argument("-D","--config-dir"  ,type=str,dest="config_dir"  ,default=None       ,help="config dir"  )

    return parser.parse_args()

#------------------------------------------------------------------------------
# main
#------------------------------------------------------------------------------
def main():  # no-coverage

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
        while tfm.state() != "stopped":
            if int(time.time() - starttime) > timeout:
                tfm.print_log(
                    "e",
                    ("FarmManager signal handler recovery attempt timed out after %d seconds; "
                    "FarmManager is in the %s state rather than the stopped state")
                    % (timeout,tfm.state()),
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
