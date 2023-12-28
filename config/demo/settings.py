#!/usr/bin/python

def init(self):
    self.setup_script = "/home/mu2etrk/test_stand/pasha_019/setup_ots.sh";
    #-------------------------------------------------------------------------------------
    # debug level ranges from 0 to 4, in increasing order of verbosity
    #-------------------------------------------------------------------------------------
    self.debug_level = 1;
    
    #------------------------------------------------------------------------------------- 
    #           Board readers
    #-------------------------------------------------------------------------------------
    self.daq_comp_list["component01"] = ("localhost", -1, -1)
    self.daq_comp_list["component01"] = ("localhost", -1, -1)

    #------------------------------------------------------------------------------------- 
    #           Event builders"                                                             
    #-------------------------------------------------------------------------------------
    evb1 = self.Procinfo(name="EventBuilder1",host="localhost")
    evb2 = self.Procinfo(name="EventBuilder2",host="localhost")

    self.Procinfos.append(evb1);
    self.Procinfos.append(evb2);
     
    logger     = self.Procinfo(name="DataLogger1", host="localhost")
    dispatcher = self.Procinfo(name="Dispatcher1", host="localhost"}

    self.Procinfos.append(logger)
    self.Procinfos.append(dispatcher)
#------------------------------------------------------------------------------
# from settings file
#------------------------------------------------------------------------------
    self.log_directory                = '$MRB_TOP/tfm_test/Logs'
    self.record_directory             = '$MRB_TOP/tfm_test/run_records'
    self.package_hashes_to_save       = [ 'artdaq-demo', 'artdaq' ]
    self.productsdir_for_bash_scripts = '$MRB_TOP/remoteProducts_mu2e_v2_06_11_e28_s124_prof'

    self.boardreader_timeout          = 60
    self.eventbuilder_timeout         = 30
    self.datalogger_timeout           = 30
    self.dispatcher_timeout           = 30
    self.routing_manager_timeout      = 30
    self.aggregator_timeout           = 30
    








# 
#   "RoutingManager:1"  : {"label":"RoutingManager11", "host":"localhost", "subsystem":"4" },
# "#":"-------------------------------------------------------------------------------------",
# "#":"           Subsystems"                                                                ,
# "#":"-------------------------------------------------------------------------------------",
#  "Subsystem:1" : {"id":"1", "source":"-1"        , "destination":"2"},
#  "Subsystem:2" : {"id":"2", "source": "1"        , "destination":"3"},
#  "Subsystem:3" : {"id":"3", "source": "2"        , "destination":"4"},
#  "Subsystem:4" : {"id":"4", "source": ["3","5"] }                    ,
#  "Subsystem:5" : {"id":"5", "source":"-1"        , "destination":"4"},
# -------------------------------------------------------------------------------------",
# "#":"           the end"                                                                   ,
# "#":"-------------------------------------------------------------------------------------"
