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

import time, os, socket, re
import paramiko
import select

class SshCbReturn():

    def __init__(self, stop=False, statuscode=-1, settimer=0, buf=None, nextargs=[]):
        """
        Used to return data from an ssh cmd callback method that can be used to handle output as it's rx'd instead of...
        waiting for the cmd to finish and returned buffer. See SshConnection.cmd() for more info.
        The call back must return type SshCbReturn.
        :param stop: If cb returns stop==True, recv loop will end, and channel will be closed, cmd will return.
        :param settimer: if cb settimer is > 0, timer timeout will be adjusted for this time
        :param statuscode: if cb statuscode is != -1 cmd status will return with this value
        :param nextargs: if cb nextargs is set, the next time cb is called these args will be passed instead
        :param buf: if cb buf is not None, the cmd['output'] buffer will be appended with this buf
        """
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
                 proxy=None,
                 keypair= None, 
                 keypath=None, 
                 password=None, 
                 username='root',
                 enable_ipv6_dns=False,
                 timeout=60, 
                 retry=1,
                 debugmethod=None,
                 verbose=False):
        '''

        :param host: -mandatory - string, hostname or ip address to establish ssh connection to
        :param username: - optional - string, username used to establish ssh session when keypath is not provided
        :param password: - optional - string, password used to establish ssh session when keypath is not provided
        :param keypair: - optional - boto keypair object, used to attept to derive local path to ssh key if present
        :param keypath:  - optional - string, path to ssh key
        :param enable_ipv6_dns: - optional - boolean to allow ipv6 dns hostname resolution
        :param timeout: - optional - integer, tcp timeout in seconds
        :param retry: - optional - integer, # of attempts made to establish ssh session without auth failures
        :param debugmethod: - method, used to handle debug msgs
        :param verbose: - optional - boolean to flag debug output on or off
        '''
        
        self.host = host
        self.proxy = proxy
        self.keypair = keypair
        self.keypath = keypath
        self.password = password
        self.username=username
        self.enable_ipv6_dns=enable_ipv6_dns
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
            self.debug("SSH connection has hostname:" + str(self.host) + " user:" +
                        str(self.username) + " and keypath: " + str(self.keypath))
        else:
            self.debug("SSH connection has hostname:" + str(self.host) + " user:" +
                       str(self.username) + " password:" + str(self.password))
            
        if (self.keypath is not None) or ((self.username is not None) and (self.password is not None)):
            self.connection = self.get_ssh_connection(self.host,
                                                      username=self.username,
                                                      password=self.password,
                                                      keypath=self.keypath,
                                                      enable_ipv6_dns=self.enable_ipv6_dns,
                                                      timeout=self.timeout,
                                                      retry=self.retry)
        else:
            raise Exception("Need either a keypath or username+password to create ssh connection")
    
    def debug(self,msg):
        '''
        simple method for printing debug. 
        :param msg: - mandatory - string to be printed
        '''
        if (self.verbose is True):
            if (self.debugmethod is None):
                print (str(msg))
            else:
                self.debugmethod(msg)

    def ssh_sys_timeout(self,chan,start,cmd):
        '''
        callback to be scheduled during ssh cmds which have timed out. 
        :param chan: - paramiko channel to be closed
        :param start - time.time() used to calc elapsed time when this fired for debug
        :param cmd - the command ran
        '''
        chan.close()
        elapsed = time.time()-start
        raise CommandTimeoutException("SSH Command timer fired after "+str(int(elapsed))+" seconds. Cmd:'"+str(cmd)+"'")   
    
     
    def sys(self, cmd, verbose=False, timeout=120, listformat=True, code=None):
        '''
        Issue a command cmd and return output in list format

        :param cmd: - mandatory - string representing the command to be run  against the remote ssh session
        :param verbose: - optional - will default to global setting, can be set per cmd() as well here
        :param timeout: - optional - integer used to timeout the overall cmd() operation in case of remote blockingd
        :param listformat:  - optional - format output into single buffer or list of lines
        :param code: - optional - expected exitcode, will except if cmd's  exitcode does not match this value
        '''
        out = self.cmd(cmd, verbose=verbose, timeout=timeout, listformat=listformat )
        output = out['output']
        if code is not None:
            if out['status'] != code:
                self.debug(output)
                raise Exception('Cmd:' + str(cmd) + ' failed with status code:' + str(out['status']))
        return output
    
    
    def cmd(self, cmd, verbose=None, timeout=120, readtimeout=20, listformat=False, cb=None, cbargs=[]):
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
        :param cmd: - mandatory - string representing the command to be run  against the remote ssh session
        :param verbose: - optional - will default to global setting, can be set per cmd() as well here
        :param timeout: - optional - integer used to timeout the overall cmd() operation in case of remote blocking
        :param listformat: - optional - boolean, if set returns output as list of lines, else a single buffer/string
        :param cb: - optional - callback, method that can be used to handle output as it's rx'd instead of...
                        waiting for the cmd to finish and return buffer. 
                        Must accept string buffer, and return an integer to be used as cmd status. 
                        Must return type 'sshconnection.SshCbReturn'
                        If cb returns stop, recv loop will end, and channel will be closed.
                        if cb settimer is > 0, timer timeout will be adjusted for this time
                        if cb statuscode is != -1 cmd status will return with this value
                        if cb nextargs is set, the next time cb is called these args will be passed instead
        :param cbargs: - optional - list of arguments to be appended to output buffer and passed to cb

        """
        args =[]
        if verbose is None:
            verbose = self.verbose
        ret = {}
        cbfired = False
        cmd = str(cmd)
        self.lastcmd = cmd
        self.lastexitcode = SshConnection.cmd_not_executed_code
        start = time.time()
        output = []
        cbnextargs = []
        status = None
        if verbose:
            self.debug( "[" + self.username +"@" + str(self.host) + "]# " + cmd)
        try:
            tran = self.connection.get_transport()
            chan = tran.open_session()
            chan.settimeout(timeout)
            chan.get_pty()
            f = chan.makefile()
            chan.exec_command(cmd) 
            output = ""
            fd = chan.fileno()
            chan.setblocking(0)
            cmdstart = start = time.time()
            newdebug="\n"
            while True and chan.closed == 0:
                try:
                    rl, wl, xl = select.select([fd],[],[], timeout)
                except select.error:
                    break
                elapsed = int(time.time()-start)
                if elapsed >= timeout:
                    raise CommandTimeoutException("SSH Command timer fired after "+str(int(elapsed))+" seconds. Cmd:'"+str(cmd)+"'")
                time.sleep(0.05)
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
                                        start = time.time()
                                        timeout=cbreturn.settimer 
                                    if cbreturn.buf:
                                        output += cbreturn.buf
                            else:
                                #if no call back then append output to return dict and handle debug
                                output += new
                                if verbose:
                                    #Dont print line by line output if cb is used, let cb handle that 
                                    newdebug += new
                                    
                        else:
                            status = self.lastexitcode = chan.recv_exit_status()
                            chan.close()
                            break
                    if newdebug and verbose:
                        self.debug(str(newdebug))
                        newdebug = ''
                        
                
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
            ret['elapsed'] = elapsed = int(time.time()-cmdstart)
            if verbose:
                self.debug("done with exec")
        except CommandTimeoutException, cte: 
            self.lastexitcode = SshConnection.cmd_timeout_err_code
            elapsed = str(int(time.time()-start))
            self.debug("Command ("+cmd+") timeout exception after " + str(elapsed) + " seconds\nException")     
            raise cte 
        return ret
        
    def refresh_connection(self):
        if self.connection:
            self.connection.close()
        self.connection = self.get_ssh_connection(self.host,
                                                  username=self.username,
                                                  password=self.password,
                                                  keypath=self.keypath,
                                                  enable_ipv6_dns=self.enable_ipv6_dns,
                                                  timeout=self.timeout,
                                                  retry=self.retry)
        
    def get_ssh_connection(self,
                           hostname,
                           username="root",
                           password=None,
                           keypath=None,
                           enable_ipv6_dns=None,
                           port=22,
                           timeout= 60,
                           retry=1):
        '''
        Create a paramiko ssh session to hostname. Will attempt to authenticate first with a keypath if provided, 
        if the sshkey file path is not provided.  username and password will be used to authenticate. This leaves out the case
        where a password is passed as the password needed to unlock the key file. This 3rd case may need to be added but
        may mask failures in tests for key inseration when using tests who's images have baked in passwords for login access(tbd). 
        Upon success returns a paramiko sshclient with an established connection. 

        :param hostname: - mandatory - hostname or ip to establish ssh connection with
        :param username: - optional - username used to authenticate ssh session
        :param password: - optional - password used to authenticate ssh session
        :param keypath: - optional - full path to sshkey file used to authenticate ssh session
        :param timeout: - optional - tcp timeout
        :param enable_ipv6_dns: - optional - boolean to avoid ipv6 dns 'AAAA' lookups
        :param retry: - optional - amount of retry attempts to establish ssh connection for errors outside of authentication
        :param port: - optional - port to connect to, default 22
        '''
        connected = False
        iplist = []
        if ((password is None) and (keypath is None)):
            raise Exception("ssh_connect: both password and keypath were set to None")
        if enable_ipv6_dns is None:
            enable_ipv6_dns=self.enable_ipv6_dns
        self.debug("ssh_connect args:\nhostname:" + hostname
                   + "\nusername:" + username
                   + "\npassword:" + str(password)
                   + "\nkeypath:" + str(keypath)
                   + "\ntimeout:" + str(timeout)
                   + "\nretry:" + str(retry))
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        hostname = str(hostname.strip())
        if not enable_ipv6_dns:
            self.debug('IPV6 DNS lookup disabled, do IPV4 resolution and pass IP to connect()')
            get_ipv4_ip = False
            # Paramiko uses family type 'AF_UNSPEC' which does both ipv4/ipv6 lookups and can cause some DNS servers
            # to fail in their response(s). Hack to avoid ipv6 lookups...
            # Try ipv4 dns resolution of 'hostname', and pass the ip instead of a hostname to
            # Paramiko's connect to avoid the potential ipv6 'AAAA' lookup...
            try:
                ipcheck = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
                if socket.inet_aton(hostname):
                    if not ipcheck.match(hostname):
                        get_ipv4_ip = True
                self.debug(str(hostname)+", is already an ip, dont do host lookup...")
                # This is already an ip don't look it up (regex might be better here?)
            except socket.error:
                get_ipv4_ip = True
            if get_ipv4_ip:
                try:
                    #ipv4 lookup host for ssh connection...
                    addrs = socket.getaddrinfo(hostname, 22, socket.AF_INET, socket.IPPROTO_IP, socket.IPPROTO_TCP)
                    for addr in addrs:
                        iplist.append(str(addr[4][0]))
                    self.debug('Resolved hostname:'+str(hostname)+' to IP(s):'+",".join(iplist))
                except Exception, de:
                    self.debug('Error looking up DNS ip for hostname:'+str(hostname)+", err:"+str(de))
        if not iplist:
            iplist = [hostname]
        attempt = 0
        while (attempt <= retry) and not connected:
            attempt += 1
            for ip in iplist:
                try:
                    self.debug("Attempting SSH connection: "+username+"@"+hostname+", using ip: "+str(ip)+", retry:"+str(attempt) )
                    if keypath is None:
                        #self.debug("Using username:"+username+" and password:"+password)
                        ssh.connect(ip, username=username, password=password, timeout= timeout)
                        connected = True
                        break
                    else:
                        if self.verbose:
                            self.debug("Using Keypath:"+keypath)
                        ssh.connect(ip, port=port, username=username, key_filename=keypath, timeout= timeout)
                        self.debug('Connected to '+str(ip))
                        connected = True
                        break
                except paramiko.ssh_exception.SSHException, se:
                        self.debug("Failed to connect to "+hostname+", retry in 10 seconds")
                        time.sleep(10)
                        pass
            if connected:
                break
        if not connected:
            raise Exception('Failed to connect to "'+str(hostname)+'", attempts:'+str(attempt)+". IPs tried:"+",".join(iplist))
        #self.debug("Returning ssh connection to: "+ hostname)
        return ssh
    
    def close(self):     
        self.connection.close()
        
        
        
class CommandTimeoutException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__ (self):
        return repr(self.value)
    

    
    
    
    
