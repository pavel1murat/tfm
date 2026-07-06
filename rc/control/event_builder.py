#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
import os, sys, argparse, glob, inspect, re, subprocess
import tfm.rc.control.utilities as rcu

from   tfm.rc.control.procinfo  import Procinfo, host_map_string, BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ;
from   pathlib                  import Path
from   datetime                 import datetime
from   zoneinfo                 import ZoneInfo

import TRACE ; TRACE_NAME='event_builder'

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
        self._type                   = EVENT_BUILDER;
        self.execname                = 'eventbuilder'
        self.art_analyzer_count      = 1;                         # make 1 the default
        self.exp_fragments_per_event = 0             ## may be different for an EB
        
    def init_connections(self):      # p = self
        TRACE.DEBUG(1,f'-- START: EventBuilder::init_connections:{self.label}',TRACE_NAME)
        # EB has to have inputs - either from own BRs or from other subsystems or EBs from other subsystems
        # start from checking inputs

        s = self.subsystem; ## self.subsystems[p.subsystem_id]; # subsystem which a given process belongs to

        # BRs should already be covered, check for input from other EBs

        # print(f's.sources:{s.sources}');
        # print(f'process.list_of_sources:{self.list_of_sources}');

        sum_fragment_size_bytes      = 0;               # sum of the BR's input
        max_event_size_bytes         = 0;               # max event from input EB's
        self.init_fragment_count     = 0;
        exp_fragments                = 0;               #
        
        # first, check input (source) subsystems, if any
        if (len(s.sources) > 0):
            TRACE.DEBUG(1,f's.id:{s.id} s.sources:{s.sources}',TRACE_NAME);
            for ss in s.list_of_sS:
                TRACE.DEBUG(1,f'ss {ss}',TRACE_NAME)
                # there should be no DLs in the source subsystem, it should end with the EB layer
                if (ss.max_type == EVENT_BUILDER):
                    list_of_ebs = ss.list_of_procinfos[EVENT_BUILDER]
                    for eb in list_of_ebs:
                        self.init_fragment_count += 1
                        if (eb.max_event_size_bytes > max_event_size_bytes):
                            max_event_size_bytes = eb.max_event_size_bytes;
                            # logically, EB sends out one 'fragment' - is that true ?
                            exp_fragments       += 1;
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
            TRACE.DEBUG(1,f'self.init_fragment_count:{self.init_fragment_count}',TRACE_NAME);
        else:
#-------^----------------------------------------------------------------------
# subsystem doesn't have inputs, look at local BRs - those already are in the list of inputs
#-----------v------------------------------------------------------------------
            for br in self.list_of_sources:
                TRACE.DEBUG(1,f'br.label:{br.label} br.max_fragment_size_bytes:{br.max_fragment_size_bytes} br.n_fragment_ids:{br.n_fragment_ids()}',TRACE_NAME)
                sum_fragment_size_bytes += br.max_fragment_size_bytes
                exp_fragments           += br.n_fragment_ids();
                
        self.max_fragment_size_bytes = sum_fragment_size_bytes;
        self.max_event_size_bytes    = sum_fragment_size_bytes+max_event_size_bytes;
        self.exp_fragments_per_event = exp_fragments;

        TRACE.DEBUG(1,f'self.max_event_size_bytes:{self.max_event_size_bytes} self.max_fragment_size_bytes:{self.max_fragment_size_bytes}',TRACE_NAME)
        TRACE.DEBUG(1,f'self.exp_fragments_per_event:{self.exp_fragments_per_event}',TRACE_NAME)
#---------------------------^--------------------------------------------------
# done with the sources
# destinations: each EB should also have 'destination' processes to which it sends events - either DL's or other EB's (or DSs ?)
# first check if the subsystem ahs data loggers
#-------v----------------------------------------------------------------------

        list_of_dls = s.list_of_procinfos[DATA_LOGGER]
        TRACE.DEBUG(1,f's.id:{s.id} list_of_dls:{list_of_dls}',TRACE_NAME)
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

        TRACE.DEBUG(1,f'-- END',TRACE_NAME)
        return;

#------------------------------------------------------------------------------
# EventBuilder: update FCL
#------------------------------------------------------------------------------
    def update_fhicl(self, transfer_plugin):
        # step 1 : read and replace - start from BRs
        TRACE.DEBUG(1,f'EB : self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
        TRACE.INFO(f'self.list_of_destinations:{self.list_of_destinations}')
        
        new_text = []

        try:
            with open(self.fhicl,'r') as f:
                lines = f.readlines()
        except OSError as e:
            TRACE.ERROR(f"Failed to open {self.fhicl}: {e}", TRACE_NAME)
            return new_text
    
        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*sources'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                # always replace the line with the real string
                # max_fragment_size_words is calculated
                s = self.source_string(transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue
    
            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                TRACE.INFO(f"---- AAAAAA key : {key} transfer_plugin:{transfer_plugin}",TRACE_NAME)
                new_text.append(f'{key}: {{\n');
                s = self.destination_string(transfer_plugin);
                TRACE.INFO(f"----- AAAA destination string: {s}",TRACE_NAME)
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

            pattern = r'(?:[\w-]+\.)*expected_fragments_per_event'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {self.exp_fragments_per_event}\n';
                new_text.append(s);
                continue;
    
            new_text.append(line);

        TRACE.DEBUG(1,f'END',TRACE_NAME)
        return new_text;
