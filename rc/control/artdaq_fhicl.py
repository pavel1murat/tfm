#!/bin/env/python

import os, sys, argparse, glob, inspect, re, subprocess

from   tfm.rc.control.procinfo          import Procinfo, BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ;

#------------------------------------------------------------------------------
def host_map_string(self,offset):
    s = ''
    for p in self.procinfos:
        s += f' {{ rank:{p.rank:3} host: "{p.host}"}}';
        if (p != self.procinfos[-1]):
            s += ','

    return s;

#------------------------------------------------------------------------------
# 'p' is a Processinfo
#------------------------------------------------------------------------------
def destination_string(self,p):
    s = ''
    for d in p.list_of_destinations:
        s += f' d{d.rank}: {{'
        s += f' transferPluginType: {self.transfer}'
        s += f' destination_rank:  {d.rank}'
        s += f' max_fragment_size_words: {p.max_fragment_size_words()}'
        
        # first destination includes the host_map
        if (d == p.list_of_destinations[0]):
            offset = '        '
            s += ' host_map: ['
            s += self.host_map_string(offset);
            s += ']'
            
        s +=  '}\n'

    return s;

#------------------------------------------------------------------------------
# 'p' is a Processinfo
#------------------------------------------------------------------------------
def source_string(self,p):
    s  = ''

    for x in p.list_of_sources:
        s += f' s{x.rank}: {{'
        s += f' transferPluginType: {self.transfer}'
        s += f' source_rank:  {x.rank}'
        s += f' max_fragment_size_words: {p.max_fragment_size_words()}'
        
        # first destination includes the host_map
        if (x == p.list_of_sources[0]):
            s += ' host_map: ['
            offset = ''
            s += self.host_map_string(offset);
            s += ']'
            
        s +=  '}\n'

    return s;
    
#------------------------------------------------------------------------------
# place in expanded FHICL file, no more processing needed
# also need to replace some lines which could be process specific
#------------------------------------------------------------------------------
def update_fhicl(self, procinfo, max_fragment_size_words):
    # step 1 : read and replace - start from BRs
    print('------ update_fhicl')
    procinfo.print()
    
    with open(procinfo.fhicl,'r') as f:
        lines = f.readlines()

    new_text = []
    if (procinfo.type() == BOARD_READER):
        for line in lines:
            # print(line);
            new_text.append(line)
            if (line.find('daq.fragment_receiver.destinations') >= 0):
                # always replace the line with the real string
                # max_fragment_size_words is calculated
                s = self.destination_string(procinfo,max_fragment_size_words)
                new_text.append(s)
                
    elif (procinfo.type() == EVENT_BUILDER):
        for line in lines:
            # print(line);
            new_text.append(line);
            pattern = 'daq.event_builder.sources';
            match = re.search(pattern,line)
            if (match):
                # always replace the line with the real string
                # max_fragment_size_words is calculated
                s = self.source_string(procinfo,max_fragment_size_words)
                new_text.append(s)
                continue

            pattern = r'art.outputs.([\w.-]+).destinations'
            match = re.search(pattern,line)
            if (match):
                module = match.group(1);
                s = self.destination_string(procinfo,max_fragment_size_words);
                new_text.append(s);
                continue;
                
            pattern = r'art.outputs.([\w.-]+).host_map'
            match = re.search(pattern,line)
            if (match):
                module = match.group(1);
                offset = '    ' # 4 spaces (TCL indent)
                s = self.host_map_string(offset);
                new_text.append(s);
                continue;

    elif (procinfo.type() == DATA_LOGGER):
        for line in lines:
            # print(line);
            new_text.append(line);
            pattern = 'daq.aggregator.sources';
            match = re.search(pattern,line)
            if (match):
                # always replace the line with the real string
                # max_fragment_size_words is calculated
                s = self.source_string(procinfo,max_fragment_size_words)
                new_text.append(s)
                continue

            pattern = r'art.outputs.([\w.-]+).destinations'
            match = re.search(pattern,line)
            if (match):
                module = match.group(1);
                s = self.destination_string(procinfo,max_fragment_size_words);
                new_text.append(s);
                continue;
                
            pattern = r'art.outputs.([\w.-]+).host_map'
            match = re.search(pattern,line)
            if (match):
                module = match.group(1);
                offset = '    ' ## 4 spaces, TCL indent
                s = self.host_map_string(offset);
                new_text.append(s);
                continue;
    

    #-------- write updated FCL
    new_fn = f'/tmp/partition_{self.partition()}/{self.config_name}/{procinfo.label}.fcl'
    with open(new_fn,'w') as f:
        f.writelines(line for line in new_text)
        
    # step 2 : flatten
    res = subprocess.run(['fhicl-dump', new_fn],capture_output=True,text=True);
    if (res.returncode != 0):
        raise Exception(res.stderr)
    
    procinfo.fhicl      = new_fn;
    procinfo.fhicl_used = res.stdout;

    print('----------------------------- end of update_fhicl')
    print(procinfo.fhicl_used);


def test001():
    return 0

#------------------------------------------------------------------------------
if __name__ == "__main__":
    x = test_001()
