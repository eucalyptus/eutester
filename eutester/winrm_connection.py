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


from winrm.protocol import Protocol
from winrm.exceptions import WinRMTransportError
from isodate.isoduration import duration_isoformat
from datetime import timedelta
import StringIO
import traceback
import socket
import copy
import sys
import time
import re


class Winrm_Connection:

    def __init__(self,
                 hostname,
                 username,
                 password,
                 port=5985,
                 protocol='http',
                 transport='plaintext',
                 default_command_timeout=600,
                 url=None,
                 debug_method=None,
                 verbose=True):
        self.debug_method = debug_method
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = int(port)
        self.protocol = protocol
        self.transport = transport
        self.default_command_timeout = default_command_timeout #self.convert_iso8601_timeout(default_command_timeout)
        self.url = url or str(protocol)+"://"+str(hostname)+":"+str(port)+"/wsman"
        self.winproto = self.get_proto()
        self.shell_id = None
        self.command_id = None
        self.last_used = None

        self.verbose = verbose


    def get_proto(self):
        self.debug('Creating winrm connection:' + str(self.hostname) + ":" + str(self.port) + ", Username:" + str(self.username) + ', Password:' + str(self.password))
        winproto = Protocol(endpoint=self.url,transport=self.transport,username=self.username,password=self.password)
        #winproto.transport.timeout = self.default_command_timeout
        return winproto

    def convert_iso8601_timeout(self, timeout):
        #convert timeout to ISO8601 format
        return duration_isoformat(timedelta(int(timeout)))

    def debug(self, msg):
        if self.debug_method:
            self.debug_method(msg)
        else:
            print(msg)

    def reset_shell(self, timeout=None, retries=5):
        retry = 0
        tb = ""
        e = None
        self.close_shell()
        timeout = timeout or self.default_command_timeout
        self.winproto.transport.timeout = timeout #self.default_command_timeout
        #self.debug('reset_shell connection, Host:' + str(self.hostname) + ":" + str(self.port) + ", Username:" + str(self.username) + ', Password:' + str(self.password))
        while retry < retries:
            retry += 1
            try:
                self.shell_id = self.winproto.open_shell()
                return self.shell_id
            except WinRMTransportError, wte:
                print "Failed to open shell on attempt#:" + str(retry) + "/" + str(retries)+ ", err:" + str(wte)
                if retry < retries:
                    time.sleep(5)
            except Exception, e:
                tb = self.get_traceback()
                errmsg = "Error caught while reseting winrm shell:" +str(e)
                self.debug("Error caught while reseting winrm shell:" +str(e))
        self.debug(str(tb))
        raise Exception('Could not open shell to ' + str(self.url) + str(e))

    def cmd(self, command, console_mode_stdin=True, skip_cmd_shell=False, timeout=None, verbose=None):
        errmsg = ""
        if verbose is None:
            verbose = self.verbose
        orig_cmd = copy.copy(command)
        arguments = command.split(' ')
        command = arguments.pop(0)
        self.command_id = None

        #if timeout is not None:
            #convert timeout to ISO8601 format
            #timeout = self.convert_iso8601_timeout(timeout)
        self.reset_shell(timeout=timeout)
        try:
            self.command_id= self.winproto.run_command(self.shell_id,
                                      command,
                                      arguments=arguments,
                                      console_mode_stdin=console_mode_stdin,
                                      skip_cmd_shell=skip_cmd_shell)
            self.debug('winrm timeout:' + str(timeout) + ', cmd:' + str(orig_cmd))
            if timeout is not None:
                sockdefault = socket.getdefaulttimeout()
                socket.setdefaulttimeout(timeout)
                stdout, stderr, statuscode = self.get_timed_command_output(self.shell_id, self.command_id, active_timeout=timeout)
            else:
                stdout, stderr, statuscode = self.winproto.get_command_output(self.shell_id, self.command_id)
            self.debug( 'Command:"' + str(orig_cmd) + '" , Done.')
        except WinRMTransportError as wte:
            errmsg = str(wte)
        except CommandTimeoutException as cte:
            self.debug(str(cte))
            errmsg = 'timed out'
        finally:
            try:
                #self.winproto.transport.timeout = self.default_command_timeout
                if timeout is not None:
                    socket.setdefaulttimeout(sockdefault)
                self.winproto.cleanup_command(self.shell_id, self.command_id)
            except: pass
            self.close_shell()
        if errmsg:
            if re.search('timed out', errmsg, re.IGNORECASE):
                raise CommandTimeoutException('ERROR: Timed out after:' +
                                              str(self.winproto.transport.timeout) +
                                              ', Cmd:"' + str(orig_cmd))
            else:
                raise Exception(errmsg)
        if verbose:
            self.debug("\n" + str(stdout) + "\n" + str(stderr))
        return {'stdout':stdout, 'stderr':stderr, 'statuscode':statuscode}



    def get_timed_command_output(self, shell_id, command_id, active_timeout=0):
        """
        Get the Output of the given shell and command
        @param string shell_id: The shell id on the remote machine.  See #open_shell
        @param string command_id: The command id on the remote machine.  See #run_command
        @param int active_timeout: Time out used during an active session. For example as the shell is actively returning
                                  data, but we want to timeout anyways. See cmd timeout for idle timeout where no
                                  data has been read.
        """
        stdout_buffer, stderr_buffer = [], []
        command_done = False
        start = time.time()
        while not command_done:
            elapsed = time.time()-start
            if active_timeout and (elapsed > active_timeout):
                raise CommandTimeoutException('Active timeout fired after:' + str(elapsed))
            stdout, stderr, return_code, command_done = \
                self.winproto._raw_get_command_output(shell_id, command_id)
            stdout_buffer.append(stdout)
            stderr_buffer.append(stderr)
        return ''.join(stdout_buffer), ''.join(stderr_buffer), return_code


    def close_shell(self):
        if self.shell_id:
            self.winproto.close_shell(self.shell_id)
        self.shell_id = None

    def sys(self, command, include_stderr=False, listformat=True, carriage_return=False, timeout=None, code=None, verbose=None):
        ret = []
        if verbose is None:
            verbose = self.verbose
        output = self.cmd(command, timeout=timeout, verbose=verbose )
        if code is not None and output['statuscode'] != code:
            raise CommandExitCodeException('Cmd:' + str(command) + ' failed with status code:'
                                               + str(output['statuscode'])
                                               + "\n, stdout:" + str(output['stdout'])
                                               + "\n, stderr:" + str(output['stderr']))
        ret = output['stdout']
        if ret:
            if not carriage_return:
                #remove the '\r' chars from the return buffer, leave '\n'
                ret = ret.replace('\r','')
            if listformat:
                ret = ret.splitlines()
            if include_stderr:
                ret = ret.extend(output['stderr'].splitlines())
        return ret

    @classmethod
    def get_traceback(cls):
        '''
        Returns a string buffer with traceback, to be used for debug/info purposes.
        '''
        try:
            out = StringIO.StringIO()
            traceback.print_exception(*sys.exc_info(),file=out)
            out.seek(0)
            buf = out.read()
        except Exception, e:
                buf = "Could not get traceback"+str(e)
        return str(buf)



class CommandExitCodeException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class CommandTimeoutException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)