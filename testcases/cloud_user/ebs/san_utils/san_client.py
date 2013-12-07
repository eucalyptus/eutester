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
from eutester.sshconnection import SshConnection
from eutester.eulogger import Eulogger
import re
import copy




class San_Client():

    def __init__(self, host, username, password):
            self.host = host
            self.username = username
            self.password = password
            self.connection = self.connect()
            self.logger = Eulogger(identifier= 'SAN-'+str(host))
            self.debug= self.logger.log.debug

    @classmethod
    def get_san_client_by_type(cls, host, username, password, santype):
        if santype == 'netapp':
            return Netapp_Client(host, username, password)
        else:
            raise Exception('Unknown santype provided:' + str(santype))

    def connect(self):
        raise Exception('Not Implemented')

    def sys(self, cmd, timeout=60, code=0):
        raise Exception('Not Implemented')

    def get_san_volume_info_by_id(self, volumeid):
        raise Exception('Not Implemented')



class netapp_menu():
    def __init__(self, path_string,  san_client, help_string = "", dir_list_raw=None):
        self._path_string = path_string
        self._helpstring = help_string
        self.__doc__ = self._helpstring
        self._san_client = san_client
        self._dir_list_raw = dir_list_raw or self._get_dir_list_raw()
        self._parse_dir_list()

    def _get_dir_list_raw(self, listformat=True):
        return self._san_client.sys(self._path_string + " ?", listformat=listformat)

    def print_help(self):
        return self._san_client.debug("\n"+ self._get_dir_list_raw(listformat=False))

    def _exec_sys(self, cmd, verbose=True):
        if verbose:
            self._san_client.debug(str(cmd))
        return self._san_client.sys(cmd)

    def _get_new_command(self, path, docstring =""):
        def new_command(value='', runmethod=self._exec_sys):
            return runmethod(path + ' ' + value)
        new_command.__doc__ = docstring
        return new_command


    def _parse_dir_list(self):
        self._san_client.debug('Populating CLI dir:' + self._path_string)
        last_obj = None
        for line in self._dir_list_raw:
            split = line.split()
            if split:
                keyname = split.pop(0)
                if re.search(',',keyname):
                    if last_obj:
                        last_obj.__doc__ += keyname + " ".join(str(x) for x in split)
                elif re.search('>', keyname):
                    keyname = keyname.replace('>','')
                    dir = netapp_menu(self._path_string + " " + keyname, self._san_client)
                    dir.__doc__ = " ".join(str(x) for x in split)
                    setattr(self, keyname, dir)
                    last_obj = dir
                else:
                    newpath = str(self._path_string) + " " + str(keyname)
                    docstring = "Command:" + str(newpath) + ". " + " ".join(str(x) for x in split)
                    self._san_client.debug('Creating new method:' + str(self._path_string) + "." + str(keyname))
                    command = self._get_new_command(newpath, docstring=docstring)

                    setattr(self, keyname, command)
                    #setattr(self, keyname, lambda input = '': self._exec_sys(str(copy.copy(newpath)) + " " + input, verbose=True))
                    last_obj = command


class Netapp_Client(San_Client):


    def connect(self):
        ssh = SshConnection(host=self.host, username=self.username, password=self.password)
        self.sys = ssh.sys

    def get_san_volume_info_by_id(self, volumeid):

        info_dict = self.get_volume_basic_info_by_id(volumeid)
        eff_dict = self.get_volume_efficiency_info_by_id(volumeid)
        san_info_obj = San_Volume_Info( volumeid, dict(info_dict.items() + eff_dict.items()), self)
        return san_info_obj

    def format_volume_id(self,volumeid):
        id = str(volumeid).replace('-','_')
        return id


    def get_volume_basic_info_by_id(self, volumeid):
        cmd = 'volume show ' + str(self.format_volume_id(volumeid))
        return self.get_cmd_dict(cmd)

    def get_efficiency_policy(self, policy_name):
        pdict = self.get_cmd_dict('volume efficiency policy show ' + str(policy_name))
        if 'efficiency_policy_name' in pdict:
            if pdict['efficiency_policy_name'] == policy_name:
                return pdict
        return None

    #def create_efficiency_policy(self, policy_name, schedule_name, duraction_hours, enabled=True, comment='eutester_created' ):

    def discover_cli_menu(self):
        self.cli = netapp_menu("", self, help_string='Parent dir for netapp commands')


    def get_volume_efficiency_info_by_id(self, volumeid):
        cmd = 'volume efficiency show -volume ' + str(self.format_volume_id(volumeid))
        return self.get_cmd_dict(cmd)


    def get_cmd_dict(self, cmd):
        info = {}
        out = self.sys(cmd)
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
