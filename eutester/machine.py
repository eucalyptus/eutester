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
# Author: vic.iglesias@eucalyptus.com

import eulogger
import sshconnection
from threading import Thread
import re
import os

class Machine:
    def __init__(self, 
                 hostname, 
                 distro="", 
                 distro_ver="", 
                 arch="", 
                 source="", 
                 components="", 
                 connect=True, 
                 password=None, 
                 keypath=None, 
                 username="root", 
                 timeout=120,
                 retry=2,
                 debugmethod=None, 
                 verbose = True ):
        
        self.hostname = hostname
        self.distro = distro
        self.distro_ver = distro_ver
        self.arch = arch
        self.source = source
        self.components = components
        self.connect = connect
        self.password = password
        self.keypath = keypath
        self.username = username
        self.timeout = timeout
        self.retry = retry
        self.debugmethod = debugmethod
        self.verbose = verbose
        self.log_threads = {}
        self.log_buffers = {}
        self.log_active = {}
        
        if self.debugmethod is None:
            logger = eulogger.Eulogger(identifier= str(hostname) + ":" + str(components))
            self.debugmethod = logger.log.debug
        if self.connect:
            self.ssh = sshconnection.SshConnection( hostname, 
                                                    keypath=keypath,          
                                                    password=password, 
                                                    username=username, 
                                                    timeout=timeout, 
                                                    retry=retry,
                                                    debugmethod=self.debugmethod,
                                                    verbose=True)
            self.sftp = self.ssh.connection.open_sftp()
    
    def refresh_ssh(self):
        self.ssh.refresh_connection()
        
    def debug(self,msg):
        '''
        Used to print debug, defaults to print() but over ridden by self.debugmethod if not None
        msg - mandatory -string, message to be printed
        '''
        if ( self.verbose is True ):
                self.debugmethod(msg)
                
    def refresh_connection(self):
        self.ssh.refresh_connection()

    def reboot(self, force=True):
        if force:
            try:
                self.sys("reboot -f", timeout=3)
            except Exception, e:
                pass
        else:
            try:
                self.sys("reboot", timeout=3)
            except Exception, e:
                pass
    
    def interrupt_network(self, time = 120, interface = "eth0"):
        self.sys("ifdown " + interface + " && sleep " + str(time) + " && ifup eth0",  timeout=3)
        
    def sys(self, cmd, verbose=True, timeout=120, listformat=True):
        '''
        Issues a command against the ssh connection to this instance
        Returns a list of the lines from stdout+stderr as a result of the command
        '''
        return self.cmd(cmd, verbose=verbose, timeout=timeout, listformat=listformat)['output']
    

    def cmd(self, cmd, verbose=True, timeout=120, listformat=False, cb=None, cbargs=[]):
        '''
        Issues a command against the ssh connection to this instance
        returns dict containing:
            ['cmd'] - The command which was executed
            ['output'] - The std out/err from the executed command
            ['status'] - The exit (exitcode) of the command, in the case a call back fires, this status code is unreliable.
            ['cbfired']  - Boolean to indicate whether or not the provided callback fired (ie returned False)
            ['elapsed'] - Time elapsed waiting for command loop to end. 
        cmd - mandatory - string, the command to be executed 
        verbose - optional - boolean flag to enable debug
        timeout - optional - command timeout in seconds 
        listformat -optional - specifies returned output in list of lines, or single string buffer
        cb - optional - call back function, accepting string buffer, returning true false see sshconnection for more info
        '''
        if (self.ssh is not None):
            return self.ssh.cmd(cmd, verbose=verbose, timeout=timeout, listformat=listformat, cb=cb, cbargs=cbargs)
        else:
            raise Exception("Euinstance ssh connection is None")
        
    def sys_until_found(self, cmd, regex, verbose=True, timeout=120, listformat=True):
        '''
        Run a command until output of command satisfies/finds regex or EOF is found. 
        returns dict containing:
            ['cmd'] - The command which was executed
            ['output'] - The std out/err from the executed command
            ['status'] - The exit (exitcode) of the command, in the case a call back fires, this status code is unreliable.
            ['cbfired']  - Boolean to indicate whether or not the provided callback fired (ie returned False)
            ['elapsed'] - Time elapsed waiting for command loop to end.
        cmd - mandatory - string, the command to be executed 
        regex - mandatory - regex to look for
        verbose - optional - boolean flag to enable debug
        timeout - optional - command timeout in seconds 
        listformat -optional - specifies returned output in list of lines, or single string buffer 
        '''
        return self.cmd(cmd, verbose=verbose,timeout=timeout,listformat=listformat,cb=self.str_not_found, cbargs=[regex])
        
        
    def str_not_found(self,buf,regex,search=True):
        '''
        Return True if given regex does NOT match against given string
        '''
        return not self.str_found(buf, regex=regex, search=search)
        
        
    def str_found(self, buf, regex, search=True):
        '''
        Return True if given regex matches against given string
        '''
        if search:
            found = re.search(regex,buf)
        else:
            found = re.match(regex, buf)
        if found:
            return True
        else:
            return False
        
         
    def found(self, command, regex, verbose=True):
        """ Returns a Boolean of whether the result of the command contains the regex"""
        result = self.sys(command, verbose=verbose)
        if result is None or result == []:
            return False
        for line in result:
            found = re.search(regex,line)
            if found:
                return True
        return False   
    
    def poll_log(self, log_file="/var/log/messages"):
        self.debug( "Starting to poll " + log_file )     
        self.log_channel = self.ssh.invoke_shell()
        self.log_channel.send("tail -f " + log_file + " \n")
        ### Begin polling channel for any new data
        while self.log_active[log_file]:
            ### CLOUD LOG
            rl, wl, xl = select.select([self.log_channel],[],[],0.0)
            if len(rl) > 0:
                self.log_buffers[log_file] += self.log_channel.recv(1024)
            self.sleep(1)                                             
    
    def start_log(self, log_file="/var/log/messages"):
        '''Start thread to poll logs''' 
        thread = threading.Thread(target=self.poll_log, args=(log_file))
        thread.daemon = True
        self.log_threads[log_file]= thread.start()
        self.log_active[log_file] = True
        
    def stop_log(self, log_file="/var/log/messages"):
        '''Terminate thread that is polling logs''' 
        self.log_active[log_file] = False
        
    def save_log(self, log_file, path="logs"):
        '''Save log buffer for log_file to the path to a file'''
        if not os.path.exists(path):
            os.mkdir(path)
        FILE = open( path + '/' + log_file,"w")
        FILE.writelines(self.log_buffers[log_file])
        FILE.close()
        
    def save_all_logs(self, path="logs"):
        '''Save log buffers to a file'''
        for log_file in self.log_buffers.keys():
            self.save_all_logs(log_file,path)
            
            
        
    
    def __str__(self):
        s  = "+++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
        s += "+" + "Hostname:" + self.hostname + "\n"
        s += "+" + "Distro: " + self.distro +"\n"
        s += "+" + "Distro Version: " +  self.distro_ver +"\n"
        s += "+" + "Install Type: " +  self.source +"\n"
        s += "+" + "Components: " +   str(self.components) +"\n"
        s += "+++++++++++++++++++++++++++++++++++++++++++++++++++++"
        return s