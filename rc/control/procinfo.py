#------------------------------------------------------------------------------
# "Procinfo" is a simple structure containing the info about a given artdaq process 
#
# However, it also contains a less-than function which allows it
# to be sorted s.t. processes you'd want shutdown first appear
# before processes you'd want shutdown last (in order:
# boardreader, eventbuilder, datalogger, dispatcher, routingmanager)
#
# JCF, Nov-17-2015
#
# I add the "fhicl_file_path" variable, which is a sequence of
# paths which are searched in order to cut-and-paste #include'd files 
# (see also the description of the FarmManager class's
# fhicl_file_path variable, whose sole purpose is to be passed to Procinfo's functions)
#
# JCF, Apr-26-2018
#
# The "label" variable is used to pick out specific FHiCL files
# for EventBuilders, DataLoggers, Dispatchers and RoutingManagers;
# a given process's label is set in the boot file, alongside its
# host and port
#------------------------------------------------------------------------------
import os, sys, re, subprocess
import tfm.rc.control.utilities as     rcu
from   tfm.rc.io.timeoutclient  import TimeoutServerProxy

import    TRACE
TRACE_NAME="procinfo"

BOARD_READER    = 1;
EVENT_BUILDER   = 2;
DATA_LOGGER     = 3;
DISPATCHER      = 4;
ROUTING_MANAGER = 5;

PROCESS_TYPES = [ BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ]

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
class Procinfo(object):

    def __init__(self,
                 name,
                 rank,
                 host,
                 port,                            # assumed to be a string
                 timeout,                         # PM: pick some reasonable default
                 label,
                 subsystem_id,
                 allowed_processors = None,
                 target             = None,
                 fhicl              = None,
                 prepend            = "",
                 fhicl_file_path    = [],
                 ):
        self._process_type           = None;             # to make it detectable
        self.name                    = name
        self.rank                    = rank
        self.port                    = port                   # isn't port obsolete and defined unambiguously by rank ?
        self.host                    = host
        self.label                   = label
        self.subsystem_id            = subsystem_id
        self.subsystem               = None;               # not defined at this point
        self.allowed_processors      = allowed_processors
        self.target                  = target
        self.prepend                 = prepend
        self.fcl_template            = None
        self.fhicl                   = fhicl               # Name of the input FHiCL document
        self.ffp                     = fhicl_file_path
        self.priority                = 999
        self.list_of_sources         = [ ]
        self.list_of_destinations    = [ ]
        self.list_of_fragment_ids    = [ ]
        self.max_fragment_size_bytes = 0;
        self.max_event_size_bytes    = 0;         ## for EBs ... DLs ?? etc
        self.init_fragment_count     = 0;            ## for DLs, DSs
        self.odb_path                = None;
        self.execname                = None;
        self.log_directory           = None;
        self.input_plugin            = None;    ## BRs don't have it defined...
        self.output_plugin           = None;

        self.server = None
        xmlrpc_url  = "http://" + self.rpc_server() + "/RPC2"
        try:
            self.server = TimeoutServerProxy(xmlrpc_url, timeout)
        except Exception:
            TRACE.TRACE(3,f'failed to create an XMLRPC server for process:{label} and socket:{xmlrpc_url}',TRACE_NAME);
        # Do NOT change the "lastreturned" string below without
        # changing the commensurate string in check_proc_transition!

        self.lastreturned = "FarmManager: ARTDAQ PROCESS NOT YET CALLED"
        self.state        = "nonexistent"

#------------------------------------------------------------------------------
# assume 8-byte data words, need max_fragment_size_bytes to be defined
#------------------------------------------------------------------------------
    def max_event_size_words(self):
        if (self.max_event_size_bytes == None):
            raise Exception(self.print())
        
        x = int(self.max_event_size_bytes/8);
        return x;
#------------------------------------------------------------------------------
# to be overloaded
#------------------------------------------------------------------------------
    def init_connections(self):
        pass
#------------------------------------------------------------------------------
# returns host:port
#------------------------------------------------------------------------------
    def process_type(self):
        return self._process_type;

    def is_boardreader(self):
        return self._process_type == BOARD_READER;

    def is_datalogger(self):
        return self._process_type == DATA_LOGGER;

    def is_dispatcher(self):
        return self._process_type == DISPATCHER;

    def is_eventbuilder(self):
        return self._process_type == EVENT_BUILDER;

    def is_routingmanager(self):
        return self._process_type == ROUTING_MANAGER;

    def logfile(self,run_number):
        fn = f'{self.log_directory}/{self.label}_{self.node}_{self.port}/{self.label}_{self.node}_{self.port}_{run_number}.log'

    def n_fragment_ids(self):
        return len(self.list_of_fragment_ids)

#------------------------------------------------------------------------------
# P.Murat: in the Edwards Center, the daq servers communicate using the private
#          data network, where mu2edaq09 has the name of mu2edaq09-ctrl
#------------------------------------------------------------------------------
    def rpc_server(self):
        return self.host+':'+self.port;

#------------------------------------------------------------------------------
# prints process parameters to STDOUT
#------------------------------------------------------------------------------
    def print_parameters(self):
        # TRACE.WARN(f'label: {self.label} : TO BE OVERWRITTEN',TRACE_NAME)
        print(f'label                  : {self.label}')
        print(f'process_type           : {self._process_type}')
        print(f'host                   : {self.host}' )
        print(f'rank                   : {self.rank}' )
        print(f'fcl_template           : {self.fcl_template}')
        print(f'list_of_sources        :')
        if (len(self.list_of_sources) > 0):
            for p in self.list_of_sources:
                print(f'                         p.label:{p.label}')

        print(f'list_of_destinations   :')
        if (len(self.list_of_destinations) > 0):
            for p in self.list_of_destinations:
                print(f'                         p.label:{p.label}')
                
        print(f'max_event_size_bytes   : {self.max_event_size_bytes}' )
        print(f'max_fragment_size_bytes: {self.max_fragment_size_bytes}')
        return
    
#------------------------------------------------------------------------------
    def print(self,text = None):
        if (text): print(f'{text}');

        s = f'procinfo: ss_id:{self.subsystem_id:5} type:{self._process_type} label:{self.label:4} rpc_server:{self.rpc_server()} name:{self.name:12} fcl:{self.fhicl}'
        
        TRACE.DEBUG(1,s,TRACE_NAME);

    def __lt__(self, other):
        if self.name != other.name:

            processes_upstream_to_downstream = [
                "BoardReader",
                "EventBuilder",
                "DataLogger",
                "Dispatcher",
                "RoutingManager",
            ]

            if processes_upstream_to_downstream.index(
                self.name
            ) < processes_upstream_to_downstream.index(other.name):
                return True
            else:
                return False
        else:
            if int(self.port) < int(other.port):
                return True
            return False

#-------^----------------------------------------------------------------------
#
#---v--------------------------------------------------------------------------
    def get_related_pids(self):
        related_pids = []
        netstat_cmd = "netstat -alpn | grep %s" % (self.port)
    
        if not rcu.host_is_local(self.host):
            netstat_cmd = "ssh -x %s '%s'" % (self.host, netstat_cmd)
    
        proc = subprocess.Popen(netstat_cmd,executable="/bin/bash",shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
        )
    
        for line in proc.stdout.readlines():
            procstring = line.decode("utf-8")
            res = re.search(r"([0-9]+)/(.*)", procstring.split()[-1])
            if res:
                pid = res.group(1)
                pname = res.group(2)
                if "python" not in pname:  # Don't want DAQInterface to kill itself off...
                    related_pids.append(res.group(1))

        return set(related_pids)
#-------^----------------------------------------------------------------------
# 'p' is a Processinfo
#------------------------------------------------------------------------------
    def destination_string(self,transfer_plugin):
        s = ''
        for d in self.list_of_destinations:
            s += f' d{d.rank}: {{'
            s += f' transferPluginType: {transfer_plugin}'
            s += f' destination_rank:  {d.rank}'
            # for BR, event=fragment
            s += f' max_fragment_size_words: {self.max_event_size_words()}'
            
            # first destination includes the host_map
            if (d == self.list_of_destinations[0]):
                offset = '        '
                s += ' host_map: ['
                s += host_map_string(self.list_of_destinations,offset);
                s += ' ]'
                
            s +=  '}\n'
    
        return s;

#-------^----------------------------------------------------------------------
# 'p' is a Processinfo
#------------------------------------------------------------------------------
    def source_string(self,transfer_plugin):
        s  = ''
    
        for x in self.list_of_sources:
            s += f' s{x.rank}: {{'
            s += f' transferPluginType: {transfer_plugin}'
            s += f' source_rank:  {x.rank}'
            s += f' max_fragment_size_words: {x.max_event_size_words()}'
            
            # first destination includes the host_map
            if (x == self.list_of_sources[0]):
                s += ' host_map: ['
                offset = ''
                s += host_map_string(self.list_of_sources,offset);
                s += ' ]'
                
            s +=  '}\n'
    
        return s;
    
#---^--------------------------------------------------------------------------
# marking the end
#------------------------------------------------------------------------------
