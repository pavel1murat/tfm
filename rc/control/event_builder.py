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
        self._process_type           = EVENT_BUILDER;
        self.execname                = 'eventbuilder'
        self.art_analyzer_count      = 1;                         # make 1 the default
        self.exp_fragments_per_event = 0             ## may be different for an EB

#------------------------------------------------------------------------------
# event builder on input
#------------------------------------------------------------------------------
    def connect_event_builder(self,eb):
        TRACE.DEBUG(1,f'--START:')
        self.list_of_sources.append(eb);
        self.init_fragment_count     += 1
        self.exp_fragments_per_event += 1
        self.max_event_size_bytes    += eb.max_event_size_bytes;
        if (eb.max_event_size_bytes > self.max_fragment_size_bytes):
            self.max_fragment_size_bytes = eb.max_event_size_bytes;
                                # logically, EB sends out one 'fragment' - is that true ?

        eb.list_of_destinations.append(self)
        TRACE.DEBUG(1,f'--END:')
        return

#------------------------------------------------------------------------------
    def connect_data_logger(self,dl):
        TRACE.DEBUG(1,f'--START:')
        self.list_of_destinations.append(dl)
    
        dl.list_of_sources.append(self)
        dl.init_fragment_count += self.art_analyzer_count
        TRACE.DEBUG(1,f'',TRACE_NAME)
        if (self.max_event_size_bytes > dl.max_event_size_bytes):
            dl.max_event_size_bytes =  self.max_event_size_bytes

        dl.print_parameters()
        
        TRACE.DEBUG(1,f'--END: dl.max_event_size_bytes:{dl.max_event_size_bytes}')
        return

#------------------------------------------------------------------------------
    def connect_dispatcher(self,ds):
        TRACE.DEBUG(1,f'--START:')
        self.list_of_destinations.append(ds)
    
        ds.list_of_sources.append(self)
        ds.init_fragment_count += self.art_analyzer_count
        if (self.max_event_size_bytes > ds.max_event_size_bytes):
            ds.max_event_size_bytes =  self.max_event_size_bytes

        TRACE.DEBUG(1,f'--END:')
        return

#------------------------------------------------------------------------------
    def init_connections(self):      # p = self
        TRACE.DEBUG(1,f'-- START: EventBuilder::init_connections:{self.label}',TRACE_NAME)
        # EB has to have inputs - either from own BRs or from other subsystems or EBs from other subsystems
        # start from checking inputs

        s = self.subsystem; ## self.subsystems[p.subsystem_id]; # subsystem which a given process belongs to

        # BRs should already be covered, check for input from other EBs

        # print(f's.sources:{s.sources}');
        # print(f'process.list_of_sources:{self.list_of_sources}');

        #  sum_fragment_size_bytes      = 0;               # sum of the BR's input
        # max_event_size_bytes         = 0;               # max event from input EB's
        # self.init_fragment_count     = 0;             done in constructor
        # exp_fragments                = 0;               #
        
        # first, check input (source) subsystems, if any - there could be EBs 
        if (len(s.sources) > 0):
            TRACE.DEBUG(1,f'self.label:{self.label} s.sources:{s.sources}',TRACE_NAME);
            for ss in s.list_of_sS:
                TRACE.DEBUG(1,f'self.label:{self.label}: ss {ss}',TRACE_NAME)
                # there should be no DLs in the source subsystem, it should end with the EB layer
                if (ss.max_type == EVENT_BUILDER):
                    list_of_ebs = ss.list_of_procinfos[EVENT_BUILDER]
                    for eb in list_of_ebs:
                        if (not eb in self.list_of_sources):
                            self.connect_event_builder(eb)

                elif (ss.max_type == BOARD_READER):
                    # BRs should have already been handled
                    list_of_brs = ss.list_of_procinfos[BOARD_READER]
                    for br in list_of_brs:
                        if (not br in self.list_of_sources):
                            raise RunTimeError(f'process {br.label} should have been accounted for as input')

            TRACE.DEBUG(1,f'self.label:{self.label}: self.init_fragment_count:{self.init_fragment_count}',TRACE_NAME);
#-------^----------------------------------------------------------------------
# subsystem doesn't have inputs, look at local BRs - those already are in the list of inputs
#-------v----------------------------------------------------------------------

        TRACE.DEBUG(1,f'self.label:{self.label}: self.max_event_size_bytes:{self.max_event_size_bytes} self.max_fragment_size_bytes:{self.max_fragment_size_bytes}',TRACE_NAME)
        TRACE.DEBUG(1,f'self.label:{self.label}: self.exp_fragments_per_event:{self.exp_fragments_per_event}',TRACE_NAME)
#---------------------------^--------------------------------------------------
# done with the sources
# destinations: each EB should also have 'destination' processes to which it sends events - either DL's or other EB's (or DSs ?)
# first check if the subsystem ahs data loggers
#-------v----------------------------------------------------------------------

        list_of_dls = s.list_of_procinfos[DATA_LOGGER]
        TRACE.DEBUG(1,f'self.label:{self.label}: s.id:{s.id} list_of_dls:{list_of_dls}',TRACE_NAME)
        if (len(list_of_dls) > 0):
            # subsystem has its own DL(s)
            for dl in list_of_dls:
                if (not dl in self.list_of_destinations):
                    self.connect_data_logger(dl);
                    TRACE.DEBUG(1,f'self.label:{self.label}: dl.max_event_size_bytes:{dl.max_event_size_bytes}',TRACE_NAME)

        else:
            # subsystem has no its own data loggers, so it should have a destination subsystem
            sd = s.dS;
            if (sd != None):
                # subsystem has a destination, that may start with BR, but they will be skipped
                # first check EBs in the destination subsystem
                list_of_ebs = sd.list_of_procinfos[EVENT_BUILDER]
                if (len(list_of_ebs) > 0):
                    for eb in list_of_ebs:
                        if (not eb in self.list_of_destinations):
                            eb.connect_event_builder(self)
                            
                else:
                    # no EBs, check for DLs of DSs
                    list_of_dls = sd.list_of_procinfos[DATA_LOGGER]
                    if (len(list_of_dls) > 0):
                        for dl in list_of_dls:
                            if (not dl in self.list_of_destinations):
                                self.connect_data_logger(dl)

                    else:
                        # no EBs/DLss, check for DSs
                        list_of_dss = sd.list_of_procinfos[DISPATCHER]
                        if (len(list_of_dss) > 0):
                            for ds in list_of_dss:
                                if (not ds in self.list_of_destinations):
                                    self.connect_dispatcher(ds);

                            else:
                                # a problem , throw
                                raise Exception(f's.id:{s.id}: EB: no EBs/DLs in the DEST');

        TRACE.DEBUG(1,f'-- END: self.label:{self.label} self.max_event_size_bytes:{self.max_event_size_bytes}',TRACE_NAME)
        return;

#------------------------------------------------------------------------------
# EventBuilder: update FCL
#------------------------------------------------------------------------------
    def update_fhicl(self): ## , transfer_plugin):
        # step 1 : read and replace - start from BRs
        TRACE.DEBUG(1,f'--START: EB : self.label:{self.label} self.fhicl:{self.fhicl}',TRACE_NAME)
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
                #<2026-07-21 PM>s = self.source_string(transfer_plugin)
                s = self.source_string(self.input_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue
    
            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                TRACE.INFO(f"---- AAAAAA key : {key}",TRACE_NAME)
                new_text.append(f'{key}: {{\n');
                # <2026-07-21 PM>s = self.destination_string(transfer_plugin);
                s = self.destination_string(self.output_plugin);
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
                TRACE.INFO(f'{self.label}: MAX EVENT SIZE BYTES line: {s}',TRACE_NAME)
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

        TRACE.DEBUG(1,f'-- END {self.label}',TRACE_NAME)
        return new_text;
