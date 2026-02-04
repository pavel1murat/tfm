#!/bin/env/python

import os, sys, argparse, glob, inspect, re, subprocess

from   tfm.rc.control.procinfo          import Procinfo, BOARD_READER, EVENT_BUILDER, DATA_LOGGER, DISPATCHER, ROUTING_MANAGER ;


#------------------------------------------------------------------------------
# list_of_processes is either a p.list_of_destinations or a p.list_of_sources
#------------------------------------------------------------------------------
def host_map_string(plist,offset = ''):
    s = ''
    for p in plist:
        s += f' {{ rank:{p.rank:3} host: "{p.host}"}}';
        if (p != plist[-1]):
            s += ','

    return s;

#------------------------------------------------------------------------------
# 'p' is a Processinfo
#------------------------------------------------------------------------------
def destination_string(p,transfer_plugin):
    s = ''
    for d in p.list_of_destinations:
        s += f' d{d.rank}: {{'
        s += f' transferPluginType: {transfer_plugin}'
        s += f' destination_rank:  {d.rank}'
        # for BR, event=fragment
        s += f' max_fragment_size_words: {p.max_event_size_words()}'
        
        # first destination includes the host_map
        if (d == p.list_of_destinations[0]):
            offset = '        '
            s += ' host_map: ['
            s += host_map_string(p.list_of_destinations,offset);
            s += ' ]'
            
        s +=  '}\n'

    return s;

#------------------------------------------------------------------------------
# 'p' is a Processinfo
#------------------------------------------------------------------------------
def source_string(p,transfer_plugin):
    s  = ''

    for x in p.list_of_sources:
        s += f' s{x.rank}: {{'
        s += f' transferPluginType: {transfer_plugin}'
        s += f' source_rank:  {x.rank}'
        s += f' max_fragment_size_words: {x.max_event_size_words()}'
        
        # first destination includes the host_map
        if (x == p.list_of_sources[0]):
            s += ' host_map: ['
            offset = ''
            s += host_map_string(p.list_of_sources,offset);
            s += ' ]'
            
        s +=  '}\n'

    return s;
    
#------------------------------------------------------------------------------
# place in expanded FHICL file, no more processing needed
# also need to replace some lines which could be process specific
#------------------------------------------------------------------------------
def update_fhicl(procinfo, transfer_plugin, tmp_dir):
    # step 1 : read and replace - start from BRs
    print('------ update_fhicl')
    procinfo.print()
    
    with open(procinfo.fhicl,'r') as f:
        lines = f.readlines()

    new_text = []
    if (procinfo.type() == BOARD_READER):
        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = destination_string(procinfo,transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue
                
            pattern = r'(?:[\w-]+\.)*max_fragment_size_bytes'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {procinfo.max_fragment_size_bytes}\n';
                new_text.append(s);
                continue;

            new_text.append(line)
                
    elif (procinfo.type() == EVENT_BUILDER):
        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*sources'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                # always replace the line with the real string
                # max_fragment_size_words is calculated
                s = source_string(procinfo,transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue

            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = destination_string(procinfo,transfer_plugin);
                new_text.append(s);
                new_text.append('}\n');
                continue;
                
            pattern = r'(?:[\w-]+\.)*host_map'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: [');
                offset = '    ' # 4 spaces (TCL indent)
                s      = host_map_string(procinfo.list_of_destinations,offset);
                new_text.append(s);
                new_text.append(' ]\n');
                continue;

            pattern = r'(?:[\w-]+\.)*max_event_size_bytes'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {procinfo.max_event_size_bytes}\n';
                new_text.append(s);
                continue;

            new_text.append(line);
            
    elif (procinfo.type() == DATA_LOGGER):
        for line in lines:
            # print(line);
            pattern = r'(?:[\w-]+\.)*sources'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = source_string(procinfo,transfer_plugin)
                new_text.append(s)
                new_text.append('}\n');
                continue

            pattern = r'(?:[\w-]+\.)*destinations'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: {{\n');
                s = destination_string(procinfo,transfer_plugin);
                new_text.append(s);
                new_text.append('}\n');
                continue;
                
            pattern = r'(?:[\w-]+\.)*host_map'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                new_text.append(f'{key}: [');
                offset = '    ' ## 4 spaces, TCL indent
                # host_map_string - always destinations
                s = host_map_string(procinfo.list_of_destinations,offset);
                new_text.append(s);
                new_text.append(' ]\n');
                continue;
    
            pattern = r'(?:[\w-]+\.)*max_event_size_bytes'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {procinfo.max_event_size_bytes}\n';
                new_text.append(s);
                continue;

            pattern = r'(?:[\w-]+\.)*init_fragment_count'
            match = re.search(pattern,line)
            if (match):
                key = match.group(0);
                # in this case, replaces
                s      = f'{key}: {procinfo.init_fragment_count}\n';
                new_text.append(s);
                continue;

            #------------------------------------------------------------------------------
            # any other line - just rewrite
            #------------------------------------------------------------------------------
            new_text.append(line);

    elif (procinfo.type() == DISPATCHER):
        raise Exception('DISPATCHER: IMPLEMENT ME!')
    
    elif (procinfo.type() == ROUTING_MANAGER):
        raise Exception('ROUTING_MANAGER: IMPLEMENT ME!')
    
#---------------^--------------------------------------------------------------
#  write updated FCL
#-------v----------------------------------------------------------------------
    new_fn = f'{tmp_dir}/{procinfo.label}.fcl'
    with open(new_fn,'w') as f:
        f.writelines(line for line in new_text)
        
    # step 2 : flatten
    res = subprocess.run(['fhicl-dump', new_fn],capture_output=True,text=True);
    procinfo.fhicl      = new_fn;
    procinfo.fhicl_used = res.stdout;

    print('----------------------------- end of update_fhicl')
    print(procinfo.fhicl_used);
    return

#---^--------------------------------------------------------------------------
# marking the end
#------------------------------------------------------------------------------
