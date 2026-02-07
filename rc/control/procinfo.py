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

class Procinfo(object):

    def __init__(self,
                 name,
                 rank,
                 host,
                 port,                            # assumed to be a string
                 timeout,         # PM: pick some reasonable default
                 label,
                 subsystem_id,
                 allowed_processors = None,
                 target             = None,
                 fhicl              = None,
                 prepend            = "",
                 fhicl_file_path    = [],
                 ):
        self.name               = name
        self.rank               = rank
        self.port               = port
        self.host               = host
        self.label              = label
        self.subsystem_id       = subsystem_id
        self.subsystem          = None;               # not defined at this point
        self.allowed_processors = allowed_processors
        self.target             = target
        self.prepend            = prepend
        self.fhicl              = fhicl  # Name of the input FHiCL document
        self.ffp                = fhicl_file_path
        self.priority           = 999
        self.list_of_sources      = [ ]
        self.list_of_destinations = [ ]
        self.max_fragment_size_bytes = None;
        self.max_event_size_bytes    = None;         ## for EBs ... DLs ?? etc
        self.init_fragment_count     = None;         ## for DLs, DSs
        self.odb_path                = None;

        if   (name == "BoardReader"   ) : self._type = BOARD_READER   ;
        elif (name == "EventBuilder"  ) : self._type = EVENT_BUILDER  ;
        elif (name == "DataLogger"    ) : self._type = DATA_LOGGER    ;
        elif (name == "Dispatcher"    ) : self._type = DISPATCHER     ;
        elif (name == "RoutingManager") : self._type = ROUTING_MANAGER;

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
    def type(self):
        return self._type;

    def is_boardreader(self):
        return self._type == BOARD_READER;

    def is_datalogger(self):
        return self._type == DATA_LOGGER;

    def is_dispatcher(self):
        return self._type == DISPATCHER;

    def is_eventbuilder(self):
        return self._type == EVENT_BUILDER;

    def is_routingmanager(self):
        return self._type == ROUTING_MANAGER;

#------------------------------------------------------------------------------
# P.Murat: in the Edwards Center, the daq servers communicate using the private
#          data network, where mu2edaq09 has the name of mu2edaq09-ctrl
#------------------------------------------------------------------------------
    def rpc_server(self):
#        return self.host+'-data:'+self.port;
        return self.host+':'+self.port;

    def print(self,text = None):
        if (text):
            print(f'{text}');
            
        print(f'procinfo: subsystem_id:{self.subsystem_id:5} type:{self._type} label:{self.label:6} rpc_server:{self.rpc_server()} name:{self.name:12} fcl:{self.fhicl}');

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

    def recursive_include(self, filename):

        if self.fhicl is not None:
            for line in open(filename).readlines():
                
                if "#include" not in line:
                    self.fhicl_used += line
                else:
                    res = re.search(r"^\s*#.*#include", line)

                    if res:
                        self.fhicl_used += line
                        continue

                    res = re.search(r"^\s*#include\s+\"(\S+)\"", line)

                    if not res:
                        raise Exception(
                            make_paragraph(
                                "Error in Procinfo::recursive_include: "
                                'unable to parse line "%s" in %s' % (line, filename)
                            )
                        )

                    included_file = res.group(1)

                    if included_file[0] == "/":
                        if not os.path.exists(included_file):
                            raise Exception(
                                make_paragraph(
                                    "Error in "
                                    "Procinfo::recursive_include: "
                                    "unable to find file %s included in %s"
                                    % (included_file, filename)
                                )
                            )
                        else:
                            self.recursive_include(included_file)
                    else:
                        found_file = False

                        for dirname in self.ffp:
                            if (
                                os.path.exists(dirname + "/" + included_file)
                                and not found_file
                            ):
                                self.recursive_include(
                                    dirname + "/" + included_file
                                )
                                found_file = True

                        if not found_file:

                            ffp_string = ":".join(self.ffp)

                            raise Exception(
                                make_paragraph(
                                    "Error in Procinfo::recursive_include: "
                                    "unable to find file %s in list of "
                                    "the following fhicl_file_paths: %s"
                                    % (included_file, ffp_string)
                                )
                            )
        return
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

