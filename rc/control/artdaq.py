#!/bin/env/python

import os, sys, argparse, glob, inspect, re, subprocess
import tfm.rc.control.utilities as rcu

from   tfm.rc.control.procinfo  import Procinfo, BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ;
from   pathlib                  import Path
from   datetime                 import datetime
from   zoneinfo                 import ZoneInfo

import TRACE ; TRACE_NAME='artdaq'

#------------------------------------------------------------------------------
def write_fcl(client,args,artdaqLabel,proc,fcl_template):

    config_dir  = os.path.expandvars(client.odb_get('/Mu2e/ConfigDir'));
    template_fn = config_dir+f'/artdaq/common/{fcl_template}.fcl'

    TRACE.INFO(f'-- START: fcl_template:{fcl_template} config_dir:{config_dir} template_fn:{template_fn}',TRACE_NAME);

    output_dir = config_dir+f'/artdaq/{args["run_conf"]}'
    fn         = f'{output_dir}/{artdaqLabel}.fcl'

    TRACE.INFO(f'output_dir:{output_dir} fn:{fn}',TRACE_NAME);

    lines = []
    with open(template_fn) as f:
        lines = f.readlines()

        TRACE.INFO(f'len(lines): {len(lines)}',TRACE_NAME);
#------------------------------------------------------------------------------
# now - additions, different for different templates
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
                fout.write(line);
                
        with open(fn,'a') as fout:
            # this one takes only one fragment, so fragment_ids should be one ID
            fout.write(f'daq.fragment_receiver.fragment_id : {proc["fragment_ids"]}\n' );
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
        trigger_table = client.odb_get("/Mu2e/ActiveRunConfiguration/Trigger/Table");

        TRACE.INFO(f'event_builder: {fcl_template} nlines:{len(lines)} trigger_table:{trigger_table}',TRACE_NAME)
        
        # in case of the event builder, do not append, override
        with open(fn,'w') as fout:
            for line in lines:
                if (re.search(r'\s*process_name\s*:',line)):
                    fout.write(f'    process_name : {artdaqLabel}\n');
                    continue;

                if (re.search(r'\s*physics\s*:\s*\{\s*\}',line)):
                    fout.write(f'    physics      : {{ @table::{trigger_table}.physics }}\n');
                    continue;

                if (re.search(r'\s*outputs\s*:\s*\{\s*\}',line)):
                    fout.write(f'    outputs      : {{ @table::{trigger_table}.outputs }}\n');
                    continue

                fout.write(line);

    elif ('data_logger' in fcl_template):
        with open(fn,'w') as fout:
            for line in lines:
                fout.write(line);
                
        with open(fn,'a') as fout:
            fout.write(f'art.process_name : {artdaqLabel}\n');

    elif (fcl_template == 'dispatcher'):
        with open(fn,'w') as fout:
            for line in lines:
                fout.write(line);
                
        with open(fn,'a') as fout:
            fout.write(f'art.process_name : {artdaqLabel}\n');

    TRACE.INFO(f'-- END:');

#------------------------------------------------------------------------------
# generate FCL for processes defined by par
#------------------------------------------------------------------------------
def gen_fcl(client,args):
    TRACE.INFO('-- START',TRACE_NAME);

    # client  = midas.client.MidasClient("gen_artdaq_fcl", None,"tracker",None)
#-----------------------------------------------------------------------------
# use None for the host , otherwise bools become ints - WHY ???
#------------------------------------------------------------------------------
       
    daq_nodes_path = f'/Mu2e/RunConfigurations/{args["run_conf"]}/DAQ/Nodes/'
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
            TRACE.INFO(f'generating fcl for run_conf:{args["run_conf"]} host:{host} process:{pname} using template:{fcl_template_name}',TRACE_NAME)
#---------------^--------------------------------------------------------------
# templates are stored in /Mu2e/RunConfigurations/{run_conf}/DAQ/FclTemplates
# step 1: save existing FCL file
#---------------v--------------------------------------------------------------
            config_dir = os.path.expandvars(client.odb_get('/Mu2e/ConfigDir'))+f'/artdaq/{args["run_conf"]}'
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
            write_fcl(client,args,pname,pdata,fcl_template_name)

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
# list_of_processes is either a p.list_of_destinations or a p.list_of_sources
#------------------------------------------------------------------------------
def host_map_string(plist,offset = ''):
    s = ''
    for p in plist:
        s += f' {{ rank:{p.rank:3} host: "{p.host}"}}';
        if (p != plist[-1]):
            s += ','

    return s;

#------------------------------------------------------------------------------
# 'p' is a Processinfo
#------------------------------------------------------------------------------
def destination_string(p,transfer_plugin):
    s = ''
    for d in p.list_of_destinations:
        s += f' d{d.rank}: {{'
        s += f' transferPluginType: {transfer_plugin}'
        s += f' destination_rank:  {d.rank}'
        # for BR, event=fragment
        s += f' max_fragment_size_words: {p.max_event_size_words()}'
        
        # first destination includes the host_map
        if (d == p.list_of_destinations[0]):
            offset = '        '
            s += ' host_map: ['
            s += host_map_string(p.list_of_destinations,offset);
            s += ' ]'
            
        s +=  '}\n'

    return s;

#------------------------------------------------------------------------------
# 'p' is a Processinfo
#------------------------------------------------------------------------------
def source_string(p,transfer_plugin):
    s  = ''

    for x in p.list_of_sources:
        s += f' s{x.rank}: {{'
        s += f' transferPluginType: {transfer_plugin}'
        s += f' source_rank:  {x.rank}'
        s += f' max_fragment_size_words: {x.max_event_size_words()}'
        
        # first destination includes the host_map
        if (x == p.list_of_sources[0]):
            s += ' host_map: ['
            offset = ''
            s += host_map_string(p.list_of_sources,offset);
            s += ' ]'
            
        s +=  '}\n'

    return s;

#---^--------------------------------------------------------------------------
# marking the end
#------------------------------------------------------------------------------

class Node:
    
    def __init__(self, name, node_artdaq_odb_path):
        self.name                 = name;
        self.node_artdaq_odb_path = node_artdaq_odb_path;
        self.list_of_processes    = []

    def add_process(self,p):
        self.list_of_processes.append(p);        

#------------------------------------------------------------------------------
class Artdaq:
    def __init__(self):
        self.list_of_nodes = []

    def add_node(self, node):
        self.list_of_nodes.append(node);
        
#------------------------------------------------------------------------------
# define processes this p.type = BOARD_READER, BR is talking to destinations only
#------------------------------------------------------------------------------
class BoardReader(Procinfo):

    def __init__(self,
                 name, ##                = None, ## pname,
                 rank, ##               = rank ,
                 host, ##               = host ,          # at this point, store long (with '-ctrl' names)
                 port, ##               = str(xmlrpc_port),
                 timeout, ##            = timeout,
                 label,   ##              = key_name  ,
                 subsystem , ##         = subsystem,
                 allowed_processors = None,
                 target             = "none",
                 fhicl              = "no_fcl_fn",
                 prepend            = ""
                 ):
        
        super().__init__(name,rank,host,port,timeout,label,subsystem,
                         allowed_processors,target,fhicl,prepend)

        self._type    = BOARD_READER;
        self.execname = 'boardreader'

#------------------------------------------------------------------------------
# boardreades only have destinations
#------------------------------------------------------------------------------
    def init_connections(self):
        
        # s = self.subsystems[p.subsystem_id]; # subsystem which a given process belongs to
        s = self.subsystem;                       # this is an object, not a string (subsystem_id)
        if (s.max_type >= EVENT_BUILDER):
            # local EBs: send fragments to them

            list_of_ebs = s.list_of_procinfos[EVENT_BUILDER]
            for eb in list_of_ebs:
                self.list_of_destinations.append(eb);
                eb.list_of_sources.append(self);
        else:
            # subsystem has only BRs, check subsystem destination
            TRACE.INFO(f'-- [BoardReader::init_connections] self.label:{self.label} s.destination:{s.destination}',TRACE_NAME)
            if (s.destination != None):
                # subsystem has a destination, that has to have event builders
                TRACE.INFO(f'subsystem:{s.id} destination is not NONE, but :"{s.destination}"',TRACE_NAME)
                sd = s.dS;                  # destination subsystem, ## self.subsystems[s.destination];
                list_of_ebs = sd.list_of_procinfos[EVENT_BUILDER]
                TRACE.DEBUG(1,f'-- [BoardReader::init_connections] sd.id:{sd.id} len(list_of_ebs):{len(list_of_ebs)}',TRACE_NAME)
                
                for eb in list_of_ebs:
                    TRACE.INFO(f'-- [init_br_connections] append {eb.label} to the destinations of {self.label}',TRACE_NAME)
                    self.list_of_destinations.append(eb);
                    eb.list_of_sources.append(self);
            else:
                # the subsystem has only BRs', that is a problem
                raise Exception(f'ERROR: subsystem:{s.id} has only BRs and no destination. FIX IT.')
        return;

#------------------------------------------------------------------------------
# BoardReader: return updated , nut not yet expanded FCL
#------------------------------------------------------------------------------
    def update_fhicl(self,transfer_plugin):
        # step 1 : read and replace - start from BRs
        TRACE.DEBUG(1,f'--START: self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
    
        with open(self.fhicl,'r') as f:
            lines = f.readlines()

        new_text = []
        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = destination_string(self,transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue
                
            pattern = r'(?:[\w-]+\.)*max_fragment_size_bytes'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {self.max_fragment_size_bytes}\n';
                new_text.append(s);
                continue;

            new_text.append(line)
        
        TRACE.DEBUG(1,f'--END: self.label:{self.label}',TRACE_NAME)
        return new_text;



#------------------------------------------------------------------------------
class EventBuilder(Procinfo):

    def __init__(self,
                 name  , ##             = pname,
                 rank  , ##             = rank ,
                 host  , ##             = host ,          # at this point, store long (with '-ctrl' names)
                 port  , ##             = str(xmlrpc_port),
                 timeout, ##            = timeout,
                 label  , ##            = key_name  ,
                 subsystem , ##         = subsystem,
                 allowed_processors = None,
                 target             = "none",
                 fhicl              = "no_fcl_fn",
                 prepend            = ""
                 ):
        
        super().__init__(name,rank,host,port,timeout,label,subsystem,
                         allowed_processors,target,fhicl,prepend)
        self._type              = EVENT_BUILDER;
        self.execname           = 'eventbuilder'
        self.art_analyzer_count = 1;                         # make 1 the default
        
    def init_connections(self):      # p = self
        TRACE.INFO(f'-- START: EventBuilder::init_connections:{self.label}',TRACE_NAME)
        # EB has to have inputs - either from own BRs or from other subsystems or EBs from other subcyctems
        # start from checking inputs

        s = self.subsystem; ## self.subsystems[p.subsystem_id]; # subsystem which a given process belongs to

        # BRs should already be covered, check for input from other EBs

        # print(f's.sources:{s.sources}');
        # print(f'process.list_of_sources:{self.list_of_sources}');

        sum_fragment_size_bytes  = 0;               # sum of the BR's input
        max_event_size_bytes     = 0;               # max event from input EB's
        self.init_fragment_count = 0;

        if (len(s.sources) > 0):
            TRACE.INFO(f's.id:{s.id} s.sources:{s.sources}',TRACE_NAME);
            for ss in s.list_of_sS:
                TRACE.INFO(f'ss {ss}',TRACE_NAME)
                # there should be no DLs in the source subsystem, it should end in EB
                if (ss.max_type == EVENT_BUILDER):
                    list_of_ebs = ss.list_of_procinfos[EVENT_BUILDER]
                    for eb in list_of_ebs:
                        self.init_fragment_count += 1
                        if (eb.max_event_size_bytes > max_event_size_bytes):
                            max_event_size_bytes = eb.max_event_size_bytes;
                        # avoid double counting
                        if (not eb in self.list_of_sources):
                            self.list_of_sources.append(eb);
                            eb.list_of_destinations.append(self);

                elif (ss.max_type == BOARD_READER):
                    list_of_brs = ss.list_of_procinfos[BOARD_READER]
                    for br in list_of_brs:
                        # it looks that the BRs send fragments, not 'serialized art events'....
                        # self.init_fragment_count += 1
                        sum_fragment_size_bytes  += br.max_fragment_size_bytes;
                        # avoid double counting
                        if (not br in self.list_of_sources):
                            self.list_of_sources.append(eb);
                            eb.list_of_destinations.append(self);
            TRACE.INFO(f'self.init_fragment_count:{self.init_fragment_count}',TRACE_NAME);
        else:
#-------^----------------------------------------------------------------------
# subsystem doesn't have inputs, look at local BRs - those already are in the list of inputs
#-----------v------------------------------------------------------------------
            for br in self.list_of_sources:
                TRACE.DEBUG(1,f'br.label:{br.label} br.max_fragment_size_bytes:{br.max_fragment_size_bytes}',TRACE_NAME)
                sum_fragment_size_bytes += br.max_fragment_size_bytes

                TRACE.DEBUG(1,f'p.max_event_size_bytes:{self.max_event_size_bytes} self.max_fragment_size_bytes:{self.max_fragment_size_bytes}',TRACE_NAME)


        self.max_fragment_size_bytes = sum_fragment_size_bytes;
        self.max_event_size_bytes    = sum_fragment_size_bytes+max_event_size_bytes;

#---------------------------^--------------------------------------------------
# done with the sources
# destinations: each EB should also have 'destination' processes tow hich it sends events - either DL's or other EB's (or DSs ?)
# first check if the subsystem ahs data loggers
#-------v----------------------------------------------------------------------

        list_of_dls = s.list_of_procinfos[DATA_LOGGER]
        if (len(list_of_dls) > 0):
            # subsystem has its own DL(s)
            for dl in list_of_dls:
                dl.list_of_sources.append(self);
                self.list_of_destinations.append(dl);
                    
        else:
            # subsystem has no its own data loggers, so it should have a destination subsystem
            sd = s.dS;
            if (sd != None):
                # subsystem has a destination, that may start with BR, but they will be skipped
                # first check EBs in the destination subsystem
                list_of_ebs = sd.list_of_procinfos[EVENT_BUILDER]
                if (len(list_of_ebs) > 0):
                    for eb in list_of_ebs:
                        self.list_of_destinations.append(eb);
                        eb.list_of_sources.append(self);
                else:
                    # no EBs, check for DLs
                    list_of_dls = sd.list_of_procinfos[DATA_LOGGER]
                    if (len(list_of_dls) > 0):
                        for dl in list_of_dls:
                            self.list_of_destinations.append(dl);
                            dl.list_of_sources.append(self);
                    else:
                        # no EBs/DLss, check for DSs
                        list_of_dss = sd.list_of_procinfos[DISPATCHER]
                        if (len(list_of_dss) > 0):
                            for ds in list_of_dss:
                                self.list_of_destinations.append(ds);
                                ds.list_of_sources.append(self);
                                
                            else:
                                # a problem , throw
                                raise Exception('EB: no EBs/DLs in the DEST');
        return;

#------------------------------------------------------------------------------
# EventBuilder: update FCL
#------------------------------------------------------------------------------
    def update_fhicl(self, transfer_plugin):
        # step 1 : read and replace - start from BRs
        TRACE.DEBUG(1,f'EB : self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
        
        with open(self.fhicl,'r') as f:
            lines = f.readlines()
    
        new_text = []
    
        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*sources'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                # always replace the line with the real string
                # max_fragment_size_words is calculated
                s = source_string(self,transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue
    
            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = destination_string(self,transfer_plugin);
                new_text.append(s);
                new_text.append('}\n');
                continue;
                
            pattern = r'(?:[\w-]+\.)*host_map'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: [');
                offset = '    ' # 4 spaces (TCL indent)
                s      = host_map_string(self.list_of_destinations,offset);
                new_text.append(s);
                new_text.append(' ]\n');
                continue;
    
            pattern = r'(?:[\w-]+\.)*max_event_size_bytes'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {self.max_event_size_bytes}\n';
                new_text.append(s);
                continue;
    
            pattern = r'(?:[\w-]+\.)*init_fragment_count'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {self.init_fragment_count}\n';
                new_text.append(s);
                continue;

            pattern = r'(?:[\w-]+\.)*art_analyzer_count'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {self.art_analyzer_count}\n';
                new_text.append(s);
                continue;
    
            new_text.append(line);

        TRACE.DEBUG(1,f'END',TRACE_NAME)
        return new_text;
            
#------------------------------------------------------------------------------
class DataLogger(Procinfo):

    def __init__(self,
                 name, ##                = pname,
                 rank , ##              = rank ,
                 host , ##              = host ,          # at this point, store long (with '-ctrl' names)
                 port , ##              = str(xmlrpc_port),
                 timeout, ##            = timeout,
                 label, ##              = key_name  ,
                 subsystem, ##          = subsystem,
                 allowed_processors = None,
                 target             = "none",
                 fhicl              = "no_fcl_fn",
                 prepend            = ""
                 ):
        
        super().__init__(name,rank,host,port,timeout,label,subsystem,
                         allowed_processors,target,fhicl,prepend)
        self._type                 = DATA_LOGGER;
        self.execname              = 'datalogger'
        self.output_data_directory = None

#-------^----------------------------------------------------------------------
# define processes for p.type = DATA_LOGGER
#------------------------------------------------------------------------------
    def init_connections(self):

        TRACE.INFO(f'-- START: p.label:{self.label} p.subsystem_id:{self.subsystem_id}',TRACE_NAME);
        # DL has to have inputs from either own EBs or from EBs other subsystems
        # start from checking inputs
        s = self.subsystem; ## self.subsystems[p.subsystem_id]; # subsystem which a given process belongs to
        s.print();
        # EBs should already be covered

        self.max_event_size_bytes = 0;
        self.init_fragment_count  = 0;

        if ((len(s.list_of_sS) > 0) and (s.min_type == DATA_LOGGER)):
            # subsystem has sources, and there is no local  EBs
            # can take input from the upstream EBs
            for ss in s.list_of_sS:
                # there should be no DLs in the source subsystem, it should end with  the EBs
                if (ss.max_type == EVENT_BUILDER):
                    list_of_ebs = ss.list_of_event_builders()
                    for eb in list_of_ebs:
                        self.init_fragment_count += eb.art_analyzer_count;
                        
                        if (eb.max_event_size_bytes > self.max_event_size_bytes):
                            self.max_event_size_bytes =  eb.max_event_size_bytes
    
                        # avoid double counting
                        if (not eb in self.list_of_sources):
                            self.list_of_sources.append(eb);
                            eb.list_of_destinations.append(self);
                            
            TRACE.INFO(f'self.init_fragment_count:{self.init_fragment_count}',TRACE_NAME);
#-------------------------------^----------------------------------------------
# no source subsystems or those start from DLs - look for local inputs
# counting logic: an init fragment per each art process
#-------v----------------------------------------------------------------------
        else:
            # subsystem has no official sources, there should be local EB's
            list_of_ebs = s.list_of_event_builders()
            if (len(list_of_ebs) > 0):
                for eb in list_of_ebs:
                    self.init_fragment_count += eb.art_analyzer_count;
                    if (eb.max_event_size_bytes > self.max_event_size_bytes):
                        self.max_event_size_bytes =  eb.max_event_size_bytes
                        
                    if (not eb in self.list_of_sources):
                        self.list_of_sources.append(eb);
                        eb.list_of_destinations.append(self);
                    
            else:
                # subsystem has no own EB's : trouble
                raise Exception('DL: no EBs in the subsystem');

            TRACE.INFO(f'self.init_fragment_count:{self.init_fragment_count}',TRACE_NAME);
#------------------------------------------------------------------------------
# now - destinations ... not done yet
#-------v----------------------------------------------------------------------
        list_of_dss = s.list_of_dispatchers()
        if (len(list_of_dss) > 0):
            for ds in list_of_dss:
                self.init_fragment_count += 1;
                        
                if (not ds in self.list_of_destinations):
                    self.list_of_destinations.append(ds);
                    ds.list_of_sources.append(self);

        TRACE.ERROR(f'DL {self.label} no destinations defined - FIXME',TRACE_NAME)
        return;

#------------------------------------------------------------------------------
#  DataLogger
#------------------------------------------------------------------------------
    def update_fhicl(self, transfer_plugin):
        TRACE.INFO(f'-- START: self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
        
        with open(self.fhicl,'r') as f:
            lines = f.readlines()
    
        new_text = []

        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*sources'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = source_string(self,transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue

            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                s = destination_string(self,transfer_plugin);
                if (s):
                    key = match.group(0);
                    new_text.append(f'{key}: {{\n');
                    new_text.append(s);
                    new_text.append('}\n');
                    continue;
                
            pattern = r'(?:[\w-]+\.)*host_map'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: [');
                offset = '    ' ## 4 spaces, TCL indent
                # host_map_string - always destinations
                s = host_map_string(self.list_of_destinations,offset);
                TRACE.INFO(f'self.label:{self.label} host_map_string:{s}',TRACE_NAME)
                new_text.append(s);
                new_text.append(' ]\n');
                continue;
    
            pattern = r'(?:[\w-]+\.)*max_event_size_bytes'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {self.max_event_size_bytes+800000}\n';
                new_text.append(s);
                continue;

            pattern = r'(?:[\w-]+\.)*init_fragment_count'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {self.init_fragment_count}\n';
                new_text.append(s);
                continue;

            #------------------------------------------------------------------------------
            # any other line - just rewrite
            #------------------------------------------------------------------------------
            new_text.append(line);

        TRACE.INFO(f'-- END: self.label:{self.label}',TRACE_NAME)
        return new_text;

#-------^----------------------------------------------------------------------
class Dispatcher(Procinfo):

    def __init__(self,
                 name, ##              = pname,
                 rank, ##               = rank ,
                 host, ##               = host ,          # at this point, store long (with '-ctrl' names)
                 port, ##               = str(xmlrpc_port),
                 timeout, ##            = timeout,
                 label, ##              = key_name  ,
                 subsystem, ##          = subsystem,
                 allowed_processors = None,
                 target             = "none",
                 fhicl              = "no_fcl_fn",
                 prepend            = ""
                 ):
        
        super().__init__(name,rank,host,port,timeout,label,subsystem,
                         allowed_processors,target,fhicl,prepend)
        self._type    = DISPATCHER;
        self.execname = 'dispatcher'
        


    def init_connections(self):
        # DS only has inputs ..DLs ? start from checking inputs
        s = self.subsystem; ## self.subsystems[p.subsystem_id]; # subsystem which a given process belongs to

        if (len(s.list_of_sS) > 0):
            # THERE ARE INPUT SUBSYSTEMS, thus there should be no local inputs
            # for now, assume correct inputs, handle errors later
            for ss in s.list_of_sS:               ## source in s.sources:
                # there should be DLs in the source subsystem
                if (ss.max_type >= DATA_LOGGER):
                    # it might make sense to allow a DL to send events to DSs anywhere,
                    # although need to check the logic
                    plist = ss.list_of_data_loggers()
                    for x in plist:
                        # avoid double counting - just in case
                        if (not x in self.list_of_sources):
                            self.list_of_sources.append(x);
                            x.list_of_destinations.append(self);
                else:
                    # ss has no DLs, check EBs 
                    plist = ss.list_of_event_builders();
                    for x in plist:
                        # avoid double counting - just in case
                        if (not x in self.list_of_sources):
                            self.list_of_sources.append(x);
                            x.list_of_destinations.append(self);
#---------------------------^--------------------------------------------------
# no input sources , check local inputs
#-------v----------------------------------------------------------------------
        else:
            plist = s.list_of_data_loggers()
            if (len(plist) > 0):
                # DLs available, local EBs should be talking to them
                for x in plist:
                    self.list_of_sources.append(x);
                    x.list_of_destinations.append(self);
                    
            else:
                # subsystem has no own data loggers, look for event builders
                plist = s.list_of_event_builders()
                if (len(plist) > 0):
                    # DLs available, local EBs should be talking to them
                    for x in plist:
                        if (not x in dl.list_of_sources):
                            self.list_of_sources.append(x);
                            x.list_of_destinations.append(self);
                else:
                    # a problem , throw
                    raise Exception('Dispatcher::init_connections: DS: no local DLs or EBs');
        return;

#------------------------------------------------------------------------------
# DS - to be impemented
#------------------------------------------------------------------------------
    def update_fhicl(self, transfer_plugin):
        print('------ DS::update_fhicl')
        TRACE.INFO(f'self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
        
        raise Exception('DISPATCHER: IMPLEMENT ME!')

        with open(self.fhicl,'r') as f:
            lines = f.readlines()
    
        new_text = []
    
        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*sources'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = source_string(self,transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue
    
            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = destination_string(self,transfer_plugin);
                new_text.append(s);
                new_text.append('}\n');
                continue;
                
            pattern = r'(?:[\w-]+\.)*host_map'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: [');
                offset = '    ' ## 4 spaces, TCL indent
                # host_map_string - always destinations
                s = host_map_string(self.list_of_destinations,offset);
                new_text.append(s);
                new_text.append(' ]\n');
                continue;
    
            pattern = r'(?:[\w-]+\.)*max_event_size_bytes'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {self.max_event_size_bytes}\n';
                new_text.append(s);
                continue;
    
            pattern = r'(?:[\w-]+\.)*init_fragment_count'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {self.init_fragment_count}\n';
                new_text.append(s);
                continue;
            
#------------------------------------------------------------------------------
# any other line - just rewrite
#------------------------------------------------------------------------------
            new_text.append(line);
    
        return new_text;
   

#-------^----------------------------------------------------------------------
class RoutingManager(Procinfo):

    def __init__(self,
                 name, ##               = pname,
                 rank, ##               = rank ,
                 host, ##               = host ,          # at this point, store long (with '-ctrl' names)
                 port, ##               = str(xmlrpc_port),
                 timeout, ##            = timeout,
                 label, ##              = key_name  ,
                 subsystem, ##          = subsystem,
                 allowed_processors = None,
                 target             = "none",
                 fhicl              = "no_fcl_fn",
                 prepend            = ""
                 ):
        
        super().__init__(name,rank,host,port,timeout,label,subsystem,
                         allowed_processors,target,fhicl,prepend)
        self._type    = ROUTING_MANAGER;
        self.execname = 'routing_manager'

#------------------------------------------------------------------------------
# define processes for p.type = ROUTINE_MANAGER
#------------------------------------------------------------------------------
    def rm_connections(self):
        raise Exception('RoutingManager::init_connection: not implemented yet');

#------------------------------------------------------------------------------
# RM - to be impemented
#------------------------------------------------------------------------------
    def update_fhicl(self, transfer_plugin):
        print('------ RM::update_fhicl')
        TRACE.INFO(f'self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
        
        raise Exception('DISPATCHER: IMPLEMENT ME!')

        with open(self.fhicl,'r') as f:
            lines = f.readlines()
    
        new_text = []
    
        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*sources'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = source_string(self,transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue
    
            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                s = destination_string(self,transfer_plugin);
                if (s):
                    key = match.group(0);
                    new_text.append(f'{key}: {{\n');
                    new_text.append(s);
                    new_text.append('}\n');
                    continue;
                
            pattern = r'(?:[\w-]+\.)*host_map'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: [');
                offset = '    ' ## 4 spaces, TCL indent
                # host_map_string - always destinations
                s = host_map_string(self.list_of_destinations,offset);
                new_text.append(s);
                new_text.append(' ]\n');
                continue;
    
            pattern = r'(?:[\w-]+\.)*max_event_size_bytes'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {self.max_event_size_bytes}\n';
                new_text.append(s);
                continue;
    
            pattern = r'^(?!#)(?:[\w-]+\.)*init_fragment_count'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {self.init_fragment_count}\n';
                new_text.append(s);
                continue;
            
#------------------------------------------------------------------------------
# any other line - just rewrite
#------------------------------------------------------------------------------
            new_text.append(line);
    
        return new_text;

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
                                            
        self.list_of_sS   = [];             # list of objects of Subsystem type
        self.dS           = None;           # if not None, object of Subsystem tyep
        
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
        print('-- START Subsystem::print')
        print ("-- subsystem ID:"  ,self.id,
               " index:"           ,self.index,
               " sources:"         ,self.sources,
               " destination:"     ,self.destination,
               "fragmentMode:"     ,self.fragmentMode);
        
        for k in self.list_of_procinfos:
            # print(f'------- k:{k}') 
            list_of_p = self.list_of_procinfos[k]   ## expect to be a list
            for p in list_of_p:
                print(f'-- k:{k} p.rank:{p.rank} p.label:{p.label} ')
        print('-- END Subsystem::print')

#------------------------------------------------------------------------------
    def list_of_board_readers(self):
        return self.list_of_procinfos[BOARD_READER];
    
    def list_of_data_loggers(self):
        return self.list_of_procinfos[DATA_LOGGER];
    
    def list_of_event_builders(self):
        return self.list_of_procinfos[EVENT_BUILDER];
    
    def list_of_dispatchers(self):
        return self.list_of_procinfos[DISPATCHER];
    
    def list_of_routing_managers(self):
        return self.list_of_procinfos[ROUTING_MANAGER];
    
    def list_of_event_processes(self, type):
        return self.list_of_procinfos[type];
    
#------------------------------------------------------------------------------
