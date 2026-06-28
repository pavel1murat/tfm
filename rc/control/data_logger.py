#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
import os, sys, argparse, glob, inspect, re, subprocess
import tfm.rc.control.utilities as rcu

from   tfm.rc.control.procinfo  import Procinfo, host_map_string, BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ;
from   pathlib                  import Path
from   datetime                 import datetime
from   zoneinfo                 import ZoneInfo

import TRACE ; TRACE_NAME='data_logger'

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
                s = self.source_string(transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue

            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                s = self.destination_string(transfer_plugin);
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
