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

            # then navigate the trigger table description in ODB and append the updates for things line
            # prescale factor
            # ------------------------------------------------------------------------------
            tt = client.odb_get(f'/Mu2e/ActiveRunConfiguration/Trigger/{trigger_table}');
        
            # print(tt);
            header_written = False
            for k0 in tt.keys():
                TRACE.INFO(f'key: {k0} is_dict:{isinstance(tt[k0],dict)}',TRACE_NAME)
                if (k0 == 'physics'):
                    line = f'art.physics'
                    # loop over 
                    for k1 in tt[k0].keys():
                        if (k1 == 'filters'):
                            line += '.filters'
                            # loop over modules
                            filters = tt[k0][k1]
                            for k2 in filters.keys():
                                print(f'k2:{k2}')
                                line += f'.{k2}'
                                module = filters[k2]
                                # next go module parameters, to begin with, consider the simplest case
                                for k3 in module.keys():
                                    line += f'.{k3} : {module[k3]}\n'
                                    TRACE.INFO(f'line:{line}',TRACE_NAME)
                                    if (not header_written):
                                        fout.write('#---------------------------------------------------\n')
                                        fout.write('# trigger overrides\n');
                                        fout.write('#---------------------------------------------------\n')
                                        header_written = True
                                        
                                    fout.write(line)
            

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

# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM# 'p' is a Processinfo
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PMdef destination_string(p,transfer_plugin):
# 2026-06-27 PM    s = ''
# 2026-06-27 PM    for d in p.list_of_destinations:
# 2026-06-27 PM        s += f' d{d.rank}: {{'
# 2026-06-27 PM        s += f' transferPluginType: {transfer_plugin}'
# 2026-06-27 PM        s += f' destination_rank:  {d.rank}'
# 2026-06-27 PM        # for BR, event=fragment
# 2026-06-27 PM        s += f' max_fragment_size_words: {p.max_event_size_words()}'
# 2026-06-27 PM        
# 2026-06-27 PM        # first destination includes the host_map
# 2026-06-27 PM        if (d == p.list_of_destinations[0]):
# 2026-06-27 PM            offset = '        '
# 2026-06-27 PM            s += ' host_map: ['
# 2026-06-27 PM            s += host_map_string(p.list_of_destinations,offset);
# 2026-06-27 PM            s += ' ]'
# 2026-06-27 PM            
# 2026-06-27 PM        s +=  '}\n'
# 2026-06-27 PM
# 2026-06-27 PM    return s;
# 2026-06-27 PM
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM# 'p' is a Processinfo
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PMdef source_string(p,transfer_plugin):
# 2026-06-27 PM    s  = ''
# 2026-06-27 PM
# 2026-06-27 PM    for x in p.list_of_sources:
# 2026-06-27 PM        s += f' s{x.rank}: {{'
# 2026-06-27 PM        s += f' transferPluginType: {transfer_plugin}'
# 2026-06-27 PM        s += f' source_rank:  {x.rank}'
# 2026-06-27 PM        s += f' max_fragment_size_words: {x.max_event_size_words()}'
# 2026-06-27 PM        
# 2026-06-27 PM        # first destination includes the host_map
# 2026-06-27 PM        if (x == p.list_of_sources[0]):
# 2026-06-27 PM            s += ' host_map: ['
# 2026-06-27 PM            offset = ''
# 2026-06-27 PM            s += host_map_string(p.list_of_sources,offset);
# 2026-06-27 PM            s += ' ]'
# 2026-06-27 PM            
# 2026-06-27 PM        s +=  '}\n'
# 2026-06-27 PM
# 2026-06-27 PM    return s;
# 2026-06-27 PM
#---^--------------------------------------------------------------------------
# marking the end
#------------------------------------------------------------------------------
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM# define processes this p.type = BOARD_READER, BR is talking to destinations only
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PMclass BoardReader(Procinfo):
# 2026-06-27 PM
# 2026-06-27 PM    def __init__(self,
# 2026-06-27 PM                 name, ##                = None, ## pname,
# 2026-06-27 PM                 rank, ##               = rank ,
# 2026-06-27 PM                 host, ##               = host ,          # at this point, store long (with '-ctrl' names)
# 2026-06-27 PM                 port, ##               = str(xmlrpc_port),
# 2026-06-27 PM                 timeout, ##            = timeout,
# 2026-06-27 PM                 label,   ##              = key_name  ,
# 2026-06-27 PM                 subsystem , ##         = subsystem,
# 2026-06-27 PM                 allowed_processors = None,
# 2026-06-27 PM                 target             = "none",
# 2026-06-27 PM                 fhicl              = "no_fcl_fn",
# 2026-06-27 PM                 prepend            = ""
# 2026-06-27 PM                 ):
# 2026-06-27 PM        
# 2026-06-27 PM        super().__init__(name,rank,host,port,timeout,label,subsystem,
# 2026-06-27 PM                         allowed_processors,target,fhicl,prepend)
# 2026-06-27 PM
# 2026-06-27 PM        self._type    = BOARD_READER;
# 2026-06-27 PM        self.execname = 'boardreader'
# 2026-06-27 PM
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM# boardreades only have destinations
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM    def init_connections(self):
# 2026-06-27 PM        
# 2026-06-27 PM        # s = self.subsystems[p.subsystem_id]; # subsystem which a given process belongs to
# 2026-06-27 PM        s = self.subsystem;                       # this is an object, not a string (subsystem_id)
# 2026-06-27 PM        if (s.max_type >= EVENT_BUILDER):
# 2026-06-27 PM            # local EBs: send fragments to them
# 2026-06-27 PM
# 2026-06-27 PM            list_of_ebs = s.list_of_procinfos[EVENT_BUILDER]
# 2026-06-27 PM            for eb in list_of_ebs:
# 2026-06-27 PM                self.list_of_destinations.append(eb);
# 2026-06-27 PM                eb.list_of_sources.append(self);
# 2026-06-27 PM        else:
# 2026-06-27 PM            # subsystem has only BRs, check subsystem destination
# 2026-06-27 PM            TRACE.INFO(f'-- [BoardReader::init_connections] self.label:{self.label} s.destination:{s.destination}',TRACE_NAME)
# 2026-06-27 PM            if (s.destination != None):
# 2026-06-27 PM                # subsystem has a destination, that has to have event builders
# 2026-06-27 PM                TRACE.INFO(f'subsystem:{s.id} destination is not NONE, but :"{s.destination}"',TRACE_NAME)
# 2026-06-27 PM                sd = s.dS;                  # destination subsystem, ## self.subsystems[s.destination];
# 2026-06-27 PM                list_of_ebs = sd.list_of_procinfos[EVENT_BUILDER]
# 2026-06-27 PM                TRACE.DEBUG(1,f'-- [BoardReader::init_connections] sd.id:{sd.id} len(list_of_ebs):{len(list_of_ebs)}',TRACE_NAME)
# 2026-06-27 PM                
# 2026-06-27 PM                for eb in list_of_ebs:
# 2026-06-27 PM                    TRACE.INFO(f'-- [init_br_connections] append {eb.label} to the destinations of {self.label}',TRACE_NAME)
# 2026-06-27 PM                    self.list_of_destinations.append(eb);
# 2026-06-27 PM                    eb.list_of_sources.append(self);
# 2026-06-27 PM            else:
# 2026-06-27 PM                # the subsystem has only BRs', that is a problem
# 2026-06-27 PM                raise Exception(f'ERROR: subsystem:{s.id} has only BRs and no destination. FIX IT.')
# 2026-06-27 PM        return;
# 2026-06-27 PM
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM# BoardReader: return updated , not not yet expanded FCL
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM    def update_fhicl(self,transfer_plugin):
# 2026-06-27 PM        # step 1 : read and replace - start from BRs
# 2026-06-27 PM        TRACE.DEBUG(1,f'--START: self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
# 2026-06-27 PM
# 2026-06-27 PM        new_text = []
# 2026-06-27 PM
# 2026-06-27 PM        try:
# 2026-06-27 PM            with open(self.fhicl,'r') as f:
# 2026-06-27 PM                lines = f.readlines()
# 2026-06-27 PM        except OSError as e:
# 2026-06-27 PM            TRACE.ERROR(f"Failed to open {self.fhicl}: {e}", TRACE_NAME)
# 2026-06-27 PM            return new_text
# 2026-06-27 PM
# 2026-06-27 PM        for line in lines:
# 2026-06-27 PM            # print(line);
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*destinations'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                new_text.append(f'{key}: {{\n');
# 2026-06-27 PM                s = destination_string(self,transfer_plugin)
# 2026-06-27 PM                new_text.append(s)
# 2026-06-27 PM                new_text.append('}\n');
# 2026-06-27 PM                continue
# 2026-06-27 PM                
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*max_fragment_size_bytes'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                # in this case, replaces
# 2026-06-27 PM                s      = f'{key}: {self.max_fragment_size_bytes}\n';
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                continue;
# 2026-06-27 PM
# 2026-06-27 PM            new_text.append(line)
# 2026-06-27 PM        
# 2026-06-27 PM        TRACE.DEBUG(1,f'--END: self.label:{self.label}',TRACE_NAME)
# 2026-06-27 PM        return new_text;
# 2026-06-27 PM


# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PMclass EventBuilder(Procinfo):
# 2026-06-27 PM
# 2026-06-27 PM    def __init__(self,
# 2026-06-27 PM                 name  , ##             = pname,
# 2026-06-27 PM                 rank  , ##             = rank ,
# 2026-06-27 PM                 host  , ##             = host ,          # at this point, store long (with '-ctrl' names)
# 2026-06-27 PM                 port  , ##             = str(xmlrpc_port),
# 2026-06-27 PM                 timeout, ##            = timeout,
# 2026-06-27 PM                 label  , ##            = key_name  ,
# 2026-06-27 PM                 subsystem , ##         = subsystem,
# 2026-06-27 PM                 allowed_processors = None,
# 2026-06-27 PM                 target             = "none",
# 2026-06-27 PM                 fhicl              = "no_fcl_fn",
# 2026-06-27 PM                 prepend            = ""
# 2026-06-27 PM                 ):
# 2026-06-27 PM        
# 2026-06-27 PM        super().__init__(name,rank,host,port,timeout,label,subsystem,
# 2026-06-27 PM                         allowed_processors,target,fhicl,prepend)
# 2026-06-27 PM        self._type              = EVENT_BUILDER;
# 2026-06-27 PM        self.execname           = 'eventbuilder'
# 2026-06-27 PM        self.art_analyzer_count = 1;                         # make 1 the default
# 2026-06-27 PM        
# 2026-06-27 PM    def init_connections(self):      # p = self
# 2026-06-27 PM        TRACE.INFO(f'-- START: EventBuilder::init_connections:{self.label}',TRACE_NAME)
# 2026-06-27 PM        # EB has to have inputs - either from own BRs or from other subsystems or EBs from other subcyctems
# 2026-06-27 PM        # start from checking inputs
# 2026-06-27 PM
# 2026-06-27 PM        s = self.subsystem; ## self.subsystems[p.subsystem_id]; # subsystem which a given process belongs to
# 2026-06-27 PM
# 2026-06-27 PM        # BRs should already be covered, check for input from other EBs
# 2026-06-27 PM
# 2026-06-27 PM        # print(f's.sources:{s.sources}');
# 2026-06-27 PM        # print(f'process.list_of_sources:{self.list_of_sources}');
# 2026-06-27 PM
# 2026-06-27 PM        sum_fragment_size_bytes  = 0;               # sum of the BR's input
# 2026-06-27 PM        max_event_size_bytes     = 0;               # max event from input EB's
# 2026-06-27 PM        self.init_fragment_count = 0;
# 2026-06-27 PM
# 2026-06-27 PM        if (len(s.sources) > 0):
# 2026-06-27 PM            TRACE.DEBUG(0,f's.id:{s.id} s.sources:{s.sources}',TRACE_NAME);
# 2026-06-27 PM            for ss in s.list_of_sS:
# 2026-06-27 PM                TRACE.DEBUG(0,f'ss {ss}',TRACE_NAME)
# 2026-06-27 PM                # there should be no DLs in the source subsystem, it should end in EB
# 2026-06-27 PM                if (ss.max_type == EVENT_BUILDER):
# 2026-06-27 PM                    list_of_ebs = ss.list_of_procinfos[EVENT_BUILDER]
# 2026-06-27 PM                    for eb in list_of_ebs:
# 2026-06-27 PM                        self.init_fragment_count += 1
# 2026-06-27 PM                        if (eb.max_event_size_bytes > max_event_size_bytes):
# 2026-06-27 PM                            max_event_size_bytes = eb.max_event_size_bytes;
# 2026-06-27 PM                        # avoid double counting
# 2026-06-27 PM                        if (not eb in self.list_of_sources):
# 2026-06-27 PM                            self.list_of_sources.append(eb);
# 2026-06-27 PM                            eb.list_of_destinations.append(self);
# 2026-06-27 PM
# 2026-06-27 PM                elif (ss.max_type == BOARD_READER):
# 2026-06-27 PM                    list_of_brs = ss.list_of_procinfos[BOARD_READER]
# 2026-06-27 PM                    for br in list_of_brs:
# 2026-06-27 PM                        # it looks that the BRs send fragments, not 'serialized art events'....
# 2026-06-27 PM                        # self.init_fragment_count += 1
# 2026-06-27 PM                        sum_fragment_size_bytes  += br.max_fragment_size_bytes;
# 2026-06-27 PM                        # avoid double counting
# 2026-06-27 PM                        if (not br in self.list_of_sources):
# 2026-06-27 PM                            self.list_of_sources.append(eb);
# 2026-06-27 PM                            eb.list_of_destinations.append(self);
# 2026-06-27 PM            TRACE.DEBUG(0,f'self.init_fragment_count:{self.init_fragment_count}',TRACE_NAME);
# 2026-06-27 PM        else:
# 2026-06-27 PM#-------^----------------------------------------------------------------------
# 2026-06-27 PM# subsystem doesn't have inputs, look at local BRs - those already are in the list of inputs
# 2026-06-27 PM#-----------v------------------------------------------------------------------
# 2026-06-27 PM            for br in self.list_of_sources:
# 2026-06-27 PM                TRACE.DEBUG(0,f'br.label:{br.label} br.max_fragment_size_bytes:{br.max_fragment_size_bytes}',TRACE_NAME)
# 2026-06-27 PM                sum_fragment_size_bytes += br.max_fragment_size_bytes
# 2026-06-27 PM
# 2026-06-27 PM                TRACE.DEBUG(0,f'p.max_event_size_bytes:{self.max_event_size_bytes} self.max_fragment_size_bytes:{self.max_fragment_size_bytes}',TRACE_NAME)
# 2026-06-27 PM
# 2026-06-27 PM
# 2026-06-27 PM        self.max_fragment_size_bytes = sum_fragment_size_bytes;
# 2026-06-27 PM        self.max_event_size_bytes    = sum_fragment_size_bytes+max_event_size_bytes;
# 2026-06-27 PM
# 2026-06-27 PM#---------------------------^--------------------------------------------------
# 2026-06-27 PM# done with the sources
# 2026-06-27 PM# destinations: each EB should also have 'destination' processes tow hich it sends events - either DL's or other EB's (or DSs ?)
# 2026-06-27 PM# first check if the subsystem ahs data loggers
# 2026-06-27 PM#-------v----------------------------------------------------------------------
# 2026-06-27 PM
# 2026-06-27 PM        list_of_dls = s.list_of_procinfos[DATA_LOGGER]
# 2026-06-27 PM        if (len(list_of_dls) > 0):
# 2026-06-27 PM            # subsystem has its own DL(s)
# 2026-06-27 PM            for dl in list_of_dls:
# 2026-06-27 PM                dl.list_of_sources.append(self);
# 2026-06-27 PM                self.list_of_destinations.append(dl);
# 2026-06-27 PM                    
# 2026-06-27 PM        else:
# 2026-06-27 PM            # subsystem has no its own data loggers, so it should have a destination subsystem
# 2026-06-27 PM            sd = s.dS;
# 2026-06-27 PM            if (sd != None):
# 2026-06-27 PM                # subsystem has a destination, that may start with BR, but they will be skipped
# 2026-06-27 PM                # first check EBs in the destination subsystem
# 2026-06-27 PM                list_of_ebs = sd.list_of_procinfos[EVENT_BUILDER]
# 2026-06-27 PM                if (len(list_of_ebs) > 0):
# 2026-06-27 PM                    for eb in list_of_ebs:
# 2026-06-27 PM                        self.list_of_destinations.append(eb);
# 2026-06-27 PM                        eb.list_of_sources.append(self);
# 2026-06-27 PM                else:
# 2026-06-27 PM                    # no EBs, check for DLs
# 2026-06-27 PM                    list_of_dls = sd.list_of_procinfos[DATA_LOGGER]
# 2026-06-27 PM                    if (len(list_of_dls) > 0):
# 2026-06-27 PM                        for dl in list_of_dls:
# 2026-06-27 PM                            self.list_of_destinations.append(dl);
# 2026-06-27 PM                            dl.list_of_sources.append(self);
# 2026-06-27 PM                    else:
# 2026-06-27 PM                        # no EBs/DLss, check for DSs
# 2026-06-27 PM                        list_of_dss = sd.list_of_procinfos[DISPATCHER]
# 2026-06-27 PM                        if (len(list_of_dss) > 0):
# 2026-06-27 PM                            for ds in list_of_dss:
# 2026-06-27 PM                                self.list_of_destinations.append(ds);
# 2026-06-27 PM                                ds.list_of_sources.append(self);
# 2026-06-27 PM                                
# 2026-06-27 PM                            else:
# 2026-06-27 PM                                # a problem , throw
# 2026-06-27 PM                                raise Exception('EB: no EBs/DLs in the DEST');
# 2026-06-27 PM
# 2026-06-27 PM        TRACE.INFO(f'-- END',TRACE_NAME)
# 2026-06-27 PM        return;
# 2026-06-27 PM
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM# EventBuilder: update FCL
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM    def update_fhicl(self, transfer_plugin):
# 2026-06-27 PM        # step 1 : read and replace - start from BRs
# 2026-06-27 PM        TRACE.DEBUG(1,f'EB : self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
# 2026-06-27 PM        
# 2026-06-27 PM        new_text = []
# 2026-06-27 PM
# 2026-06-27 PM        try:
# 2026-06-27 PM            with open(self.fhicl,'r') as f:
# 2026-06-27 PM                lines = f.readlines()
# 2026-06-27 PM        except OSError as e:
# 2026-06-27 PM            TRACE.ERROR(f"Failed to open {self.fhicl}: {e}", TRACE_NAME)
# 2026-06-27 PM            return new_text
# 2026-06-27 PM    
# 2026-06-27 PM        for line in lines:
# 2026-06-27 PM            # print(line);
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*sources'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                new_text.append(f'{key}: {{\n');
# 2026-06-27 PM                # always replace the line with the real string
# 2026-06-27 PM                # max_fragment_size_words is calculated
# 2026-06-27 PM                s = source_string(self,transfer_plugin)
# 2026-06-27 PM                new_text.append(s)
# 2026-06-27 PM                new_text.append('}\n');
# 2026-06-27 PM                continue
# 2026-06-27 PM    
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*destinations'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                new_text.append(f'{key}: {{\n');
# 2026-06-27 PM                s = destination_string(self,transfer_plugin);
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                new_text.append('}\n');
# 2026-06-27 PM                continue;
# 2026-06-27 PM                
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*host_map'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                new_text.append(f'{key}: [');
# 2026-06-27 PM                offset = '    ' # 4 spaces (TCL indent)
# 2026-06-27 PM                s      = host_map_string(self.list_of_destinations,offset);
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                new_text.append(' ]\n');
# 2026-06-27 PM                continue;
# 2026-06-27 PM    
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*max_event_size_bytes'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                # in this case, replaces
# 2026-06-27 PM                s      = f'{key}: {self.max_event_size_bytes}\n';
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                continue;
# 2026-06-27 PM    
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*init_fragment_count'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                # in this case, replaces
# 2026-06-27 PM                s      = f'{key}: {self.init_fragment_count}\n';
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                continue;
# 2026-06-27 PM
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*art_analyzer_count'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                # in this case, replaces
# 2026-06-27 PM                s      = f'{key}: {self.art_analyzer_count}\n';
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                continue;
# 2026-06-27 PM    
# 2026-06-27 PM            new_text.append(line);
# 2026-06-27 PM
# 2026-06-27 PM        TRACE.DEBUG(1,f'END',TRACE_NAME)
# 2026-06-27 PM        return new_text;
# 2026-06-27 PM            
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PMclass DataLogger(Procinfo):
# 2026-06-27 PM
# 2026-06-27 PM    def __init__(self,
# 2026-06-27 PM                 name, ##                = pname,
# 2026-06-27 PM                 rank , ##              = rank ,
# 2026-06-27 PM                 host , ##              = host ,          # at this point, store long (with '-ctrl' names)
# 2026-06-27 PM                 port , ##              = str(xmlrpc_port),
# 2026-06-27 PM                 timeout, ##            = timeout,
# 2026-06-27 PM                 label, ##              = key_name  ,
# 2026-06-27 PM                 subsystem, ##          = subsystem,
# 2026-06-27 PM                 allowed_processors = None,
# 2026-06-27 PM                 target             = "none",
# 2026-06-27 PM                 fhicl              = "no_fcl_fn",
# 2026-06-27 PM                 prepend            = ""
# 2026-06-27 PM                 ):
# 2026-06-27 PM        
# 2026-06-27 PM        super().__init__(name,rank,host,port,timeout,label,subsystem,
# 2026-06-27 PM                         allowed_processors,target,fhicl,prepend)
# 2026-06-27 PM        self._type                 = DATA_LOGGER;
# 2026-06-27 PM        self.execname              = 'datalogger'
# 2026-06-27 PM        self.output_data_directory = None
# 2026-06-27 PM
# 2026-06-27 PM#-------^----------------------------------------------------------------------
# 2026-06-27 PM# define processes for p.type = DATA_LOGGER
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM    def init_connections(self):
# 2026-06-27 PM
# 2026-06-27 PM        TRACE.INFO(f'-- START: p.label:{self.label} p.subsystem_id:{self.subsystem_id}',TRACE_NAME);
# 2026-06-27 PM        # DL has to have inputs from either own EBs or from EBs other subsystems
# 2026-06-27 PM        # start from checking inputs
# 2026-06-27 PM        s = self.subsystem; ## self.subsystems[p.subsystem_id]; # subsystem which a given process belongs to
# 2026-06-27 PM        s.print();
# 2026-06-27 PM        # EBs should already be covered
# 2026-06-27 PM
# 2026-06-27 PM        self.max_event_size_bytes = 0;
# 2026-06-27 PM        self.init_fragment_count  = 0;
# 2026-06-27 PM
# 2026-06-27 PM        if ((len(s.list_of_sS) > 0) and (s.min_type == DATA_LOGGER)):
# 2026-06-27 PM            # subsystem has sources, and there is no local  EBs
# 2026-06-27 PM            # can take input from the upstream EBs
# 2026-06-27 PM            for ss in s.list_of_sS:
# 2026-06-27 PM                # there should be no DLs in the source subsystem, it should end with  the EBs
# 2026-06-27 PM                if (ss.max_type == EVENT_BUILDER):
# 2026-06-27 PM                    list_of_ebs = ss.list_of_event_builders()
# 2026-06-27 PM                    for eb in list_of_ebs:
# 2026-06-27 PM                        self.init_fragment_count += eb.art_analyzer_count;
# 2026-06-27 PM                        
# 2026-06-27 PM                        if (eb.max_event_size_bytes > self.max_event_size_bytes):
# 2026-06-27 PM                            self.max_event_size_bytes =  eb.max_event_size_bytes
# 2026-06-27 PM    
# 2026-06-27 PM                        # avoid double counting
# 2026-06-27 PM                        if (not eb in self.list_of_sources):
# 2026-06-27 PM                            self.list_of_sources.append(eb);
# 2026-06-27 PM                            eb.list_of_destinations.append(self);
# 2026-06-27 PM                            
# 2026-06-27 PM            TRACE.INFO(f'self.init_fragment_count:{self.init_fragment_count}',TRACE_NAME);
# 2026-06-27 PM#-------------------------------^----------------------------------------------
# 2026-06-27 PM# no source subsystems or those start from DLs - look for local inputs
# 2026-06-27 PM# counting logic: an init fragment per each art process
# 2026-06-27 PM#-------v----------------------------------------------------------------------
# 2026-06-27 PM        else:
# 2026-06-27 PM            # subsystem has no official sources, there should be local EB's
# 2026-06-27 PM            list_of_ebs = s.list_of_event_builders()
# 2026-06-27 PM            if (len(list_of_ebs) > 0):
# 2026-06-27 PM                for eb in list_of_ebs:
# 2026-06-27 PM                    self.init_fragment_count += eb.art_analyzer_count;
# 2026-06-27 PM                    if (eb.max_event_size_bytes > self.max_event_size_bytes):
# 2026-06-27 PM                        self.max_event_size_bytes =  eb.max_event_size_bytes
# 2026-06-27 PM                        
# 2026-06-27 PM                    if (not eb in self.list_of_sources):
# 2026-06-27 PM                        self.list_of_sources.append(eb);
# 2026-06-27 PM                        eb.list_of_destinations.append(self);
# 2026-06-27 PM                    
# 2026-06-27 PM            else:
# 2026-06-27 PM                # subsystem has no own EB's : trouble
# 2026-06-27 PM                raise Exception('DL: no EBs in the subsystem');
# 2026-06-27 PM
# 2026-06-27 PM            TRACE.INFO(f'self.init_fragment_count:{self.init_fragment_count}',TRACE_NAME);
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM# now - destinations ... not done yet
# 2026-06-27 PM#-------v----------------------------------------------------------------------
# 2026-06-27 PM        list_of_dss = s.list_of_dispatchers()
# 2026-06-27 PM        if (len(list_of_dss) > 0):
# 2026-06-27 PM            for ds in list_of_dss:
# 2026-06-27 PM                self.init_fragment_count += 1;
# 2026-06-27 PM                        
# 2026-06-27 PM                if (not ds in self.list_of_destinations):
# 2026-06-27 PM                    self.list_of_destinations.append(ds);
# 2026-06-27 PM                    ds.list_of_sources.append(self);
# 2026-06-27 PM
# 2026-06-27 PM        TRACE.ERROR(f'DL {self.label} no destinations defined - FIXME',TRACE_NAME)
# 2026-06-27 PM        return;
# 2026-06-27 PM
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM#  DataLogger
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM    def update_fhicl(self, transfer_plugin):
# 2026-06-27 PM        TRACE.INFO(f'-- START: self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
# 2026-06-27 PM        
# 2026-06-27 PM        with open(self.fhicl,'r') as f:
# 2026-06-27 PM            lines = f.readlines()
# 2026-06-27 PM    
# 2026-06-27 PM        new_text = []
# 2026-06-27 PM
# 2026-06-27 PM        for line in lines:
# 2026-06-27 PM            # print(line);
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*sources'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                new_text.append(f'{key}: {{\n');
# 2026-06-27 PM                s = source_string(self,transfer_plugin)
# 2026-06-27 PM                new_text.append(s)
# 2026-06-27 PM                new_text.append('}\n');
# 2026-06-27 PM                continue
# 2026-06-27 PM
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*destinations'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                s = destination_string(self,transfer_plugin);
# 2026-06-27 PM                if (s):
# 2026-06-27 PM                    key = match.group(0);
# 2026-06-27 PM                    new_text.append(f'{key}: {{\n');
# 2026-06-27 PM                    new_text.append(s);
# 2026-06-27 PM                    new_text.append('}\n');
# 2026-06-27 PM                    continue;
# 2026-06-27 PM                
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*host_map'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                new_text.append(f'{key}: [');
# 2026-06-27 PM                offset = '    ' ## 4 spaces, TCL indent
# 2026-06-27 PM                # host_map_string - always destinations
# 2026-06-27 PM                s = host_map_string(self.list_of_destinations,offset);
# 2026-06-27 PM                TRACE.INFO(f'self.label:{self.label} host_map_string:{s}',TRACE_NAME)
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                new_text.append(' ]\n');
# 2026-06-27 PM                continue;
# 2026-06-27 PM    
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*max_event_size_bytes'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                # in this case, replaces
# 2026-06-27 PM                s      = f'{key}: {self.max_event_size_bytes+800000}\n';
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                continue;
# 2026-06-27 PM
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*init_fragment_count'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                # in this case, replaces
# 2026-06-27 PM                s      = f'{key}: {self.init_fragment_count}\n';
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                continue;
# 2026-06-27 PM
# 2026-06-27 PM            #------------------------------------------------------------------------------
# 2026-06-27 PM            # any other line - just rewrite
# 2026-06-27 PM            #------------------------------------------------------------------------------
# 2026-06-27 PM            new_text.append(line);
# 2026-06-27 PM
# 2026-06-27 PM        TRACE.INFO(f'-- END: self.label:{self.label}',TRACE_NAME)
# 2026-06-27 PM        return new_text;
# 2026-06-27 PM
# 2026-06-27 PM#-------^----------------------------------------------------------------------
# 2026-06-27 PMclass Dispatcher(Procinfo):
# 2026-06-27 PM
# 2026-06-27 PM    def __init__(self,
# 2026-06-27 PM                 name, ##              = pname,
# 2026-06-27 PM                 rank, ##               = rank ,
# 2026-06-27 PM                 host, ##               = host ,          # at this point, store long (with '-ctrl' names)
# 2026-06-27 PM                 port, ##               = str(xmlrpc_port),
# 2026-06-27 PM                 timeout, ##            = timeout,
# 2026-06-27 PM                 label, ##              = key_name  ,
# 2026-06-27 PM                 subsystem, ##          = subsystem,
# 2026-06-27 PM                 allowed_processors = None,
# 2026-06-27 PM                 target             = "none",
# 2026-06-27 PM                 fhicl              = "no_fcl_fn",
# 2026-06-27 PM                 prepend            = ""
# 2026-06-27 PM                 ):
# 2026-06-27 PM        
# 2026-06-27 PM        super().__init__(name,rank,host,port,timeout,label,subsystem,
# 2026-06-27 PM                         allowed_processors,target,fhicl,prepend)
# 2026-06-27 PM        self._type    = DISPATCHER;
# 2026-06-27 PM        self.execname = 'dispatcher'
# 2026-06-27 PM        
# 2026-06-27 PM
# 2026-06-27 PM
# 2026-06-27 PM    def init_connections(self):
# 2026-06-27 PM        # DS only has inputs ..DLs ? start from checking inputs
# 2026-06-27 PM        s = self.subsystem; ## self.subsystems[p.subsystem_id]; # subsystem which a given process belongs to
# 2026-06-27 PM
# 2026-06-27 PM        if (len(s.list_of_sS) > 0):
# 2026-06-27 PM            # THERE ARE INPUT SUBSYSTEMS, thus there should be no local inputs
# 2026-06-27 PM            # for now, assume correct inputs, handle errors later
# 2026-06-27 PM            for ss in s.list_of_sS:               ## source in s.sources:
# 2026-06-27 PM                # there should be DLs in the source subsystem
# 2026-06-27 PM                if (ss.max_type >= DATA_LOGGER):
# 2026-06-27 PM                    # it might make sense to allow a DL to send events to DSs anywhere,
# 2026-06-27 PM                    # although need to check the logic
# 2026-06-27 PM                    plist = ss.list_of_data_loggers()
# 2026-06-27 PM                    for x in plist:
# 2026-06-27 PM                        # avoid double counting - just in case
# 2026-06-27 PM                        if (not x in self.list_of_sources):
# 2026-06-27 PM                            self.list_of_sources.append(x);
# 2026-06-27 PM                            x.list_of_destinations.append(self);
# 2026-06-27 PM                else:
# 2026-06-27 PM                    # ss has no DLs, check EBs 
# 2026-06-27 PM                    plist = ss.list_of_event_builders();
# 2026-06-27 PM                    for x in plist:
# 2026-06-27 PM                        # avoid double counting - just in case
# 2026-06-27 PM                        if (not x in self.list_of_sources):
# 2026-06-27 PM                            self.list_of_sources.append(x);
# 2026-06-27 PM                            x.list_of_destinations.append(self);
# 2026-06-27 PM#---------------------------^--------------------------------------------------
# 2026-06-27 PM# no input sources , check local inputs
# 2026-06-27 PM#-------v----------------------------------------------------------------------
# 2026-06-27 PM        else:
# 2026-06-27 PM            plist = s.list_of_data_loggers()
# 2026-06-27 PM            if (len(plist) > 0):
# 2026-06-27 PM                # DLs available, local EBs should be talking to them
# 2026-06-27 PM                for x in plist:
# 2026-06-27 PM                    self.list_of_sources.append(x);
# 2026-06-27 PM                    x.list_of_destinations.append(self);
# 2026-06-27 PM                    
# 2026-06-27 PM            else:
# 2026-06-27 PM                # subsystem has no own data loggers, look for event builders
# 2026-06-27 PM                plist = s.list_of_event_builders()
# 2026-06-27 PM                if (len(plist) > 0):
# 2026-06-27 PM                    # DLs available, local EBs should be talking to them
# 2026-06-27 PM                    for x in plist:
# 2026-06-27 PM                        if (not x in dl.list_of_sources):
# 2026-06-27 PM                            self.list_of_sources.append(x);
# 2026-06-27 PM                            x.list_of_destinations.append(self);
# 2026-06-27 PM                else:
# 2026-06-27 PM                    # a problem , throw
# 2026-06-27 PM                    raise Exception('Dispatcher::init_connections: DS: no local DLs or EBs');
# 2026-06-27 PM        return;
# 2026-06-27 PM
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM# DS - to be impemented
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM    def update_fhicl(self, transfer_plugin):
# 2026-06-27 PM        print('------ DS::update_fhicl')
# 2026-06-27 PM        TRACE.INFO(f'self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
# 2026-06-27 PM        
# 2026-06-27 PM        raise Exception('DISPATCHER: IMPLEMENT ME!')
# 2026-06-27 PM
# 2026-06-27 PM        with open(self.fhicl,'r') as f:
# 2026-06-27 PM            lines = f.readlines()
# 2026-06-27 PM    
# 2026-06-27 PM        new_text = []
# 2026-06-27 PM    
# 2026-06-27 PM        for line in lines:
# 2026-06-27 PM            # print(line);
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*sources'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                new_text.append(f'{key}: {{\n');
# 2026-06-27 PM                s = source_string(self,transfer_plugin)
# 2026-06-27 PM                new_text.append(s)
# 2026-06-27 PM                new_text.append('}\n');
# 2026-06-27 PM                continue
# 2026-06-27 PM    
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*destinations'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                new_text.append(f'{key}: {{\n');
# 2026-06-27 PM                s = destination_string(self,transfer_plugin);
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                new_text.append('}\n');
# 2026-06-27 PM                continue;
# 2026-06-27 PM                
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*host_map'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                new_text.append(f'{key}: [');
# 2026-06-27 PM                offset = '    ' ## 4 spaces, TCL indent
# 2026-06-27 PM                # host_map_string - always destinations
# 2026-06-27 PM                s = host_map_string(self.list_of_destinations,offset);
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                new_text.append(' ]\n');
# 2026-06-27 PM                continue;
# 2026-06-27 PM    
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*max_event_size_bytes'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                # in this case, replaces
# 2026-06-27 PM                s      = f'{key}: {self.max_event_size_bytes}\n';
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                continue;
# 2026-06-27 PM    
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*init_fragment_count'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                # in this case, replaces
# 2026-06-27 PM                s      = f'{key}: {self.init_fragment_count}\n';
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                continue;
# 2026-06-27 PM            
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM# any other line - just rewrite
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM            new_text.append(line);
# 2026-06-27 PM    
# 2026-06-27 PM        return new_text;
# 2026-06-27 PM   
# 2026-06-27 PM
#-------^----------------------------------------------------------------------
# 2026-06-27 PMclass RoutingManager(Procinfo):
# 2026-06-27 PM
# 2026-06-27 PM    def __init__(self,
# 2026-06-27 PM                 name, ##               = pname,
# 2026-06-27 PM                 rank, ##               = rank ,
# 2026-06-27 PM                 host, ##               = host ,          # at this point, store long (with '-ctrl' names)
# 2026-06-27 PM                 port, ##               = str(xmlrpc_port),
# 2026-06-27 PM                 timeout, ##            = timeout,
# 2026-06-27 PM                 label, ##              = key_name  ,
# 2026-06-27 PM                 subsystem, ##          = subsystem,
# 2026-06-27 PM                 allowed_processors = None,
# 2026-06-27 PM                 target             = "none",
# 2026-06-27 PM                 fhicl              = "no_fcl_fn",
# 2026-06-27 PM                 prepend            = ""
# 2026-06-27 PM                 ):
# 2026-06-27 PM        
# 2026-06-27 PM        super().__init__(name,rank,host,port,timeout,label,subsystem,
# 2026-06-27 PM                         allowed_processors,target,fhicl,prepend)
# 2026-06-27 PM        self._type    = ROUTING_MANAGER;
# 2026-06-27 PM        self.execname = 'routing_manager'
# 2026-06-27 PM
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM# define processes for p.type = ROUTINE_MANAGER
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM    def rm_connections(self):
# 2026-06-27 PM        raise Exception('RoutingManager::init_connection: not implemented yet');
# 2026-06-27 PM
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM# RM - to be impemented
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM    def update_fhicl(self, transfer_plugin):
# 2026-06-27 PM        print('------ RM::update_fhicl')
# 2026-06-27 PM        TRACE.INFO(f'self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
# 2026-06-27 PM        
# 2026-06-27 PM        raise Exception('DISPATCHER: IMPLEMENT ME!')
# 2026-06-27 PM
# 2026-06-27 PM        with open(self.fhicl,'r') as f:
# 2026-06-27 PM            lines = f.readlines()
# 2026-06-27 PM    
# 2026-06-27 PM        new_text = []
# 2026-06-27 PM    
# 2026-06-27 PM        for line in lines:
# 2026-06-27 PM            # print(line);
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*sources'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                new_text.append(f'{key}: {{\n');
# 2026-06-27 PM                s = source_string(self,transfer_plugin)
# 2026-06-27 PM                new_text.append(s)
# 2026-06-27 PM                new_text.append('}\n');
# 2026-06-27 PM                continue
# 2026-06-27 PM    
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*destinations'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                s = destination_string(self,transfer_plugin);
# 2026-06-27 PM                if (s):
# 2026-06-27 PM                    key = match.group(0);
# 2026-06-27 PM                    new_text.append(f'{key}: {{\n');
# 2026-06-27 PM                    new_text.append(s);
# 2026-06-27 PM                    new_text.append('}\n');
# 2026-06-27 PM                    continue;
# 2026-06-27 PM                
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*host_map'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                new_text.append(f'{key}: [');
# 2026-06-27 PM                offset = '    ' ## 4 spaces, TCL indent
# 2026-06-27 PM                # host_map_string - always destinations
# 2026-06-27 PM                s = host_map_string(self.list_of_destinations,offset);
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                new_text.append(' ]\n');
# 2026-06-27 PM                continue;
# 2026-06-27 PM    
# 2026-06-27 PM            pattern = r'(?:[\w-]+\.)*max_event_size_bytes'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                # in this case, replaces
# 2026-06-27 PM                s      = f'{key}: {self.max_event_size_bytes}\n';
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                continue;
# 2026-06-27 PM    
# 2026-06-27 PM            pattern = r'^(?!#)(?:[\w-]+\.)*init_fragment_count'
# 2026-06-27 PM            match = re.search(pattern,line)
# 2026-06-27 PM            if (match):
# 2026-06-27 PM                key = match.group(0);
# 2026-06-27 PM                # in this case, replaces
# 2026-06-27 PM                s      = f'{key}: {self.init_fragment_count}\n';
# 2026-06-27 PM                new_text.append(s);
# 2026-06-27 PM                continue;
# 2026-06-27 PM            
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM# any other line - just rewrite
# 2026-06-27 PM#------------------------------------------------------------------------------
# 2026-06-27 PM            new_text.append(line);
# 2026-06-27 PM    
# 2026-06-27 PM        return new_text;
# 2026-06-27 PM
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
