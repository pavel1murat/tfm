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
import os, sys, re
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
                 timeout            = 30,         # PM: pick some reasonable default
                 label              = None,
                 subsystem          = "1",
                 allowed_processors = None,
                 target             = None,
                 prepend            = "",
                 fhicl              = None,
                 fhicl_file_path    = [],
                 ):
        self.name               = name
        self.rank               = rank
        self.port               = port
        self.host               = host
        self.label              = label
        self.subsystem          = subsystem
        self.allowed_processors = allowed_processors
        self.target             = target
        self.prepend            = prepend
        self.fhicl              = fhicl  # Name of the input FHiCL document
        self.ffp                = fhicl_file_path
        self.priority           = 999

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

        # FHiCL code actually sent to the process

        # JCF, 11/11/14 -- note that "fhicl_used" will be modified
        # during the initalization function, as bookkeeping, etc.,
        # is performed on FHiCL parameters

        if self.fhicl is not None:
            self.fhicl_used = ""
            self.recursive_include(self.fhicl)
        else:
            self.fhicl_used = None

        # JCF, Jan-14-2016

        # Do NOT change the "lastreturned" string below without
        # changing the commensurate string in check_proc_transition!

        self.lastreturned = "FarmManager: ARTDAQ PROCESS NOT YET CALLED"
        self.state        = "nonexistent"

#------------------------------------------------------------------------------
# returns host:port
#------------------------------------------------------------------------------
    def type(self):
        return self._type;
#------------------------------------------------------------------------------
# P.Murat: in the Edwards Center, the daq servers communicate using the private
#          data network, where mu2edaq09 has the name of mu2edaq09-ctrl
#------------------------------------------------------------------------------
    def rpc_server(self):
#        return self.host+'-data:'+self.port;
        return self.host+':'+self.port;

    def print(self):
        print("procinfo: name:%-20s"%self.name+" type:%i"%self._type+
              " label:%-20s"%self.label+' rpc_server:'+self.rpc_server());

#------------------------------------------------------------------------------
# place in expanded FHICL file, no more processing needed
#------------------------------------------------------------------------------
    def update_fhicl(self, fhicl):
#        self.fhicl      = fhicl
#        self.fhicl_used = ""
#        self.recursive_include(self.fhicl)
        res = subprocess.run(['fhicl-dump', filename],capture_output=True,text=True);
        self.fhicl      = filename;
        self.fhicl_used = res.stdout;

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

