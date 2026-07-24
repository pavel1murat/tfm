#!/bin/env/python

import os, sys, argparse, glob, inspect, re, subprocess
import tfm.rc.control.utilities as rcu

from   tfm.rc.control.procinfo  import Procinfo, BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ;
from   pathlib                  import Path
from   datetime                 import datetime
from   zoneinfo                 import ZoneInfo

import TRACE ; TRACE_NAME='artdaq'

#------------------------------------------------------------------------------
# takes a template FCL file from config/artdaq/common/$template,
# adds information read from ODB (at this point stored in the process record 'proc')
# and writes output FCL file to config/artdaq/$config_name/
# in addition, overrides EB parameters by reading ODB
#------------------------------------------------------------------------------
def write_fcl(run_conf_name,client,args,artdaqLabel,proc,fcl_template):

    config_dir  = os.path.expandvars(client.odb_get('/Mu2e/ConfigDir'));
    template_fn = config_dir+f'/artdaq/common/{fcl_template}.fcl'

    TRACE.INFO(f'-- START: fcl_template:{fcl_template} config_dir:{config_dir} template_fn:{template_fn}',TRACE_NAME);

    
    output_dir = config_dir+f'/artdaq/{run_conf_name}'
    fn         = f'{output_dir}/{artdaqLabel}.fcl'

    TRACE.INFO(f'output_dir:{output_dir} fn:{fn}',TRACE_NAME);
#------------------------------------------------------------------------------
# read in the template FCL
#------------------------------------------------------------------------------
    lines = []
    with open(template_fn) as f:
        lines = f.readlines()

        TRACE.INFO(f'len(lines): {len(lines)}',TRACE_NAME);
#------------------------------------------------------------------------------
# for different templates, add different things 
#-------v----------------------------------------------------------------------
    if   (fcl_template == 'tracker_brdr'):
        with open(fn,'w') as fout:
            for line in lines:
                fout.write(line);

        # and append 
        with open(fn,'a') as fout:
            fout.write(f'daq.fragment_receiver.artdaqLabel  : {artdaqLabel}\n');
            fout.write(f'daq.fragment_receiver.fragment_ids : [ {proc["fragment_ids"]} ]\n');
                
    elif (fcl_template == 'mu2e_subevent_receiver'):
        with open(fn,'w') as fout:
            for line in lines:
                if (re.search(r'\s*daq.fragment_receiver.fragment_id\s*:',line)):
                    # this one takes only one fragment, so fragment_ids should be one ID
                    fout.write(f'daq.fragment_receiver.fragment_id : {proc["fragment_ids"]}\n' );
                    continue

                if (re.search(r'\s*daq.fragment_receiver.dtc_id\s*:',line)):
                    # it also needs the DTC_ID
                    odb_path = proc["DTC"]
                    TRACE.INFO(f'odb_path: {odb_path}',TRACE_NAME);
                    pcie_addr = client.odb_get(odb_path+'/PcieAddress')
                    fout.write(f'daq.fragment_receiver.dtc_id : {pcie_addr}\n' );
                    continue
                
                fout.write(line);

#------------------------------------------------------------------------------
# CFO reader
#------------------------------------------------------------------------------
    elif (fcl_template == 'cfo_fragment_receiver'):
        with open(fn,'w') as fout:
            for line in lines:
                fout.write(line);

        with open(fn,'a') as fout:
            # this one takes only one fragment, so fragment_ids should be one ID
            fout.write(f'daq.fragment_receiver.rollover_subrun_interval : {proc["rollover_subrun_interval"]}\n' );
#------------------------------------------------------------------------------
# TOY generator
#------------------------------------------------------------------------------
    elif (fcl_template == 'toysim_fragment_receiver'):
        with open(fn,'w') as fout:
            for line in lines:
                fout.write(line);
        # append fragment types
        with open(fn,'a') as fout:
            fout.write(f'daq.fragment_receiver.fragment_type : "{proc["fragment_type"]}"\n');
            fout.write(f'daq.fragment_receiver.fragment_ids  : [ {proc["fragment_ids"]} ]\n' );
                
    elif ('event_builder' in fcl_template):
        # get the trigger table - the FCL mods
        # ------------------------------------------------------------------------------
        tt_name = client.odb_get("/Mu2e/ActiveRunConfiguration/Trigger/Table");
        tt      = client.odb_get(f'/Mu2e/ActiveRunConfiguration/Trigger/{tt_name}');
        # print(tt);

        TRACE.INFO(f'event_builder: {fcl_template} nlines:{len(lines)} trigger_table:{tt_name}',TRACE_NAME)
        
        # in case of the event builder, do not append, override
        # it is important that 'physics : {}' etc is located on one line
        #---------------------------------------------------------
        with open(fn,'w') as fout:
            for line in lines:
                if (re.search(r'\s*process_name\s*:',line)):
                    # see , if this reduces the number of branches... nothing good came from that...
                    fout.write(f'    process_name : {artdaqLabel}\n');
                    # fout.write(f'    process_name : "eb"\n');
                    continue;

                if (re.search(r'\s*physics\s*:\s*\{\s*\}',line)):
                    fout.write(f'    physics      : {{ @table::{tt_name}.physics }}\n');
                    continue;

                if (re.search(r'\s*outputs\s*:\s*\{\s*\}',line)):
                    fout.write(f'    outputs      : {{ @table::{tt_name}.outputs }}\n');
                    continue

                fout.write(line);

            # now look at the trigger table for overrides in the filter settings
            #------------------------------------------------------------------------------
            header_written = False
            for k0 in tt.keys():
                TRACE.INFO(f'key: {k0} is_dict:{isinstance(tt[k0],dict)}',TRACE_NAME)
                if (k0 == 'physics'):
                    l0 = 'art.physics'
                    # loop over
                    TRACE.INFO(f'tt[k0].keys(): {tt[k0].keys()}',TRACE_NAME)
                    for k1 in tt[k0].keys():
                        if (k1[0] == '#') :
                            continue
                        
                        if (k1 == 'filters') or (k1 == 'producers'):
                            l1 = l0 + f'.{k1}'
                            
                            # loop over modules
                            modules = tt[k0][k1] # this is a subdict
                            TRACE.INFO(f'l1:{l1} modules:{modules}',TRACE_NAME)
                            for k2 in modules.keys():
                                print(f'k2:{k2}')
                                l2 = l1+f'.{k2}'
                                module = modules[k2]
                                # next go module parameters, to begin with, consider the simplest case
                                TRACE.INFO(f'module:{module} l2:{l2}',TRACE_NAME)
                                for k3 in module.keys():
                                    l3 = l2+f'.{k3} : {module[k3]}\n'
                                    TRACE.INFO(f'l3:{l3}',TRACE_NAME)

                                    if (not header_written):
                                        fout.write('#---------------------------------------------------\n')
                                        fout.write('# trigger overrides from ODB\n');
                                        fout.write('#---------------------------------------------------\n')
                                        header_written = True
                                    
                                    fout.write(l3)
                                    
                        elif ((k1 == 'path_p1') or (k1 == 'path_e1')):
                            l1 = l0 + f'.{k1}: [ {tt[k0][k1]} ]'
                                        
                            if (not header_written):
                                fout.write('#---------------------------------------------------\n')
                                fout.write('# trigger overrides from ODB\n');
                                fout.write('#---------------------------------------------------\n')
                                header_written = True
                                
                            fout.write(l1)

                                                

    elif ('data_logger' in fcl_template):
        TRACE.INFO(f'generating DATA_LOGGER FCL',TRACE_NAME)
        # get the trigger table - the FCL mods
        # ------------------------------------------------------------------------------
        tt_name = client.odb_get("/Mu2e/ActiveRunConfiguration/Trigger/Table");
        tt      = client.odb_get(f'/Mu2e/ActiveRunConfiguration/Trigger/{tt_name}');
        # print(tt);

        with open(fn,'w') as fout:
            for line in lines:
                if (re.search(r'\s*art.outputs\.([^.]+)\.fileName\s*:\s*',line)):
                    data_directory_override = client.odb_get('/Mu2e/ActiveRunConfiguration/DAQ/Tfm/data_directory_override')
                    data_dir = os.path.expandvars(data_directory_override)
                    s2 = line.replace('/tmp/', f'{data_dir.rstrip("/")}/', 1)
                    fout.write(s2)
                    continue
                
                TRACE.INFO(f'writing line:{line}',TRACE_NAME)        
                fout.write(line);
                
        with open(fn,'a') as fout:
            fout.write(f'art.process_name : {artdaqLabel}\n');

            # now look at the trigger table for overrides in the filter settings
            #------------------------------------------------------------------------------
            if ('data_logger' in tt.keys()):
                dl_pars = tt['data_logger']
                TRACE.INFO(f'tt.keys:{tt.keys()} dl_pars:{dl_pars}',TRACE_NAME)
                for k0 in dl_pars.keys():
                    TRACE.INFO(f'key: {k0} is_dict:{isinstance(tt[k0],dict)}',TRACE_NAME)
                    if (k0 == 'physics'):
                        l0 = 'art.physics'
                        # loop over
                        TRACE.INFO(f'physics.keys(): {dl_pars[k0].keys()}',TRACE_NAME)
                        for k1 in dl_pars[k0].keys():
                            if (k1 == 'path_e1'):
                                l1 = l0 + f'.{k1}: [ {dl_pars[k0][k1]} ]'
                                TRACE.INFO(f'writing line:{l1}',TRACE_NAME)        
                                fout.write(l1)


    elif ('dispatcher' in fcl_template):
        with open(fn,'w') as fout:
            for line in lines:
                fout.write(line);
                
        with open(fn,'a') as fout:
            fout.write(f'art.process_name : {artdaqLabel}\n');

    TRACE.INFO(f'-- END:');

#------------------------------------------------------------------------------
# generate FCL for processes defined by par, always for ACTIVE configuration !
# do that for all enabled nodes and processes - that saves a restart:
# traverse ODB, do not look at the cached in the software list of nodes
# 1) before restarting TFM, enable what needs to be enabled and generate FCLs
# 2) restart TFM
#------------------------------------------------------------------------------
def gen_fcl(client,args):
    TRACE.INFO('-- START',TRACE_NAME);

    # client  = midas.client.MidasClient("gen_artdaq_fcl", None,"tracker",None)
#-----------------------------------------------------------------------------
# use None for the host , otherwise bools become ints - WHY ???
#-----------------------------------------------------------------------------

    run_conf_name  = client.odb_get('/Mu2e/ActiveRunConfiguration/Name')
    daq_nodes_path = f'/Mu2e/ActiveRunConfiguration/DAQ/Nodes/'
    TRACE.INFO(f'------------- daq_nodes_path:{daq_nodes_path}',TRACE_NAME)
    daq_nodes = client.odb_get(daq_nodes_path)
    TRACE.DEBUG(1,f'------------- daq_nodes_dir:\n{daq_nodes}',TRACE_NAME)

    for host,params in daq_nodes.items():
        TRACE.INFO(f'host:{host:12} ----------- enabled:{params["Enabled"]} status:{params["Status"]}',TRACE_NAME);
        if ((args["host"] != 'all') and (args["host"] != host )): continue;
            
        if (params["Enabled"] == 0):                             continue
        artdaq = params["Artdaq"];       # should be a dict (subdirectory)
        if (artdaq["Enabled"] == 0):                             continue
        TRACE.DEBUG(1,f'artdaq:{artdaq}',TRACE_NAME)
        # pname - parameter name
        for pname,pdata in artdaq.items():
            TRACE.INFO(f'host:{host} pname:{pname} is_dict:{isinstance(pdata,dict)}',TRACE_NAME)
            if ((args["process"] != 'all') and (args["process"] != pname)): continue;
            if (not isinstance(pdata,dict)):                                continue;
            
            TRACE.INFO(f'pname:{pname} pdata["Enabled"]:{pdata["Enabled"]}',TRACE_NAME)
            
            if (pdata['Enabled'] == 0):                          continue;
#-----------------------------------------------------------------------------
# this is a link
#------------------------------------------------------------------------------
            fcl_template_path = pdata['fcl_template']
            fcl_template_name = client.odb_get(fcl_template_path); 
#---------------^--------------------------------------------------------------
# found template name, templates are stored in config/artdaq/common
# now only need to check what is requested
#---------------v--------------------------------------------------------------
            TRACE.INFO(f'generating fcl for host:{host} process:{pname} using template:{fcl_template_name}',TRACE_NAME)
#---------------^--------------------------------------------------------------
# templates are stored in /Mu2e/RunConfigurations/{run_conf}/DAQ/FclTemplates
# step 1: save existing FCL file
#---------------v--------------------------------------------------------------
            config_dir = os.path.expandvars(client.odb_get('/Mu2e/ConfigDir'))+f'/artdaq/{run_conf_name}'
            fcl_fn = f'{config_dir}/{pname}.fcl'
            fpath = Path(fcl_fn)
            TRACE.INFO(f'config_dir:{config_dir} fcl_fn:{fcl_fn}',TRACE_NAME);
            if (fpath.exists()):
                # FHICL file exists, save it
                tstamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
                cmd    = f'cp {fcl_fn} {fcl_fn}.save.{tstamp}'
                os.system(cmd)
#---------------^--------------------------------------------------------------
# step 2: generate new fcl and save it, error handling to be added
#         proc is a dict coresponding to the artdaq process record in ODB
#---------------v--------------------------------------------------------------
            TRACE.INFO(f'fcl_template_name:{fcl_template_name}',TRACE_NAME)
            write_fcl(run_conf_name,client,args,pname,pdata,fcl_template_name)

    # client.disconnect();
    
    TRACE.INFO('-- END',TRACE_NAME);
    return 0;
    

#------------------------------------------------------------------------------
# returns the name like /scratch/mu2e/mu2etrk/daquser_002_v001/logs/pmt/pmt_050030_${nodename}_mu2etrk_partition_11_20260513154539
# it looks that the node name on the local network is used
#------------------------------------------------------------------------------
def pmt_log_fn(log_directory,partition,run_number):
    TRACE.INFO(f'-- START: run_number:{run_number} user:{os.environ.get("USER")} partition:{partition}');
    fn = f'{log_directory}/pmt/pmt_{run_number:06d}_${{nodename}}_{os.environ.get("USER")}_partition_{partition:02d}_{rcu.date_and_time_filename()}'
    TRACE.INFO(f'-- END: fn:{fn}')
    return fn

#------------------------------------------------------------------------------
# pass nodename explicitly - not sure how who is the end user
#------------------------------------------------------------------------------
def pmt_log_fn_node(nodename,log_directory,partition,run_number):
    TRACE.INFO(f'-- START: node:{node} run_number:{run_number} user:{os.environ.get("USER")} partition:{partition}');
    fn = f'{log_directory}/pmt/pmt_{run_number:06d}_{nodename}_{os.environ.get("USER")}_partition_{partition:02d}_{rcu.date_and_time_filename()}'
    TRACE.INFO(f'-- END: fn:{fn}')
    return fn

#------------------------------------------------------------------------------
# "Subsystem" is a structure containing all info about a given artdaq subsystem
# a subsystem has 
# - an ID, 
# - one or several input sources,
# - one output destination,
# - a mode in which it handles the artdaq fragments
#-----------------------------------------------------------------------------
class Subsystem(object):
    __index = 0;                            # subsystem number counter

    def __init__(self,ssid,enabled):
        self.id           = ssid            # ssid is a string
        self.index        = Subsystem.__index;        # 
        self.fragmentMode = None            #

        self.sources      = []              # list of strings (ss_id's) - get rid of that...
        self.destination  = None            # string
        self.enabled      = enabled         # has to be defined
        
                                            # temporarily duplicate the above, prepare for a transition
                                            
        self.list_of_sS   = [];             # list of source subsystems (objects of Subsystem type)
        self.dS           = None;           # destination subsystem (if not None, object of Subsystem type)
        
        self.list_of_procinfos = { }
        self.list_of_procinfos[BOARD_READER   ] = []
        self.list_of_procinfos[EVENT_BUILDER  ] = []
        self.list_of_procinfos[DATA_LOGGER    ] = []
        self.list_of_procinfos[DISPATCHER     ] = []
        self.list_of_procinfos[ROUTING_MANAGER] = []
        self.max_type     = -1;             # max type of the processes in this subsystem
        self.min_type     = 99;             # min type of the processes in this subsystem

        Subsystem.__index += 1;             # increment the subsystem counter, why is it needed ?
        
    def __lt__(self, other):
        if self.index != other.index:
                                            # both destination and id are strings (names)
            if self.destination == other.id:  
                # 'self' provides input for 'other', should go before in the ordered list
                return True
            else:
                return False
        else:
            return False  # equal

#------------------------------------------------------------------------------
    def print(self):
        TRACE.DEBUG(1,f'-- START: ID:{self.id} index:{self.index} fragmentMode:{self.fragmentMode}',TRACE_NAME)
        TRACE.DEBUG(1,f'sources     :{self.list_of_sS}',TRACE_NAME)
        TRACE.DEBUG(1,f'destination :{self.dS}',TRACE_NAME)
        TRACE.DEBUG(1,f'procinfos   :',TRACE_NAME)
        
        for k in self.list_of_procinfos:
            list_of_p = self.list_of_procinfos[k]   ## expect to be a list
            for p in list_of_p:
                TRACE.DEBUG(1,f'-- k:{k} p.label:{p.label}')

        TRACE.DEBUG(1,'-- END:',TRACE_NAME);

#------------------------------------------------------------------------------
    def list_of_board_readers(self):
        return self.list_of_procinfos[BOARD_READER];
    
    def list_of_data_loggers(self):
        return self.list_of_procinfos[DATA_LOGGER];
    
    def list_of_dispatchers(self):
        return self.list_of_procinfos[DISPATCHER];
    
    def list_of_event_builders(self):
        return self.list_of_procinfos[EVENT_BUILDER];
    
    def list_of_routing_managers(self):
        return self.list_of_procinfos[ROUTING_MANAGER];
    
    def list_of_event_processes(self, type):
        return self.list_of_procinfos[type];
    
#------------------------------------------------------------------------------
class Node:
    
    def __init__(self, name, node_artdaq_odb_path):
        self.name                 = name;
        self.node_artdaq_odb_path = node_artdaq_odb_path;
        self.list_of_processes    = []

    def add_process(self,p):
        self.list_of_processes.append(p);        

#------------------------------------------------------------------------------
# Artdaq: a list of nodes, a list of subsystems,
# ... and a list of processes [to come]
#------------------------------------------------------------------------------

class Artdaq:
    def __init__(self):
        self.list_of_nodes      = []
        self.list_of_subsystems = []

    def add_node(self, node):
        self.list_of_nodes.append(node);

#------------------------------------------------------------------------------
