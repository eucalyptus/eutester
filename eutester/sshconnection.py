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
# Author: matt.clark@eucalyptus.com
'''
Created on Mar 7, 2012
@author: clarkmatthew

simple class to establish an ssh session
example usage:
    import sshconnection
    ssh = SshConnection( '192.168.1.1', keypath='/home/testuser/keyfile.pem')
    
    #use sys() to get either a list of output lines or a single string buffer depending on listformat flag
    output = ssh.sys('ls /dev/sd*',timeout=10)
    print output[0]
    print ssh.lastcmd+" exited with code: "+str(ssh.lastexitcode)
    
    #...or use cmd to get a dict of output, exitstatus, and elapsed time to execute...
    out = ssh.cmd('ping 192.168.1.2 -c 1 -W 5')
   
     print out['cmd']+" exited with status:"+out['status']+", elapsed time:"+out['elapsed']
     print out['output']
'''

import time, os, sys
import paramiko
from threading import Timer
from boto.ec2 import keypair
import select

class SshCbReturn():
    '''
    Used to return data from an ssh cmd callback method that can be used to handle output as it's rx'd instead of...  
    waiting for the cmd to finish and returned buffer. See SshConnection.cmd() for more info.
    The call back must return type SshCbReturn.   
        If cb returns stop==True, recv loop will end, and channel will be closed, cmd will return. 
        if cb settimer is > 0, timer timeout will be adjusted for this time
        if cb statuscode is != -1 cmd status will return with this value
        if cb nextargs is set, the next time cb is called these args will be passed instead
        if cb buf is not None, the cmd['output'] buffer will be appended with this buf
    '''
    def __init__(self, stop=False, statuscode=-1, settimer=0, buf=None,nextargs=[]):
        self.stop = stop
        self.statuscode = statuscode
        self.settimer = settimer
        self.nextargs = nextargs
        self.buf = buf

class SshConnection():
    cmd_timeout_err_code = -100
    cmd_not_executed_code = -99
    
    def __init__(self, 
                 host, 
                 keypair= None, 
                 keypath=None, 
                 password=None, 
                 username='root', 
                 timeout=60, 
                 retry=1,
                 debugmethod=None,
                 verbose=False):
        '''
        host -mandatory - string, hostname or ip address to establish ssh connection to
        username - optional - string, username used to establish ssh session when keypath is not provided
        password - optional - string, password used to establish ssh session when keypath is not provided
        keypair - optional - boto keypair object, used to attept to derive local path to ssh key if present
        keypath  - optional - string, path to ssh key
        timeout - optional - integer, tcp timeout in seconds
        retry - optional - integer, # of attempts made to establish ssh session without auth failures
        debugmethod - method, used to handle debug msgs
        verbose - optional - boolean to flag debug output on or off
        '''
        
        self.host = host
        self.keypair = keypair
        self.keypath = keypath
        self.password = password
        self.username=username
        self.timeout = timeout
        self.retry = retry
        self.debugmethod = debugmethod
        self.verbose = verbose
        
        #Used to store the last cmd attempted and it's exit code
        self.lastcmd  = ""
        self.lastexitcode = SshConnection.cmd_not_executed_code
        
        
        
        if (self.keypair is not None):
            self.keypath = os.getcwd() + "/" + self.keypair.name + ".pem" 
        if (self.keypath is not None):
            self.debug( "SSH connection has hostname:"+ str(self.host) +" user:"+ str(self.username) +" and keypath: "+ str(self.keypath) )
        else:
            self.debug( "SSH connection has hostname:"+ str(self.host)+" user:"+ str(self.username) +" password:"+ str(self.password))
            
        if (self.keypath is not None) or ((self.username is not None) and (self.password is not None)):
            self.connection = self.get_ssh_connection(self.host, username=self.username, password=self.password, keypath=self.keypath, timeout=self.timeout)
        else:
            raise Exception("Need either a keypath or username+password to create ssh connection")
    
    def debug(self,msg):
        '''
        simple method for printing debug. 
        msg - mandatory - string to be printed
        method - optional - callback to over ride default printing method 
        '''
        if (self.verbose is True):
            if (self.debugmethod is None):
                print (str(msg))
            else:
                self.debugmethod(msg)

    def ssh_sys_timeout(self,chan,start,cmd):
        '''
        callback to be scheduled during ssh cmds which have timed out. 
        chan - paramiko channel to be closed 
        start - time.time() used to calc elapsed time when this fired for debug
        '''
        chan.close()
        elapsed = time.time()-start
        raise CommandTimeoutException("SSH Command timer fired after "+str(int(elapsed))+" seconds. Cmd:'"+str(cmd)+"'")   
    
     
    def sys(self, cmd, verbose=None, timeout=120, listformat=True, code=None):
        '''
        Issue a command cmd and return output in list format
        cmd - mandatory - string representing the command to be run  against the remote ssh session
        verbose - optional - will default to global setting, can be set per cmd() as well here
        timeout - optional - integer used to timeout the overall cmd() operation in case of remote blockingd
        '''
        out = self.cmd(cmd, verbose=verbose, timeout=timeout, listformat=listformat )
        output = out['output']
        if code is not None:
            if out['status'] != code:
                self.debug(output)
                raise Exception('Cmd:'+str(cmd)+' failed with status code:'+str(out['status']))
        return output
    
    
    def cmd(self, cmd, verbose=None, timeout=120, readtimeout=20, listformat=False, cb=None, cbargs=[] ):
        """ 
        Runs a command 'cmd' within an ssh connection. 
        Upon success returns dict representing outcome of the command.
        Returns dict:
            ['cmd'] - The command which was executed
            ['output'] - The std out/err from the executed command
            ['status'] - The exit (exitcode) of the command, in the case a call back fires, this status code is unreliable.
            ['cbfired']  - Boolean to indicate whether or not the provided callback fired (ie returned False)
            ['elapsed'] - Time elapsed waiting for command loop to end. 
        Arguments:
        cmd - mandatory - string representing the command to be run  against the remote ssh session
        verbose - optional - will default to global setting, can be set per cmd() as well here
        timeout - optional - integer used to timeout the overall cmd() operation in case of remote blocking
        listformat - optional - boolean, if set returns output as list of lines, else a single buffer/string
        cb - optional - callback, method that can be used to handle output as it's rx'd instead of...  
                        waiting for the cmd to finish and returned buffer. 
                        Must accept string buffer, and return an integer to be used as cmd status. 
                        Must return type 'sshconnection.SshCbReturn'
                        If cb returns stop, recv loop will end, and channel will be closed.
                        if cb settimer is > 0, timer timeout will be adjusted for this time
                        if cb statuscode is != -1 cmd status will return with this value
                        if cb nextargs is set, the next time cb is called these args will be passed instead
        cbargs - optional - list of arguments to be appended to output buffer and passed to cb
        
        
        """
        args =[]
        if verbose is None:
            verbose = self.verbose
        ret = {}
        cbfired = False
        cmd = str(cmd)
        self.lastcmd = cmd
        self.lastexitcode = SshConnection.cmd_not_executed_code
        t = None #used for timer 
        start = time.time()
        output = []
        cbnextargs = []
        status = None
        if verbose:
            self.debug( "[" + self.username +"@" + str(self.host) + "]# " + cmd)
        try:
            tran = self.connection.get_transport()
            chan = tran.open_session()
            chan.get_pty()
            f = chan.makefile()
            t = Timer(timeout, self.ssh_sys_timeout,[chan, start,cmd] )
            t.start()
            chan.exec_command(cmd) 
            output = ""
            fd = chan.fileno()
            chan.setblocking(0)
            while True and chan.closed == 0:
                time.sleep(0.05)
                try:
                    rl, wl, xl = select.select([fd],[],[],0.0)
                except select.error:
                    break
                if len(rl) > 0:
                    while chan.recv_ready():
                        new = chan.recv(1024)
                        if new is not None:
                            #We have data to handle...
                            
                            #Run call back if there is one, let call back handle data read in
                            if cb is not None:
                                #If cb returns false break, end rx loop, return cmd outcome/output dict. 
                                cbreturn = SshCbReturn()
                                cbreturn = cb(new,*cbargs)
                                #Let the callback control whether or not to continue
                                if cbreturn.stop:
                                    cbfired=True
                                    #Let the callback dictate the return code, otherwise -1 for connection err may occur
                                    if cbreturn.statuscode != -1:
                                        status = cbreturn.statuscode
                                    else:
                                        status = self.lastexitcode = chan.recv_exit_status()
                                    chan.close()
                                    break
                                else:
                                    #Let the callback update its calling args if needed
                                    cbargs = cbreturn.nextargs or cbargs
                                    #Let the callback update/reset the timeout if needed
                                    if cbreturn.settimer > 0: 
                                        t.cancel()
                                        t = Timer(cbreturn.settimer, self.ssh_sys_timeout,[chan, time.time(),cmd] )
                                        t.start()
                                    if cbreturn.buf:
                                        output += cbreturn.buf
                            else:
                                #if no call back then append output to return dict and handle debug
                                output += new
                                if verbose:
                                    #Dont print line by line output if cb is used, let cb handle that 
                                    self.debug(str(new))
                        else:
                            status = self.lastexitcode = chan.recv_exit_status()
                            chan.close()
                            t.cancel()
                            break
                
            if (listformat):
                #return output as list of lines
                output = output.splitlines()
                if output is None:
                    output = []
            #add command outcome in return dict. 
            if not status:
                status = self.lastexitcode = chan.recv_exit_status()
            ret['cmd'] = cmd
            ret['output'] = output
            ret['status'] = status
            ret['cbfired'] = cbfired
            ret['elapsed'] = elapsed = int(time.time()-start)
            if verbose:
                self.debug("done with exec")
        except CommandTimeoutException, cte: 
            self.lastexitcode = SshConnection.cmd_timeout_err_code
            elapsed = str(int(time.time()-start))
            self.debug("Command ("+cmd+") timeout exception after " + str(elapsed) + " seconds\nException")     
            raise cte
        finally:
            if (t is not None):
                t.cancel()          
        if verbose:
            if (listformat is True):
                self.debug("".join(output))
            else:
                self.debug(output)
                
        return ret
        
    def refresh_connection(self):
        self.connection = self.get_ssh_connection(self.host, self.username,self.password , self.keypath, self.timeout, self.retry)
        
    def get_ssh_connection(self, hostname, username="root", password=None, keypath=None, timeout= 60, retry=1):
        '''
        Create a paramiko ssh session to hostname. Will attempt to authenticate first with a keypath if provided, 
        if the sshkey file path is not provided.  username and password will be used to authenticate. 
        Upon success returns a paramiko sshclient with an established connection. 
        hostname - mandatory - hostname or ip to establish ssh connection with
        username - optional - username used to authenticate ssh session
        password - optional - password used to authenticate ssh session
        keypath - optional - full path to sshkey file used to authenticate ssh session
        timeout - optional - tcp timeout 
        retry - optional - amount of retry attempts to establish ssh connection for errors outside of authentication
        '''
        if ((password is None) and (keypath is None)):
            raise Exception("ssh_connect: both password and keypath were set to None")
        
        #self.debug("ssh_connect args:\nhostname:"+hostname+"\nusername:"+username+"\npassword:"+str(password)+"\nkeypath:"+str(keypath)+"\ntimeout:"+str(timeout)+"\nretry:"+str(retry))

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
        while ( retry >= 0  ):
            retry -= 1 
            try:
                #self.debug("Attempting SSH connection: "+username+"@"+hostname )            
                if keypath is None:   
                    #self.debug("Using username:"+username+" and password:"+password)
                    ssh.connect(hostname, username=username, password=password, timeout= timeout)
                else:
                    if self.verbose:
                        self.debug("Using Keypath:"+keypath)
                    ssh.connect(hostname,  username=username, key_filename=keypath, timeout= timeout)
                break
            except paramiko.ssh_exception.SSHException, se:
                if retry < 0: 
                    self.debug("Failed to connect to "+hostname+", retry in 10 seconds")
                    time.sleep(10)
                    pass
                else:
                    raise se
        #self.debug("Returning ssh connection to: "+ hostname)
        return ssh
    
    def close(self):     
        self.connection.close()
        
        
        
class CommandTimeoutException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__ (self):
        return repr(self.value)
    

    
    
    
    