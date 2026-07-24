#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
import os, sys, argparse, glob, inspect, re, subprocess
import tfm.rc.control.utilities as rcu

from   tfm.rc.control.procinfo  import Procinfo, host_map_string, BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ;
from   pathlib                  import Path
from   datetime                 import datetime
from   zoneinfo                 import ZoneInfo

import TRACE ; TRACE_NAME='dispatcher'

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
        self._process_type = DISPATCHER;
        self.execname      = 'dispatcher'
        

#------------------------------------------------------------------------------
    def init_connections(self):
        # DS only has inputs ..DLs ? start from checking inputs
        s = self.subsystem; ## self.subsystems[p.subsystem_id]; # subsystem which a given process belongs to

        # self.max_event_size_bytes = 0;
        # self.init_fragment_count  = 0;
        
        if (len(s.list_of_sS) > 0):
            # THERE ARE INPUT SUBSYSTEMS, thus there should be no local inputs
            # for now, assume correct inputs, handle errors later
            TRACE.INFO(f's.list_of_sS:{s.list_of_sS}',TRACE_NAME);
            for ss in s.list_of_sS:               ## source in s.sources:
                # there should be DLs in the source subsystem
                if (ss.max_type >= DATA_LOGGER):
                    # it might make sense to allow a DL to send events to DSs anywhere,
                    # although need to check the logic
                    plist = ss.list_of_data_loggers()
                    for x in plist:
                        # sanity check - shouldn't do anything
                        if (not x in self.list_of_sources):
                            raise Exception(f'process {x.label} should have been accounted for as input')
 
                else:
                    # ss has no DLs, check EBs - they also should've been handled
                    plist = ss.list_of_event_builders();
                    for x in plist:
                        if (not x in self.list_of_sources):
                            raise Exception(f'DS {self.label} : process {x.label} should have been already accounted for as input')
                            
#-----------^--------------------------------------------------
# no input sources , check local inputs
#-------v----------------------------------------------------------------------
        else:
            plist = s.list_of_data_loggers()
            TRACE.INFO(f'list of DLs:{plist}',TRACE_NAME)
            if (len(plist) > 0):
                # DLs available, local DSs should be talking to them
                for x in plist:
                    if (not x in self.list_of_sources):
                        raise Exception(f'DS {self.label} : process {x.label} should have been already accounted for as input')
            else:
                # subsystem has no own data loggers, look for event builders - in principle, those
                # may also send data to dispatchers
                plist = s.list_of_event_builders()
                TRACE.INFO(f'list of EBs:{plist}',TRACE_NAME)
                if (len(plist) > 0):
                    # no DLs, but EBs available, DS gets input from them
                    for x in plist:
                        if (not x in self.list_of_sources):
                            raise Exception(f'DS {self.label} : process {x.label} should have been already accounted for as input')
                else:
                    # a problem , throw
                    raise Exception('Dispatcher::init_connections: DS: no local DLs or EBs');
        return;

#------------------------------------------------------------------------------
# DS - to be impemented
#------------------------------------------------------------------------------
    def update_fhicl(self): ## , transfer_plugin):
        print('------ DS::update_fhicl')
        TRACE.INFO(f'self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
        
        # raise Exception('DISPATCHER: IMPLEMENT ME!')

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
                #<2026-07-21 PM>s = self.source_string(transfer_plugin)
                s = self.source_string(self.input_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue
    
            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                #<2026-07-21 PM>s = self.destination_string(transfer_plugin);
                s = self.destination_string(self.output_plugin);
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
