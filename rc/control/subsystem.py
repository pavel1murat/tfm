#------------------------------------------------------------------------------
# "Subsystem" is a structure containing all info about a given artdaq subsystem
# a subsystem has 
# - an ID, 
# - one or several input sources,
# - one output destination,
# - a mode in which it handles the artdaq fragments
#-----------------------------------------------------------------------------
from   tfm.rc.control.procinfo          import Procinfo, BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ;

class Subsystem(object):
    __index = 0;                            # subsystem number counter

    def __init__(self,ssid):
        self.id           = ssid            # ssid is a string
        self.index        = Subsystem.__index;        # 
        self.fragmentMode = None            #

        self.sources      = []              # list of strings (ss_id's) - get rid of that...
        self.destination  = None            # string
        
                                            # temporarily duplicate the above, prepare for a transition
                                            
        self.list_of_sS   = [];             # list of objects of Subsystem type
        self.dS           = None;           # if not None, object of Subsystem tyep
        
        self.list_of_procinfos = { }
        self.list_of_procinfos[BOARD_READER   ] = []
        self.list_of_procinfos[EVENT_BUILDER  ] = []
        self.list_of_procinfos[DATA_LOGGER    ] = []
        self.list_of_procinfos[DISPATCHER     ] = []
        self.list_of_procinfos[ROUTING_MANAGER] = []
        self.max_type     = -1;             # max type of the processes in this subsystem
        self.min_type     = 99;             # min type of the processes in this subsystem

        Subsystem.__index += 1;             # increment the subsystem counter, why is it needed ?
        
    def __lt__(self, other):
        if self.index != other.index:
                                            # both destination and id are strings (names)
            if self.destination == other.id:  
                # 'self' provides input for 'other', should go before in the ordered list
                return True
            else:
                return False
        else:
            return False  # equal

#------------------------------------------------------------------------------
    def print(self):
        print('-- START Subsystem::print')
        print ("-- subsystem ID:"  ,self.id,
               " index:"           ,self.index,
               " sources:"         ,self.sources,
               " destination:"     ,self.destination,
               "fragmentMode:"     ,self.fragmentMode);
        
        for k in self.list_of_procinfos:
            # print(f'------- k:{k}') 
            list_of_p = self.list_of_procinfos[k]   ## expect to be a list
            for p in list_of_p:
                print(f'-- k:{k} p.rank:{p.rank} p.label:{p.label} ')
        print('-- END Subsystem::print')

#------------------------------------------------------------------------------
    def list_of_board_readers(self):
        return self.list_of_procinfos[BOARD_READER];
    
    def list_of_data_loggers(self):
        return self.list_of_procinfos[DATA_LOGGER];
    
    def list_of_event_builders(self):
        return self.list_of_procinfos[EVENT_BUILDER];
    
    def list_of_event_processes(self, type):
        return self.list_of_procinfos[type];
    
#------------------------------------------------------------------------------
