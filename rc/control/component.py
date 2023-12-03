import argparse
import datetime
import os.path
import os
import random
from contextlib       import contextmanager
from rc.io.rpc        import rpc_server
from rc.threading     import threadable
from rc.util.contexts import ContextObject

import run_control_state

#------------------------------------------------------------------------------
class Component(ContextObject):
    """
    Dummy (or subclass-able) component for use with the LBNE Run Control prototype.
    """

    __MAXPORT = 65535

    def __init__(self,
                 name         = "toycomponent",
                 rpc_host     = "localhost",
                 control_host = "localhost",
                 synchronous  = False,
                 rpc_port     = 6659,
                 skip_init    = False):

        if rpc_port > Component.__MAXPORT:
            raise ValueError("Maximum allowed port is %s" % Component.__MAXPORT)

        if name == "daq":
            raise ValueError("Name 'daq' is not allowed for individual components")

        self.name        = name
        self.synchronous = synchronous
        self.__state     = "stopped"
        self.__rpc_host  = rpc_host
        self.__rpc_port  = rpc_port
        self.run_params  = None
        self.__dummy_val = 0
#------------------------------------------------------------------------------
# initialize the RPC server and commands it can execute
# two contexts corresponding to two threads
#------------------------------------------------------------------------------
        self.contexts = [
            ("rpc_server", rpc_server(port  = self.__rpc_port,
                                      funcs = { "state"              : self.state,
                                                "shutdown"           : self.complete_shutdown,
                                                "get_state"          : self.get_state,
                                                "artdaq_process_info": self.artdaq_process_info,
                                                "state_change"       : self.state_change,
                                                "listconfigs"        : self.listconfigs,
                                                "trace_get"          : self.trace_get,
                                                "trace_set"          : self.trace_set,
                                            })),
            ("runner"    , threadable(func=self.runner))
        ]
#------------------------------------------------------------------------------
# transition "booting" leads to the "booted' state
# states we need: 
# 1. "booted" or "idle" : the state the system gets upon startup
# 2. "configured"       : all processes are started, run number known, ready to start running
#                         needed, as different hardware susbsystems take different time to get ready 
#                         for running, so configuration is performed in parallel
# 3. "running"          : taking data
# thus, the needed transitions are :
# 1. "configure"        : "idle" --> "configured"
# 2. "start"            : "configured" --> "running"
# 3. "stop"             : "running" --> "idle"
# 4. "recover"          : from anywhere trouble to "idle"
#
# but do the cleanup step by step
#-------
        self.fState = None;
        
        self.transition = { 
            "boot"        : {"state": "booting"    , "from": "stopped", "to": "booted" },
            "configure"   : {"state": "configuring", "from": "booted" , "to": "ready"  },
            "start"       : {"state": "starting"   , "from": "ready"  , "to": "running"},
            "stop"        : {"state": "stopping"   , "from": "running", "to": "booted" },
            "pause"       : {"state": "pausing"    , "from": "running", "to": "paused" },
            "resume"      : {"state": "resuming"   , "from": "paused" , "to": "running"},
            "recover"     : {"state": "recovering" , "from": ""       , "to": "booted" },
        }
        
        self.dict_state_to = {
            "booting"    : "booted",
            "shutting"   : "booted",
            "stopping"   : "booted",
            "configuring": "ready",
            "starting"   : "running",
            "pausing"    : "paused",
            "resuming"   : "running",
            "terminating": "stopped",
            "recovering" : "stopped",
        }

#------------------------------------------------------------------------------
# transition "booting" allowed only from "stopped" state
#------------------------------------------------------------------------------
        self.dict_state_from = {
            "booting"    : "stopped",
            "shutting"   : "booted",
            "stopping"   : "running",
            "configuring": "booted",
            "starting"   : "ready",
            "pausing"    : "running",
            "resuming"   : "paused",
            "terminating": "ready|booted",
        }
#------------------------------------------------------------------------------
# this is just nuts! 
#------------------------------------------------------------------------------
        self.dict_correct_grammar = {
            "booting"    : "boot",
            "shutting"   : "shutdown",
            "stopping"   : "stop",
            "configuring": "config",
            "starting"   : "start",
            "pausing"    : "pause",
            "resuming"   : "resume",
            "terminating": "terminate",
        }

    def state(self, name):
        # if name != self.name: return "unknown"
        return self.__state

    def get_state(self,name):
        return self.fState.get_name()+':%s'%self.fState.get_completed()

    def artdaq_process_info(self, name):
        raise NotImplementedError()

    def complete_state_change(self, requested):
        newstate     = self.dict_state_to.get(requested, requested)
        self.__state = newstate

    # JCF, Dec-15-2016

    # revert_state_change should be called when a nonfatal error
    # occurs during a transition and DAQInterface should go back to
    # its original state before the transition request. Note that
    # unlike "complete_state_change", there's no provision for the
    # recover transition, as this can occur at any point in the state
    # machine

    def revert_state_change(self, name, requested):
        # if name != self.name: return
        oldstate = self.dict_state_from.get(requested, requested)
        # trep     = datetime.datetime.utcnow()
        self.__state = oldstate

    def listconfigs(self):
        assert False, "This version of the function should not be called"

    # JCF, Jun-29-2018

    # While print_log here seemingly does nothing, this can be
    # overridden in derived classes s.t.  messages not just in derived
    # classes but here in Component can be decorated with, e.g., a
    # severity level

    def print_log(self, severity, printstr, debuglevel=-999):
        print(printstr)

    def trace_get(self, name, trace_args):
        if name != self.name: return
        self.run_params           = trace_args
        self.do_trace_get_boolean = True

    def trace_set(self, name, trace_args):
        if name != self.name: return
        self.run_params           = trace_args
        self.do_trace_set_boolean = True

#------------------------------------------------------------------------------
# should be able to shut down correctly from any state, not only from 'stopped'
# to begin with, assume that we're in a 'stopped' state
#---v--------------------------------------------------------------------------
    def complete_shutdown(self,name):
        print(" >>> complete_shutdown Requested");
        self.shutdown()
        return;

#------------------------------------------------------------------------------
# request to change state comes from the outside
#---v--------------------------------------------------------------------------
    def state_change(self, name, requested, state_args):

        if (requested in self.dict_state_from.keys() and (self.__state not in self.dict_state_from[requested])):
            self.print_log("w","\nWARNING: Unable to accept transition request "
                           '"%s" from current state "%s"; the command will have no effect.'
                           % (self.dict_correct_grammar[requested], self.__state))

            allowed_transitions = []

            for key, val in self.dict_state_from.items():
                if self.__state in val:
                    allowed_transitions.append(key)

            assert len(allowed_transitions) > 0, "Zero allowed transitions"

            self.print_log("w","Can accept the following transition request(s): "
                           + ", ".join(
                               [
                                self.dict_correct_grammar[transition]
                                   for transition in allowed_transitions
                               ]
                           ),
                       )
            return
        # breakpoint()
        # set out transition state now.

        self.__state = requested

        if requested == "starting":
            self.run_params = state_args
            self.start_running()
        if requested == "stopping":
#------------------------------------------------------------------------------
# stopping involves sending shutdown signal if any to the processes, no separate 
# shutdown transition
#------------------------------------------------------------------------------
            self.stop_running()
#            self.shutdown()
        if requested == "pausing":
            self.pause_running()
        if requested == "booting":
            self.run_params = state_args
            self.boot()
        if requested == "configuring":
            self.run_params = state_args
            self.config()
        if requested == "resuming":
            self.resume_running()
        if requested == "terminating":
            self.terminate()
        if requested == "recovering":
            self.recover()

    def wakeup(self):
        self.runner.wakeup()

    def runner(self):
        """
        Component "ops" loop.  Called at threading hearbeat frequency,
        currently 1/sec.

        Overide this, and use it to check statuses, send periodic report,
        etc.

        """
        if self.__state == "running":
            self.__dummy_val += random.random() * 100 - 50

    def boot(self):
        self.complete_state_change("booting")

    def shutdown(self):
        self.complete_state_change("shutting")

    def config(self):
        self.complete_state_change("configuring")

    def start_running(self):
        """
        Override this to explicitly do something during "starting" transitional
        state (changing from "ready" to "running" states)

        Be sure to report when your transition is complete.
        """
        self.complete_state_change("starting")

    def stop_running(self):
        """
        Override this to explicitly do something during "stopping" transitional
        state (changing from "running" to "ready" states)

        Be sure to report when your transition is complete.
        """
        self.complete_state_change("stopping")

    def pause_running(self):
        """
        Override this to explicitly do something during "pausing" transitional
        state (changing from "running" to "paused" states)

        Be sure to report when your transition is complete.
        """
        self.complete_state_change("pausing")

    def resume_running(self):
        """
        Override this to explicitly do something during "resuming" transitional
        state (changing from "paused" to "running" states)

        Be sure to report when your transition is complete.
        """
        self.complete_state_change("resuming")

    def terminate(self):
        """
        Override this to explicitly do something during "terminating"
        transitional state (changing from "ready" to "stopped" states)

        Be sure to report when your transition is complete.
        """
        self.complete_state_change("terminating")

    def recover(self):
        """
        Override this to explicitly do something during
        "recovering" transitional state

        Perform resets, clean up file handles, etc.  Go back to
        a "clean stop" in the "stopped" state.

        Be sure to report when your transition is complete.
        """
        self.complete_state_change("recovering")


def get_args():  # no-coverage
    parser = argparse.ArgumentParser(description="Simulated LBNE 35 ton component")

    parser.add_argument("-n", "--name"          , type=str, dest="name"    , default="toy"      , help="Component name")
    parser.add_argument("-r", "--rpc-port"      , type=int, dest="rpc_port", default=6660       , help="RPC port"      )
    parser.add_argument("-H", "--rpc-host"      , type=str, dest="rpc_host", default="localhost", help="This hostname/IP addr")
    parser.add_argument("-c", "--control-host"  , type=str, dest="control_host", default="localhost", help="Control host" )
    parser.add_argument("-s", "--is-synchronous", action ="store_true", dest ="synchronous", default=False, 
                        help ="Component is synchronous (starts/stops w/ DAQ)")

    return parser.parse_args()
