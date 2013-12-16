#!/usr/bin/python
# -*- coding: utf-8 -*-
# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2011, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
__author__ = 'clarkmatthew'


from san_volume_info import  San_Volume_Info
from eutester.sshconnection import SshConnection, SshCbReturn, CommandExitCodeException, CommandTimeoutException
from eutester.eulogger import Eulogger
import re
import string




class San_Client():
    '''
    Basic San Client test interface to be implemented by each SAN client. The intention is to use a common
    interface to verify SAN side operations when resources from that san are used in cloud operations.
    '''

    def __init__(self, host, username, password):
            self.host = host
            self.username = username
            self.password = password
            self.connection = self.connect()
            self.logger = Eulogger(identifier= 'SAN-'+str(host))
            self.debug= self.logger.log.debug

    @classmethod
    def get_san_client_by_type(cls, host, username, password, santype):
        '''
        Returns a SAN client type object by santype.

        param host: string representing the hostname/ip of the SAN
        param username: string username used to access the SAN
        param password: string password used to access the SAN
        param santype: string used to determine what SAN client to create and return. Supported Values: 'netapp'
        returns San_Client obj of type santype
        '''
        if santype == 'netapp':
            return Netapp_Client(host, username, password)
        else:
            raise Exception('Unknown santype provided:' + str(santype))

    def connect(self):
        '''
        Will perform the steps needed to connect/interface with the SAN/San_Client
        '''
        raise Exception('Not Implemented')

    def sys(self, cmd, timeout=60, code=0):
        '''
        Will Executes the command provided against the San_Client interface
        param cmd: string representing the command to be executed against this san San_Client
        param timeout: optional timeout for the command which is executed
        param code: optional integer value used to provide the expected return code
        returns sanclient's output from the executed command
        '''
        raise Exception('Not Implemented')

    def get_san_volume_info_by_id(self, volumeid):
        '''
        Attempt to populate a san_volume_info obj with information about a given volumeid
        param volumeid: string representing the volume's id in which to gather information
        returns san_volume_info
        '''
        raise Exception('Not Implemented')



class netapp_menu():

    def __init__(self, path_string,  san_client, help_string = "", dir_list_raw=None, scan_all=False):
        '''
        Represent a Netapp cli menu context.
        param path_string: the relative path or context within the san client Netapp_Client cli
        param san_client: the Netapp_Client
        param help_string: optional string which can be used as a doc string and help string for this menu context
        param dir_list_raw: optional Netapp_Client list of strings representing the menu context
        '''
        self._path_string = path_string
        self._helpstring = help_string
        self.__doc__ = self._helpstring
        self._san_client = san_client
        self._dir_list_raw = dir_list_raw or self._get_dir_list_raw(scan_all=scan_all)
        self._parse_dir_list()

    def _get_dir_list_raw(self, listformat=True, scan_all=False):
        '''
        Will attempt to get the contents of this menu context and will present the text returned from the san Netapp_Client
        in either a single string buffer or list of lines/strings
        param listformat: boolean when true, the output will be returned as a list of strings
        '''
        ret = [] if listformat else ""
        ret = self._san_client.sys("?")
        if scan_all:
            for letter in string.lowercase:
                if listformat:
                    try:
                        scan_results = self._san_client.sys_send_non_exec(str(letter)+"\t", timeout=2)
                        ret.extend(self._parse_scanned_results(scan_results))
                    except CommandTimeoutException:
                        pass
                else:
                    ret += self._san_client.sys_send_non_exec(str(letter)+"\t", listformat=False,timeout=2)
        return ret

    def _parse_scanned_results(self, scan_results, prompt='::>'):
        #todo lookup each key and better distinguish between command and new menu item, also provide more help info
        keywords = []
        ret_list = []
        for line in scan_results:
            if re.search('Error', line, re.IGNORECASE):
                #There's no commands for this specific menu context
                return []
            if line and not re.search(prompt, line):
                split = line.strip().split()
                keywords.extend(split)
        for key in keywords:
            self._san_client.debug('Scan found KEY:'+str(key))
            out = self._san_client.sys(key + "?")
            print "\n".join(str(x) for x in out)
            ret_list.extend(out)
        return ret_list

    def print_help(self):
        '''
        method that will print the help contents for this menu context
        '''
        return self._san_client.debug("\n"+ self._get_dir_list_raw(listformat=False))

    def _exec_sys(self, cmd, verbose=True):
        '''
        Helper function to execute commands on the remote san via the provided san client interface
        param cmd: string representing the command to execute on the san_volume_info
        param verbose: boolean if true will print the command to the san client's debug method
        '''
        if verbose:
            self._san_client.debug(str(cmd))
        return self._san_client.sys(cmd)

    def _get_new_command(self, path, docstring =""):
        '''
        Attempt to create dynamic methods for the menu items found when traversing the cli menu(s)
        param path: string representing the cli menu path to this obj/command
        param docstring: optional string will be used to populate the docstring of the returned method
        '''
        def new_command( string = "" ):
            return self._exec_sys(path + ' ' + string)
        new_command.__doc__ = docstring
        new_command.help = lambda x='?':new_command(x)
        return new_command


    def _parse_dir_list(self):
        '''
        Attempt to traverse and discover  all the items in the menu item and either create executable methods or
        new netapp_menu items which contain more cli methods/menus.
        '''
        self._san_client.debug('Populating CLI dir:' + self._path_string)
        last_obj = None
        for line in self._dir_list_raw:
            split = line.split()
            if split:
                keyname = split.pop(0)
                value = str(" ".join(str(x) for x in split))
                #is this line a help string continuation
                if re.search(',',keyname):
                    if last_obj:
                        last_obj.__doc__ += keyname + value
                #is this line a new menu option
                elif re.search('>', keyname) or re.search("Manage", value):
                    keyname = keyname.replace('>','')
                    dir = netapp_menu(self._path_string + " " + keyname, self._san_client)
                    dir.__doc__ = value
                    setattr(self, keyname, dir)
                    last_obj = dir
                #is this line a command in this menu context
                else:
                    match = re.search('\w+', keyname)
                    if match:
                        keyname = match.group()
                        newpath = str(self._path_string) + " " + str(keyname)
                        docstring = "Command:" + str(newpath) + ". " + value
                        command = self._get_new_command(newpath, docstring=docstring)
                        setattr(self, keyname, command)
                        last_obj = command


class Netapp_Client(San_Client):


    def connect(self):
        '''
        Attempts to connect to the SAN cli via ssh
        '''
        ssh = SshConnection(host=self.host, username=self.username, password=self.password)
        if not ssh:
            raise Exception('Could not connect to SAN at:' + str(self.host))
        self.sys = ssh.sys
        return ssh

    def get_san_volume_info_by_id(self, volumeid):
        '''
        Attempts to gather info from the san client about the volume id provided.
        Returns a San_Volume_Info object representing the volume's san client information

        param volumeid: string representing the volumeid ie:vol-abcd123
        returns San_Volume_Info object
        '''
        info_dict = self._get_volume_basic_info_by_id(volumeid)
        eff_dict = self._get_volume_efficiency_info_by_id(volumeid)
        san_info_obj = San_Volume_Info( volumeid, dict(info_dict.items() + eff_dict.items()), self)
        return san_info_obj

    def _format_volume_id(self,volumeid):
        id = str(volumeid).replace('-','_')
        return id

    def _raw_cb(self, buf, promptcount, promptstring, promptmax, debug):
        '''
        Call back which can be used to control and ssh command when a shell and raw
         input needed (ie to send controlled tabs for example)
        param buf: buffer provided by ssh.cmd session
        param promptcount: int amount of times we've seen the prompt
        param promptstring: string the string to match
        param promptmax: the maximum number prompt matches before the command is signaled 'done'
        returns SshCbReturn obj
        '''
        ret = SshCbReturn(buf=buf, stop=False)
        #Count the number of occurrences of the promptstring
        promptcount = promptcount + len(re.findall(promptstring,buf))
        if promptcount >= promptmax:
            ret.stop = True
        #Return the args this call back will be called with the next time around
        ret.nextargs=[promptcount, promptstring, promptmax, debug]
        if debug:
            print str(buf)+ '\npromptcount:' + str(promptcount) + ', promptstring:' + str(promptstring) + ', promptmax:'+ str(promptmax)
        return ret

    def sys_send_non_exec(self, cmd, promptstring='::>', promptmax=2, listformat=True, timeout=120, debug=False, code=0):
        '''
        Ssh connection command which can be used when raw input to a remote shell
         are needed (ie to send controlled tabs for example)

        param cmd: String to be send to remote ssh shell
        param promptstring: string used to match as the 'prompt'
        param promptmax: the maximum number prompt matches before the command is signaled 'done'
        param code: integer representing the expected return/exit code from the command
        returns
        '''
        out = self.connection.cmd(cmd,
                                  get_pty=True,
                                  invoke_shell=True,
                                  timeout=timeout,
                                  listformat=listformat,
                                  cb=self._raw_cb,
                                  cbargs=[0,promptstring, promptmax,debug])
        output = out['output']
        if code is not None:
            if out['status'] != -1 and out['status'] != code:
                self.debug(output)
                raise CommandExitCodeException('Cmd:' + str(cmd) + ' failed with status code:'
                                               + str(out['status']) + ", output:" + str(output))
        return output

    def _get_volume_basic_info_by_id(self, volumeid):
        cmd = 'volume show ' + str(self._format_volume_id(volumeid))
        return self.get_cmd_dict(cmd, code=0)

    def get_efficiency_policy(self, policy_name):
        pdict = self.get_cmd_dict('volume efficiency policy show ' + str(policy_name))
        if 'efficiency_policy_name' in pdict:
            if pdict['efficiency_policy_name'] == policy_name:
                return pdict
        return None

    #def create_efficiency_policy(self, policy_name, schedule_name, duraction_hours, enabled=True, comment='eutester_created' ):

    def discover_cli_menu(self):
        '''
        Attempts to traverse and discover the CLI menu creating executable python methods and help strings for the
        items found in each menu context. CLI menu items will be available from self.cli
        '''
        self.cli = netapp_menu("", self, help_string='Parent dir for netapp commands', scan_all=True)


    def _get_volume_efficiency_info_by_id(self, volumeid):
        cmd = 'volume efficiency show -volume ' + str(self._format_volume_id(volumeid))
        return self.get_cmd_dict(cmd)


    def get_cmd_dict(self, cmd, code=0):
        '''
        Execute a command via the client and attempt to parse the results into a returned dict
        param cmd: string representing the command to be run on the san client
        returns dict
        '''
        info = {}
        out = self.sys(cmd, code=code)
        for line in out:
            split = line.split(':')
            clean_chars = re.compile('([\W])')
            underscore_cleanup = re.compile('([_+]{2,})')
            key = split.pop(0).strip().lower()
            key = clean_chars.sub('_', key)
            key = underscore_cleanup.sub('_', key).strip('_')
            value = ":".join(str(x) for x in split)
            info[key] = str(value).strip()
        return info
