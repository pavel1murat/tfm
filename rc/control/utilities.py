#!/usr/bin/env python

import os, re, string, socket, shutil, sys, stat

import subprocess
from   subprocess import Popen
from   datetime   import datetime
from   zoneinfo   import ZoneInfo

from   time       import sleep
from   time       import time

from   threading  import Thread

import TRACE; TRACE_NAME="utilities";

# from rc.control.procinfo import Procinfo

# PM: no more UPS
# bash_unsetup_command = 'upsname=$( which ups 2>/dev/null ); if [[ -n $upsname ]]; then unsetup() { . `$upsname unsetup "$@"` ; }; for pp in `printenv | sed -ne "/^SETUP_/{s/SETUP_//;s/=.*//;p}"`; do test $pp = UPS && continue; prod=`echo $pp | tr "A-Z" "a-z"`; unsetup -j $prod; done; echo "After bash unsetup, products active (should be nothing but ups listed):"; ups active; else echo "ups does not appear to be set up; will not unsetup any products"; fi'

# Raise exceptions from threads https://stackoverflow.com/questions/2829329/catch-a-threads-exception-in-the-caller-thread
class RaisingThread(Thread):
    def run(self):
        self._exc = None
        try:
            super().run()
        except Exception as e:
            self._exc = e

    def join(self, timeout=None):
        super().join(timeout=timeout)
        if self._exc:
            raise self._exc


def make_paragraph(userstring, chars_per_line=75):
    userstring.strip()

    string_index          = chars_per_line
    previous_string_index = -1
    ignore_algorithm      = False

    userstring            = userstring.replace("\n", " ")

    while len(userstring) - string_index > 0:

        if not ignore_algorithm:
            while not userstring[string_index].isspace():
                string_index -= 1
                assert string_index >= 0
        else:
            while not userstring[string_index].isspace():
                string_index += 1
                if len(userstring) <= string_index:
                    return "\n" + userstring

        userstring = userstring[:string_index] + "\n" + userstring[string_index + 1 :]

        string_index += chars_per_line

        # If there's a token with no whitespace which is longer
        # than chars_per_line characters (as may be the case with
        # some full pathnames, e.g.) there's a risk of an infinite
        # loop without the external logic below

        if previous_string_index == string_index:
            ignore_algorithm = True

        previous_string_index = string_index

    return "\n" + userstring


# JCF, 3/11/15

# "get_pids" is a simple utility function which will go to the
# requested host (defaults to the local host), and searches for a
# process by grep-ing for the passed greptoken in the process
# table returned by "ps aux". It returns a (possibly empty) list
# of the process IDs found

# JCF, Dec-12-2018

# Have "grepresults" serve as a pass-by-reference in which, if the caller
# thinks not just the pid list but the actual lines grep'd for may be
# of interest - e.g., for diagnostics or debugging - they can save
# this result

#------------------------------------------------------------------------------
# assume that a long hostname might have been passed, allow for 'localhost'
#------------------------------------------------------------------------------
def host_is_local(host):
    return ( (host == "localhost") or (socket.gethostname() in host) )

#------------------------------------------------------------------------------
def get_pids(greptoken, host="localhost", grepresults=None):

    cmd = 'ps aux | grep "%s" | grep -v grep' % (greptoken)

    if not host_is_local(host):
        cmd = "ssh -x %s '%s'" % (host, cmd)

    # breakpoint()
    proc = subprocess.Popen(cmd, shell=True, executable="/usr/bin/bash", stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")

    out, err = proc.communicate()
    lines = []
    if len(out) > 0:
        lines = out.strip().split('\n')
    if len(err) > 0:
        raise Exception(
            "SSH process for retrieving PIDs had the following error output:\n %s"
            % (err)
        )

    if grepresults is not None:
        for line in lines:
            grepresults.append(
                line
            )  # Clunkier than a straight assignment, but needed for pass-by-reference

    pids = [line.split()[1] for line in lines]

    return pids

#------------------------------------------------------------------------------
# [Comment added by KAB, 17-Apr-2018]
# This function returns the contents of the FHiCL table that immediately
# follows the specified string (tablename).  It does not require that
# 'tablename' actually be a FHiCL key.
#------------------------------------------------------------------------------
def table_range(fhiclstring, tablename, startingloc=0):

    # 13-Apr-2018, KAB: added the startingloc argument so that this function can
    # be used to find more than the first instance of the tablename in the string.
    loc = fhiclstring.find(tablename, startingloc)

    if loc == -1:
        return (-1, -1)

    # JCF, Apr-18-2019
    # Account for the scenario where in the FHiCL we have something like
    # table_whose_range_we_want: @local::table_which_gets_assigned_to_table_whose_range_we_want

    res = re.search(r"%s\s*:\s*@local::(\S+)" % tablename, fhiclstring[loc:])
    if res:
        original_table_name = res.group(1)
        return table_range(fhiclstring, original_table_name)

    # JCF, Aug-1-2019

    # Check that what we have is actually a table - this is prompted
    # by an email Kurt sent on June 26, 12:46 PM. If it's not, then
    # keep searching further on in the FHiCL blob.

    res = re.search(r"^%s\s*:\s*{" % tablename, fhiclstring[loc:])
    if not res:
        (offset_start, offset_end) = table_range(fhiclstring[loc + 1 :], tablename)
        if (offset_start, offset_end) != (-1, -1):
            return (loc + 1 + offset_start, loc + 1 + offset_end)
        else:
            return (-1, -1)

    open_brace_loc = fhiclstring[loc:].index("{")

    close_braces_needed = 1
    close_brace_loc = -1

    for i_char, char in enumerate(fhiclstring[(loc + open_brace_loc + 1) :]):

        if char == "{":
            close_braces_needed += 1
        elif char == "}":
            close_braces_needed -= 1

        if close_braces_needed == 0:
            close_brace_loc = i_char
            break

    if close_brace_loc == -1:
        raise Exception(
            'Unable to find close brace for requested table "%s"' % tablename
        )

    return (loc, loc + open_brace_loc + 1 + close_brace_loc + 1)


# 17-Apr-2018, KAB: added this function to find the *enclosing* FHiCL
# table for the specified string. This can be useful when looking for
# a table that has a desirable FHiCL value, and we want to fetch the
# contents of the entire table.
def enclosing_table_range(fhiclstring, searchstring, startingloc=0):

    loc = fhiclstring.find(searchstring, startingloc)

    if loc == -1:
        return (-1, -1)

    braces_before = [
        (i + startingloc, c)
        for (i, c) in enumerate(fhiclstring[startingloc:loc])
        if (c == "}" or c == "{")
    ]

    opening_count = 0
    closing_count = 0
    opening_position = -1

    for brace in reversed(braces_before):
        if brace[1] == "{":
            opening_count += 1
        else:
            closing_count += 1

        if opening_count - closing_count == 1:
            opening_position = brace[0]
            break

    if opening_position == -1:
        return (-1, -1)

    braces_after = [
        (i + loc, c)
        for (i, c) in enumerate(fhiclstring[loc:])
        if (c == "}" or c == "{")
    ]

    opening_count = 0
    closing_count = 0
    closing_position = -1

    for brace in braces_after:
        if brace[1] == "}":
            closing_count += 1
        else:
            opening_count -= 1

        if closing_count - opening_count == 1:
            closing_position = brace[0]
            break

    if closing_position == -1:
        return (-1, -1)

    return (opening_position, closing_position + 1)


# 26-Nov-2018, ELF: This function finds the name of the enclosing table
# for the specified string. This is used when determining which
# destinations block is currently being filled during bookkeeping.
def enclosing_table_name(fhiclstring, searchstring, startingloc=0):

    (open_brace_loc, close_brace_loc_will_be_ignored) = enclosing_table_range(
        fhiclstring, searchstring, startingloc
    )

    colon_loc = fhiclstring.rindex(":", 0, open_brace_loc)

    while fhiclstring[colon_loc - 1] == " ":
        colon_loc -= 1

    name = re.sub(".*\s", "", fhiclstring[:colon_loc])

    return name


# def commit_check_throws_if_failure(packagedir, commit_hash, date, request_after):
# 
#     assert os.path.exists(packagedir), (
#         "Directory %s doesn't appear to exist; a check should occur earlier in the program for this"
#         % (packagedir)
#     )
# 
#     cmds = []
#     cmds.append("cd " + packagedir)
#     cmds.append("git log | grep %s" % (commit_hash))
# 
#     proc = Popen(
#         ";".join(cmds), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="UTF-8"
#     )
#     proclines = proc.stdout.readlines()
# 
#     if request_after and len(proclines) != 1:
#         raise Exception(
#             make_paragraph(
#                 'Unable to find expected git commit hash %s (%s) in directory "%s"; this means the version of code in that directory isn\'t the one expected'
#                 % (commit_hash, date, packagedir)
#             )
#         )
#     elif not request_after and len(proclines) != 0:
#         raise Exception(
#             make_paragraph(
#                 'Unexpectedly found git commit hash %s (%s) in directory "%s"; this means the version of code in that directory isn\'t the one expected'
#                 % (commit_hash, date, packagedir)
#             )
#         )


def is_msgviewer_running():

    for line in Popen(
        "ps u", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="UTF-8"
    ).stdout.readlines():
        if (
            "msgviewer" in line
                # P.Murat: don't need message viewer, turn it off softly
#            and "TFM_TTY" in os.environ
#            and os.environ["TFM_TTY"] in line
        ):
            return True

    return False


def execute_command_in_xterm(home, cmd):

    if not os.path.exists(os.environ["HOME"] + "/.Xauthority"):
        raise Exception("Unable to find .Xauthority file in home directory")

    if home != os.environ["HOME"]:
        status = Popen(
            "cp -p ~/.Xauthority %s" % (home),
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).wait()
        if status != 0:
            raise Exception(
                "Unable to copy .Xauthority file into directory %s; do you have write permissions there?"
                % (home)
            )

    # JCF, May-11-2017

    # The following chant to xterm is influenced both by Ron's
    # implementation of xt_cmd.sh in artdaq-demo as well as the info
    # found at
    # https://superuser.com/questions/363614/leave-xterm-open-after-task-is-complete

    fullcmd = (
        'env -i SHELL=/bin/bash PATH=/usr/bin:/bin LOGNAME=%s USER=%s  DISPLAY=%s  REALHOME=%s HOME=%s KRB5CCNAME=%s  xterm -geometry 100x33+720+0 -sl 2500 -e "%s ; read " &'
        % (
            os.environ["LOGNAME"],
            os.environ["USER"],
            os.environ["DISPLAY"],
            os.environ["HOME"],
            home,
            os.environ["KRB5CCNAME"],
            cmd,
        )
    )

    Popen(
        fullcmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).wait()


#------------------------------------------------------------------------------
# return date and time in Chicago with 0.1 sec precision
#------------------------------------------------------------------------------
def date_and_time():
    return datetime.now(tz=ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S.%f")[:-5]

def date_and_time_more_precision():
    return datetime.now(tz=ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S.%f")[:-4]

def date_and_time_filename():
    return datetime.now(tz=ZoneInfo("America/Chicago")).strftime("%Y%m%d%H%M%S")

def construct_checked_command(cmds):

    checked_cmds = []

    for cmd in cmds:
        TRACE.DEBUG(1,f'cmd:{cmd}',TRACE_NAME)
        checked_cmds.append(cmd)

#        if not re.search(r"\s*&\s*$", cmd) and not bash_unsetup_command in cmd:
        if not re.search(r"\s*&\s*$", cmd): #  and not bash_unsetup_command in cmd:
            check_cmd = (
                ('if [[ "$?" != "0" ]]; then '
                 'echo %s: Nonzero return value from the following command: "%s" '
                '>> /tmp/daqinterface_checked_command_failures_%s.log; '
                 'exit 1;'
                 ' fi ') % (date_and_time(), cmd, os.environ["USER"])
            )
            checked_cmds.append(check_cmd)

    total_cmd = " ; ".join(checked_cmds)

    return total_cmd

#------------------------------------------------------------------------------
# P.Murat: this one was a disaster, as in the only place it is called for, one 
#          associates the reformatted fcl's to  procinfos
# 2026-01-30: fcl's are already processed through fhicl-dump - do we need to do it the
#             second time ?
#------------------------------------------------------------------------------
def reformat_fhicl_documents(setup_fhiclcpp, procinfos):
    TRACE.DEBUG(0,f'-- START',TRACE_NAME)

    if not os.path.exists(setup_fhiclcpp):
        raise Exception(
            make_paragraph("Expected fhiclcpp setup script %s doesn't appear to exist" % setup_fhiclcpp)
        )

    cmd = "grep -c ^processor /proc/cpuinfo"

    nprocessors = (
        Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="UTF-8")
        .stdout.readlines()[0]
        .strip()
    )

    if not re.search(r"^[0-9]+$", nprocessors):
        raise Exception(
            make_paragraph(
                'A problem occurred when TFM tried to execute "%s"; result was not an integer'
                % (cmd)
            )
        )

    reformat_indir = (
        Popen("mktemp -d", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="UTF-8")
        .stdout.readlines()[0]
        .strip()
    )
    reformat_outdir = (
        Popen("mktemp -d", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="UTF-8")
        .stdout.readlines()[0]
        .strip()
    )
    TRACE.DEBUG(0,f'reformat_indir :{reformat_indir} reformat_outdir:{reformat_outdir}' ,TRACE_NAME);

    for p in procinfos:
        fn = "%s/%s.fcl" % (reformat_indir, p.label)
        with open(fn, "w") as preformat_fhicl_file:
            preformat_fhicl_file.write(p.fhicl_used)

    cmds = []
    cmds.append("if [[ -z $( command -v fhicl-dump ) ]]; then source %s; fi" % setup_fhiclcpp)
    cmds.append("if [[ $FHICLCPP_VERSION =~ v4_1[01]|v4_0|v[0123] ]]; then dump_arg=0; else dump_arg=none; fi")
    cmds.append("cd %s" % reformat_indir)

    xargs_cmd = (
        "find ./ -name \*.fcl -print | xargs -I {} -n 1 -P %s fhicl-dump -l $dump_arg -c {} -o %s/{}"
        % (nprocessors, reformat_outdir)
    )
#------------------------------------------------------------------------------
# 'reformatted' means expanded by fhicl-dump
#------------------------------------------------------------------------------
    cmds.append("echo About to execute '%s'" % xargs_cmd)
    cmds.append(xargs_cmd)
    
    # breakpoint()
    TRACE.DEBUG(0,f'commands:',TRACE_NAME)
    for cmd in cmds:
        TRACE.DEBUG(0,f'{cmd}',TRACE_NAME)

    proc = Popen("\n".join(cmds), shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, 
                 encoding="UTF-8")
    proc.wait()
#------------------------------------------------------------------------------
# to check the return code need to wait...
#---v--------------------------------------------------------------------------
    TRACE.DEBUG(0,f'proc.returncode:{proc.returncode}',TRACE_NAME)
    if proc.returncode != 0:

        if proc.stdout : print(proc.stdout)
        if proc.stderr : print(proc.stderr)

        raise Exception(
            ("There was a problem reformatting the FHiCL documents found in %s;"
             " this is very likely due to illegal FHiCL syntax somewhere."
             " See above for more info.") % reformat_indir
        )

    for p in procinfos:
        fn = "%s/%s.fcl" % (reformat_outdir, p.label)
        with open(fn) as reformatted_fhicl_file:
            p.fhicl_used = reformatted_fhicl_file.read()

    shutil.rmtree(reformat_indir)
    shutil.rmtree(reformat_outdir)

    TRACE.DEBUG(0,f'-- END',TRACE_NAME)
    return # end of reformat_fhicl_documents, P.Murat: don't need to return anything


def fhicl_writes_root_file(fhicl_string):
#------------------------------------------------------------------------------
# 17-Apr-2018, KAB: added the MULTILINE flag to get this search to behave as desired.
# 30-Aug-2018, KAB: added support for RootDAQOutput
# P.M. the logic is completely childish.. a high schooler would fare better
# a high schooler would look for 'outputs: {' and a 'fileName:'
#---v--------------------------------------------------------------------------
    # breakpoint()
    found          = False
    fhicl_struct   = [];
    nest_level     = 0;
    key            = None
    inside_outputs = 0;

    for s in fhicl_string.split('\n'):
        s_strip  = s.strip();
        l1       = 0;
        if ((s_strip[l1:] == '') or (s[0] == '#')): continue
        loc = s_strip[l1:].find(':');
        if (loc >= 0): 
            key = s_strip[:loc].strip()
            l1  = loc;
#------------------------------------------------------------------------------
# 
#-------v----------------------------------------------------------------------
        if (key == 'outputs'):
          inside_outputs = 1
          if (s_strip.find('{') >= 0):
              fhicl_struct.append(key);
              nest_level +=1
        elif (inside_outputs == 1):
            if (key == 'fileName'):
#------------------------------------------------------------------------------
# the output module label doesn't matter
# assume certain structure of the FHICL document
#---------------v--------------------------------------------------------------
                found = True;
                break;
            else:
                if (s_strip.find('{') >= 0):
                    nest_level +=1
                    fhicl_struct.append(key);
                if (s_strip.find('}') >= 0):
                    nest_level -=1
                    fhicl_struct.pop()
                    if (nest_level == 0): inside_outputs = 0

    return found;
        
#     if ("RootOutput" in fhicl_string or "RootDAQOut" in fhicl_string) and re.search(
#         r"^\s*fileName\s*:\s*.*\.root", fhicl_string, re.MULTILINE
#     ):
#         return True
#     else:
#         return False




def fhiclize_document(filename):

    fhiclized_lines = []

    with open(filename) as inf:
        for line in inf.readlines():
            # Parse any line that's not blank or a comment
            if not re.search(r"^\s*$", line) and not re.search(r"^\s*#.*$", line):
                res = re.search(r"^\s*(\S[^:]*):\s*(\S.*)[\s]", line)
                if res:
                    key = res.group(1)
                    key = "_".join(key.split())
                    key = re.sub(r"[\(\)/]", "_", key)

                    value = res.group(2)
                    value = value.strip(' "')
                    value = value.strip("'")
                    value = value.replace('"', '\\"')

                    fhiclized_lines.append('%s: "%s"' % (key, value))
                else:
                    print(
                        'WARNING: %s not able to FHiCLize the line "%s"'
                        % (fhiclize_document.__name__, line.rstrip())
                    )
            else:
                continue
    return "\n".join(fhiclized_lines)

#------------------------------------------------------------------------------
def get_private_networks(host):
    cmd = '/usr/sbin/ifconfig | sed -r -n "s/^\s*inet\s+(192\.168\.\S+|10\.\S+)\s+.*/\\1/p"'

    if not host_is_local(host):
        cmd = "ssh -x %s '%s'" % (host, cmd)

    lines = Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="UTF-8"
    ).stdout.readlines()
    networks = []

    for line in lines:
        network = line.strip()
        res = re.search(r"^([0-9]+\.[0-9]+\.[0-9]+\.)[0-9]+", network)
        if not res:
            raise Exception(
                'Unexpected result from command "%s"; line "%s" doesn\'t appear to be an address'
                % (cmd, network)
            )
        networks.append(network)

    return networks


def zero_out_last_subnet(network):
    res = re.search(r"^([0-9]+\.[0-9]+\.[0-9]+\.)[0-9]+", network)
    assert res, 'Developer error: proper address not passed to "zero_out_last_subnet"'
    return "%s0" % (res.group(1))


# 2026-02-11 PM #def upsproddir_from_productsdir(productsdir):
# 2026-02-11 PM #    for pp in productsdir.split(":"):
# 2026-02-11 PM #        upsproddir = ""  # may not find what we're looking for
# 2026-02-11 PM #        tt = pp.rstrip("/") + "/"  # make sure it ends with _single_ '/'
# 2026-02-11 PM #        if (
# 2026-02-11 PM #            os.path.isdir(tt)
# 2026-02-11 PM #            and os.path.isfile(tt + "setup")
# 2026-02-11 PM #            and os.path.isdir(tt + ".upsfiles")
# 2026-02-11 PM #            and os.path.isdir(tt + "ups")
# 2026-02-11 PM #        ):
# 2026-02-11 PM #            upsproddir = pp.rstrip("/")  # make sure it does not end with '/'
# 2026-02-11 PM #            break
# 2026-02-11 PM #    return upsproddir
# 2026-02-11 PM #

def record_directory_info(recorddir):
    if not os.path.exists(recorddir):
        raise Exception('Directory "%s" doesn\'t exist, exiting...')
    stats = os.stat(recorddir)
    return "inode: %s" % (stats.st_ino)

def get_setup_commands(productsdir=None, spackdir=None, log_file=None):
    output = []
    if productsdir != None:
        if log_file == None:
            output.append(
                'export PRODUCTS="%s"; . %s/setup'
                % (
                    productsdir,
                    upsproddir_from_productsdir(productsdir),
                )
            )
        else:
            output.append(
                'export PRODUCTS="%s"; . %s/setup >> %s 2>&1 '
                % (
                    productsdir,
                    upsproddir_from_productsdir(productsdir),
                    log_file,
                )
            )
        output.append(
                bash_unsetup_command + " > /dev/null 2>&1 "
        )
    elif spackdir != None:
        if log_file == None:
            output.append('. %s/share/spack/setup-env.sh' % (spackdir))
            output.append('spack unload > /dev/null 2>&1')
        else:
            output.append('. %s/share/spack/setup-env.sh >> %s 2>&1' % (spackdir, log_file))
            output.append('spack unload > /dev/null 2>&1')
    return output

def kill_tail_f():
    
    tail_pids = ""; # P.Murat: turn it off "softly"
    
    if len(tail_pids) > 0:
        status = Popen("kill %s" % (" ".join(tail_pids)), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait()
        if status != 0:
            print(
                "There was a problem killing \"tail -f\" commands in this terminal; "
                "you'll want to do this manually or you'll get confusing output moving forward"
            )

if __name__ == "__main__":
    main()
