#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
import os, sys, argparse, glob, inspect, re, subprocess
import tfm.rc.control.utilities as rcu

from   tfm.rc.control.procinfo  import Procinfo, host_map_string, BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ;
from   pathlib                  import Path
from   datetime                 import datetime
from   zoneinfo                 import ZoneInfo

import TRACE ; TRACE_NAME='routing_manager'

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
                s = self.source_string(transfer_plugin)   # from ProcInfo
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
