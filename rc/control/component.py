#------------------------------------------------------------------------------
#
#------------------------------------------------------------------------------
import argparse, datetime, os.path, os, random, threading

from   contextlib    import contextmanager
from   xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler

#------------------------------------------------------------------------------
# homebrew
#------------------------------------------------------------------------------
from   tfm.rc.io.rpc                    import rpc_server
from   tfm.rc.threading                 import threadable
from   tfm.rc.util.contexts             import ContextObject

import tfm.rc.control.run_control_state as run_control_state
import TRACE
TRACE_NAME="component.py"

import midas.client;
#------------------------------------------------------------------------------
# use simplistic implementation of the XMLRPC server thread
# Restrict to RPC2
#------------------------------------------------------------------------------
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)
    
class ServerThread(threading.Thread):
    def __init__(self,host='localhost',port=6000,funcs = {}):
        threading.Thread.__init__(self)
        self.server = SimpleXMLRPCServer((host,port),requestHandler=RequestHandler)
        TRACE.TRACE(7,"start server",TRACE_NAME)

        # self.localServer.register_function(getTextA) #just return a string
        self.server.register_introspection_functions()      
        for name, func in funcs.items():
            self.server.register_function(func, name)

    def serve_forever(self):
        self.quit = 0
        while not self.quit:
            self.handle_request()
            
        TRACE.TRACE(7,"quitting",TRACE_NAME)
        return

    def kill(self):
        self.server.quit = 1

        TRACE.TRACE(7,"killing server",TRACE_NAME)
        return 1

    def run(self):
         self.server.serve_forever()
#------------------------------------------------------------------------------
# P.M. why we're inheriting from something with LBNE in the name ?
#------------------------------------------------------------------------------
class Component(ContextObject):
    """
    Dummy (or subclass-able) component for use with the LBNE Run Control prototype.
    """

    __MAXPORT = 65535

    def __init__(self,
                 name         = "toycomponent",
                 odb_client   = None,
                 rpc_host     = "localhost",
                 control_host = "localhost",
                 synchronous  = False,
                 skip_init    = False):

        if name == "daq":
            raise ValueError("Name 'daq' is not allowed for individual components")

        self.name        = name
        self.synchronous = synchronous
        self.__state     = "stopped"
        self.fClient     = odb_client;
        self.__rpc_host  = self.fClient.odb_get("/Mu2e/ActiveRunConfiguration/DAQ/Tfm/RpcHost");
        self.run_params  = None
        self.__dummy_val = 0
        self.__partition = self.fClient.odb_get('/Mu2e/ActiveRunConfiguration/DAQ/PartitionID');
        self.__rpc_port  = 10000+1000*self.__partition;
        self.__messages  = [];

        TRACE.TRACE(7,f"rpc_host={self.__rpc_host} rpc_port={self.__rpc_port}",TRACE_NAME)
#------------------------------------------------------------------------------
# initialize the RPC server and commands it can execute
# two contexts correspond to two threads
# better get rid of contexts - smth is fishy with the thread implementation
# stick to server
#------------------------------------------------------------------------------
        self.contexts = [("runner",threadable(func=self.runner))]

        self._server = ServerThread(host  = self.__rpc_host,
                                    port  = self.__rpc_port,
                                    funcs = { "alarm"              : self.alarm,
                                              "state"              : self.state,
                                              "shutdown"           : self.complete_shutdown,
                                              "get_state"          : self.get_state,
                                              "artdaq_process_info": self.artdaq_process_info,
                                              "state_change"       : self.state_change,
                                              "listconfigs"        : self.listconfigs,
                                              "trace_get"          : self.trace_get,
                                              "trace_set"          : self.trace_set,
                                              "message"            : self.message,
                                              "get_messages"       : self.get_messages                                     
                                             })
        self._server.setDaemon(True);
        self._server.start() # server is now running

        TRACE.TRACE(7,f"XMLRPC server should be running !",TRACE_NAME)
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
#-------v----------------------------------------------------------------------
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
        return

    def __del__(self):
        self._server.kill()

    def rpc_port(self):
        return self.__rpc_port

    def partition(self):
        return self.__partition

    def state(self):
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
# react to alarm messages sent by the ARTDAQ processes - first of all , the boardreaders
#---v--------------------------------------------------------------------------
    def alarm(self,message):
        print(" >>> ALARM");
        return
#------------------------------------------------------------------------------
# should be able to shut down correctly from any state, not only from 'stopped'
# to begin with, assume that we're in a 'stopped' state
#---v--------------------------------------------------------------------------
    def complete_shutdown(self,name):
        print(" >>> complete_shutdown Requested");
        self.shutdown()
        return "farm_manager: performing complete shutdown";

    def message(self, msg_type, message):
        self.print_log("i","rpc message type:%s message:'%s'" % (msg_type, message));
        self.__messages.append([msg_type, message])
        return "return"

    def get_messages(self, dummy):
        out_str = "\n".join([f"{item[0]}:{item[1]}" for item in self.__messages])
        self.__messages = []
        return out_str

#------------------------------------------------------------------------------
# request to change state comes from the outside
#---v--------------------------------------------------------------------------
    def state_change(self, name, requested, state_args):
        #breakpoint()

        self.print_log("d","component::state_change name=%s requested:%s state_args:%s" % (name,requested,state_args),2);

        if (requested in self.dict_state_from.keys() and (self.__state not in self.dict_state_from[requested])):
            self.print_log("w","\nWARNING: Unable to accept transition request "
                           '"%s" from current state "%s";\n'
                           'the command will have no effect.'
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
        if requested == "pausing":
            self.pause_running()
        if requested == "booting":
            self.run_params = state_args
            self.boot()
        if requested == "configuring":
            self.run_params = state_args
            self.config()
        if requested == "recovering":
            self.recover()
        if requested == "resuming":
            self.resume_running()
        if requested == "shutdown":
            self.complete_shutdown(name)
        if requested == "terminating":
            self.terminate()
        return "ok"
#-------^----------------------------------------------------------------------
#
#---v--------------------------------------------------------------------------
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


#def get_args():  # no-coverage
#    parser = argparse.ArgumentParser(description="Simulated LBNE 35 ton component")
#
#    parser.add_argument("-n", "--name"          , type=str, dest="name"    , default="toy"      , help="Component name")
#    parser.add_argument("-r", "--rpc-port"      , type=int, dest="rpc_port", default=6660       , help="RPC port"      )
#    parser.add_argument("-H", "--rpc-host"      , type=str, dest="rpc_host", default="localhost", help="This hostname/IP addr")
#    parser.add_argument("-c", "--control-host"  , type=str, dest="control_host", default="localhost", help="Control host" )
#    parser.add_argument("-s", "--is-synchronous", action ="store_true", dest ="synchronous", default=False, 
#                        help ="Component is synchronous (starts/stops w/ DAQ)")
#
#    return parser.parse_args()

