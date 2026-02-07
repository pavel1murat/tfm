#!/bin/env/python

import os, sys, argparse, glob, inspect, re, subprocess

from   tfm.rc.control.procinfo          import Procinfo, BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ;

import TRACE ; TRACE_NAME='artdaq'
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
    
#------------------------------------------------------------------------------
# place in expanded FHICL file, no more processing needed
# also need to replace some lines which could be process specific
#------------------------------------------------------------------------------
def update_fhicl(procinfo, transfer_plugin, tmp_dir):
    # step 1 : read and replace - start from BRs
    print('------ update_fhicl')
    procinfo.print()
    TRACE.INFO(f'procinfo.label:{procinfo.label} procinfo.fhicl:{procinfo.fhicl}',TRACE_NAME)
    
    with open(procinfo.fhicl,'r') as f:
        lines = f.readlines()

    new_text = []
    if (procinfo.type() == BOARD_READER):
        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = destination_string(procinfo,transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue
                
            pattern = r'(?:[\w-]+\.)*max_fragment_size_bytes'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {procinfo.max_fragment_size_bytes}\n';
                new_text.append(s);
                continue;

            new_text.append(line)
                
    elif (procinfo.type() == EVENT_BUILDER):
        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*sources'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                # always replace the line with the real string
                # max_fragment_size_words is calculated
                s = source_string(procinfo,transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue

            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = destination_string(procinfo,transfer_plugin);
                new_text.append(s);
                new_text.append('}\n');
                continue;
                
            pattern = r'(?:[\w-]+\.)*host_map'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: [');
                offset = '    ' # 4 spaces (TCL indent)
                s      = host_map_string(procinfo.list_of_destinations,offset);
                new_text.append(s);
                new_text.append(' ]\n');
                continue;

            pattern = r'(?:[\w-]+\.)*max_event_size_bytes'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {procinfo.max_event_size_bytes}\n';
                new_text.append(s);
                continue;

            pattern = r'(?:[\w-]+\.)*init_fragment_count'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {procinfo.init_fragment_count}\n';
                new_text.append(s);
                continue;

            new_text.append(line);
            
    elif (procinfo.type() == DATA_LOGGER):
        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*sources'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = source_string(procinfo,transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue

            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = destination_string(procinfo,transfer_plugin);
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
                s = host_map_string(procinfo.list_of_destinations,offset);
                new_text.append(s);
                new_text.append(' ]\n');
                continue;
    
            pattern = r'(?:[\w-]+\.)*max_event_size_bytes'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {procinfo.max_event_size_bytes}\n';
                new_text.append(s);
                continue;

            pattern = r'(?:[\w-]+\.)*init_fragment_count'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {procinfo.init_fragment_count}\n';
                new_text.append(s);
                continue;

            #------------------------------------------------------------------------------
            # any other line - just rewrite
            #------------------------------------------------------------------------------
            new_text.append(line);

    elif (procinfo.type() == DISPATCHER):
        raise Exception('DISPATCHER: IMPLEMENT ME!')
    
    elif (procinfo.type() == ROUTING_MANAGER):
        raise Exception('ROUTING_MANAGER: IMPLEMENT ME!')
    
#---------------^--------------------------------------------------------------
#  write updated FCL
#-------v----------------------------------------------------------------------
    new_fn = f'{tmp_dir}/{procinfo.label}.fcl'
    with open(new_fn,'w') as f:
        f.writelines(line for line in new_text)
        
    # step 2 : flatten
    res = subprocess.run(['fhicl-dump', new_fn],capture_output=True,text=True);
    procinfo.fhicl      = new_fn;
    procinfo.fhicl_used = res.stdout;

    print('----------------------------- end of update_fhicl')
    print(procinfo.fhicl_used);
    return

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
            print(f'-- [BoardReader::init_connections] self.label:{self.label} s.destination:{s.destination}')
            if (s.destination != None):
                # subsystem has a destination, that has to have event builders
                print(f'subsystem:{s.id} destination is not NONE, but :"{s.destination}"')
                sd = s.dS;                  # destination subsystem, ## self.subsystems[s.destination];
                list_of_ebs = sd.list_of_procinfos[EVENT_BUILDER]
                print(f'-- [BoardReader::init_connections] sd.id:{sd.id} len(list_of_ebs):{len(list_of_ebs)}')
                
                for eb in list_of_ebs:
                    print(f'-- [init_br_connections] append {eb.label} to the destinations of {self.label}')
                    self.list_of_destinations.append(eb);
                    eb.list_of_sources.append(self);
            else:
                # the subsystem has only BRs', that is a problem
                raise Exception(f'ERROR: subsystem:{s.id} has only BRs and no destination. FIX IT.')
        return;


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
        
    def init_connections(self):      # p = self
        print(f'--------------------------- EventBuilder::init_connections:{self.label}')
        # EB has to have inputs - either from own BRs or from other subsystems or EBs from other subcyctems
        # start from checking inputs
        s = self.subsystem; ## self.subsystems[p.subsystem_id]; # subsystem which a given process belongs to
        # BRs should already be covered, check for input from other EBs

        print(f's.sources:{s.sources}');
        print(f'process.list_of_sources:{self.list_of_sources}');

        sum_fragment_size_bytes  = 0;               # sum of the BR's input
        max_event_size_bytes     = 0;               # max event from input EB's
        self.init_fragment_count = 0;

        if (len(s.sources) > 0):
            for ss in s.list_of_sS:
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
                        sum_fragment_size_bytes += br.max_fragment_size_bytes;
                        # avoid double counting
                        if (not br in self.list_of_sources):
                            self.list_of_sources.append(eb);
                            eb.list_of_destinations.append(self);

        else:
#-------^----------------------------------------------------------------------
# subsystem doesn't have inputs, look at local BRs - those are already in the list
# of inputs
#-----------v------------------------------------------------------------------
            for br in self.list_of_sources:
                print(f'br.label:{br.label} br.max_fragment_size_bytes:{br.max_fragment_size_bytes}')
                sum_fragment_size_bytes += br.max_fragment_size_bytes

                print(f'p.max_event_size_bytes:{self.max_event_size_bytes} self.max_fragment_size_bytes:{self.max_fragment_size_bytes}')


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
                # subsystem has a destination, that has to start with EB level
                if (sd.min_type < EVENT_BUILDER):
                    # a problem, subsystem has BRs at best - throw an exception
                    raise Exception('EB: trouble');
                else:
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

#-------^----------------------------------------------------------------------
# define processes for p.type = DATA_LOGGER
#------------------------------------------------------------------------------
    def init_connections(self):

        print(f'--- p.label:{self.label} p.subsystem_id:{self.subsystem_id}');
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
                        self.init_fragment_count += 1;
                        
                        if (eb.max_event_size_bytes > self.max_event_size_bytes):
                            self.max_event_size_bytes =  eb.max_event_size_bytes
    
                        # avoid double counting
                        if (not eb in self.list_of_sources):
                            self.list_of_sources.append(eb);
                            eb.list_of_destinations.append(self);
#-------------------------------^----------------------------------------------
# no source subsystems or those start from DLs - look for local inputs
#-------v----------------------------------------------------------------------
        else:
            # subsystem has no official sources, there should be local EB's
            list_of_ebs = s.list_of_event_builders()
            if (len(list_of_ebs) > 0):
                for eb in list_of_ebs:
                    self.init_fragment_count += 1;
                    if (eb.max_event_size_bytes > self.max_event_size_bytes):
                        self.max_event_size_bytes =  eb.max_event_size_bytes
                        
                    if (not eb in self.list_of_sources):
                        self.list_of_sources.append(eb);
                        eb.list_of_destinations.append(self);
                    
            else:
                # subsystem has no own EB's : trouble
                raise Exception('DL: no EBs in the subsystem');

#------------------------------------------------------------------------------
# now - destinations ... not done yet
#------------------------------------------------------------------------------

        TRACE.ERROR(f'DL {self.label} no destinations defined - FIXME',TRACE_NAME)
        return;

#------------------------------------------------------------------------------
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

#------------------------------------------------------------------------------
# define processes for p.type = ROUTINE_MANAGER
#------------------------------------------------------------------------------
    def rm_connections(self):
        raise Exception('RoutingManager::init_connection: not implemented yet');
#------------------------------------------------------------------------------
