#------------------------------------------------------------------------------
# "Subsystem" is a structure containing all info about a given artdaq subsystem
# a subsystem has 
# - an ID, 
# - one or several input sources,
# - one output destination,
# - a mode in which it handles the artdaq fragments
#-----------------------------------------------------------------------------
class Subsystem(object):
    def __init__(self,ss_id):
        self.id           = ss_id           # ss_id is a string
        self.sources      = []              # list of strings ? integers ?
        self.destination  = None            # string 
        self.fragmentMode = None            # 
        
    def __lt__(self, other):
        if self.id != other.id:
            
            if self.destination == other.id:  
                # 'self' provides input for 'other', should go before in the ordered list
                return True
            else:
                return False
        else:
            return False  # equal

    def print(self):
        print ("---- subsystem ID:",self.id,
               " sources:"    ,self.sources,
               " destination:",self.destination,
               "fragmentMode:",self.fragmentMode);
#------------------------------------------------------------------------------
