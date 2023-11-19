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

class Procinfo(object):
    def __init__(
        self,
        name,
        rank,
        host,
        port,
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
        self.socketstring = "http://" + self.host + ":" + self.port + "/RPC2"
        self.state        = "nonexistent"

    def print(self):
        print("procinfo: name:%-20s"%self.name+" label:%-20s"%self.label+" port:"+self.port);

    def update_fhicl(self, fhicl):
        self.fhicl      = fhicl
        self.fhicl_used = ""
        self.recursive_include(self.fhicl)

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
