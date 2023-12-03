#------------------------------------------------------------------------------
# transition, from_state and to_state : stable RC states
# a system can be in a stable state or in transition
# a transition can be completed by 'completed' percent
#------------------------------------------------------------------------------
class RunControlState:

#------------------------------------------------------------------------------
# stable states are always completed by 100%
#------------------------------------------------------------------------------
    def __init__(self,name,stable=1,frm=None,to=None):
        self.name      = name;
        self.stable    = stable;
        self.frm       = frm;
        self.to        = to;

        if (stable == 1): self.completed = 100
        else            : self.completed = 0

    def get_name(self):
        return self.name;

    def get_completed(self):
        return self.completed;

#------------------------------------------------------------------------------
    def set_completed(self,percentage):
        self.completed = percentage

State = {};
State[""          ] = RunControlState(""           ,1)   # any state
State["stopped"   ] = RunControlState("stopped"    ,1)
State["configured"] = RunControlState("configured" ,1)
State["running"   ] = RunControlState("running"    ,1)
State["paused"    ] = RunControlState("paused"     ,1)
State["failed"    ] = RunControlState("failed"     ,1)

#------------------------------------------------------------------------------
# transitions have finite allocated time, stable states can last forever
#------------------------------------------------------------------------------
Transition  = {};
Transition ["init"     ] = RunControlState("init"     ,0,None                ,State["stopped"   ])
Transition ["configure"] = RunControlState("configure",0,State["stopped"    ],State["configured"])
Transition ["start"    ] = RunControlState("start"    ,0,State["configured" ],State["running"   ])
Transition ["pause"    ] = RunControlState("pause"    ,0,State["running"    ],State["paused"    ])
Transition ["resume"   ] = RunControlState("resume"   ,0,State["paused"     ],State["running"   ])
Transition ["recover"  ] = RunControlState("recover"  ,0,State["failed"     ],State["stopped"   ])
Transition ["stop"     ] = RunControlState("stop"     ,0,State["running"    ],State["stopped"   ])
Transition ["shutdown" ] = RunControlState("shutdown" ,0,State[""           ],None               )

#------------------------------------------------------------------------------
def state(name):
    if name in State.keys():
        return State[name]
    else:
        return None;

#------------------------------------------------------------------------------
def transition(name):
    if name in Transition.keys():
        return Transition[name]
    else:
        return None;
