#------------------------------------------------------------------------------
# "Subsystem" is a structure containing all info about a given artdaq subsystem
# a subsystem has 
# - an ID, 
# - one or several input sources,
# - one output destination,
# - a mode in which it handles the artdaq fragments
#-----------------------------------------------------------------------------
class Subsystem(object):
    __index = 0;                            # subsystem number counter

    def __init__(self,ss_id):
        self.id           = ss_id           # ss_id is a string
        self.index        = Subsystem.__index;        # 
        self.sources      = []              # list of strings ? integers ?
        self.destination  = None            # string 
        self.fragmentMode = None            #

        Subsystem.__index += 1;                       # increment the counter
        
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

    def print(self):
        print ("---- subsystem ID:",self.id,
               " index:"           ,self.index,
               " sources:"         ,self.sources,
               " destination:"     ,self.destination,
               "fragmentMode:"     ,self.fragmentMode);
#------------------------------------------------------------------------------
