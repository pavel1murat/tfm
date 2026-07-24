#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
import os, sys, argparse, glob, inspect, re, subprocess
import tfm.rc.control.utilities as rcu

from   tfm.rc.control.procinfo  import Procinfo, BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ;
from   pathlib                  import Path
from   datetime                 import datetime
from   zoneinfo                 import ZoneInfo

import TRACE ; TRACE_NAME='board_reader'

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

        self._process_type = BOARD_READER;
        self.execname      = 'boardreader'

#------------------------------------------------------------------------------
    def connect_event_builder(self,eb):
        self.list_of_destinations.append(eb);
        eb.list_of_sources.append(self);
        eb.exp_fragments_per_event += self.n_fragment_ids()
        max_sum_fragment_sizes      = self.n_fragment_ids()*self.max_fragment_size_bytes;
        eb.max_event_size_bytes    += max_sum_fragment_sizes;
        # max size of data from one destination
        if (max_sum_fragment_sizes > eb.max_fragment_size_bytes):
            eb.max_fragment_size_bytes = max_sum_fragment_sizes;
        
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
                if (not eb in self.list_of_destinations):
                    self.connect_event_builder(eb)
        else:
            # subsystem has only BRs, check subsystem destination
            TRACE.INFO(f'-- [BoardReader::init_connections] self.label:{self.label} s.destination:{s.destination}',TRACE_NAME)
            if (s.destination != None):
                # subsystem has a destination, that has to have EBs
                TRACE.INFO(f'subsystem:{s.id} destination is not NONE, but :"{s.destination}"',TRACE_NAME)
                sd = s.dS;                  # destination subsystem, ## self.subsystems[s.destination];
                list_of_ebs = sd.list_of_procinfos[EVENT_BUILDER]
                TRACE.DEBUG(1,f'-- [BoardReader::init_connections] sd.id:{sd.id} len(list_of_ebs):{len(list_of_ebs)}',TRACE_NAME)
                
                for eb in list_of_ebs:
                    TRACE.INFO(f'-- [init_br_connections] append {eb.label} to the destinations of {self.label}',TRACE_NAME)
                    if (not eb in self.list_of_destinations):
                        self.connect_event_builder(eb);
            else:
                # the subsystem has only BRs', that is a problem
                raise Exception(f'ERROR: subsystem:{s.id} has only BRs and no destination. FIX IT.')
        return;

#------------------------------------------------------------------------------
# BoardReader: return updated , not not yet expanded FCL
#------------------------------------------------------------------------------
    def update_fhicl(self): ## ,transfer_plugin):
        # step 1 : read and replace - start from BRs
        TRACE.DEBUG(1,f'--START: self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)

        new_text = []

        try:
            with open(self.fhicl,'r') as f:
                lines = f.readlines()
        except OSError as e:
            TRACE.ERROR(f"Failed to open {self.fhicl}: {e}", TRACE_NAME)
            return new_text

        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                #<2026-07-21 PM>s = self.destination_string(transfer_plugin)
                s = self.destination_string(self.output_plugin)
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



