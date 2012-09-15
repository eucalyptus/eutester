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



from eutester import sshconnection 
from eutester.sshconnection import SshConnection 
from eutester.eulogger import Eulogger
import time
import re

class WindowsProxyTests():
     
    def __init__(self, 
                  proxy_hostname,  #192.168.23.9
                  proxy_username = 'Administrator',
                  proxy_password = None, 
                  proxy_keypath = None,
                  timeout = 120,
                  retry = 2, 
                  debugmethod = None,
                  verbose = True,
                  win_instance = None,
                  win_keypath = None,
                  win_password = None ):
        
        self.proxy_hostname = proxy_hostname
        self.proxy_username = proxy_username or 'Administrator'
        self.proxy_password = proxy_password
        self.proxy_keypath = proxy_keypath
        self.timeout = timeout
        self.retry = retry
        self.verbose = verbose
        self.win_instance = win_instance
        self.win_keypath = win_keypath
        self.win_password = win_password
        self.debugmethod = debugmethod
        if self.debugmethod is None:
            logger = Eulogger(identifier= 'winproxy'+ str(proxy_hostname) + ":")
            self.debugmethod = logger.log.debug
            
        #setup ssh connection to power shell proxy server
        self.ssh = SshConnection( proxy_hostname, keypath=proxy_keypath, password=proxy_password, username=proxy_username, 
                                                timeout=timeout, retry=retry,debugmethod=self.debugmethod, verbose=True)
        self.sys = self.ssh.sys
        self.cmd = self.ssh.cmd


    def debug(self,msg):
        '''
        Used to print debug, defaults to print() but over ridden by self.debugmethod if not None
        msg - mandatory -string, message to be printed
        '''
        if ( self.verbose is True ):
            if self.debugmethod:
                self.debugmethod(msg)
            else:
                print(msg)
    def reset_ssh(self):
        self.ssh.close()
        self.ssh.refresh_connection()

    
    def ps_cmd(self, 
               hostname, 
               password,
               ps1source = '. C:\eutester_profile.ps1;', 
               command=None,
               cmdprefix=None, 
               expect=None,
               listformat=False, 
               retries=1, 
               retryinterval=10, 
               cmdtimeout=30, 
               pscb = None,
               timeout=360):
        '''
        Send command over ssh connection to power shell proxy server. Proxy server then excutes Power shell command
        against 'hostname' using 'password'. Checks for ssh errors, as well as attempts to match the text 'expect' against the text returned from executing 
        the command. 
        Returns the command output in either a single string buffer or list of lines depending on 'listformat' setting. 
        hostname - mandatory - string, hostname or ip addr of instance
        password - mandatory - string, windows Administrator password derived from instance
        ps1source - optional - string, in ". <filename;" form. A prefix to source a given powershell script for cmdlets default: '. C:\eutester_profile.ps1;'
        command= optional - string, command/cmdlet to run after the login sequence. 
        cmdprefix - optional - string, command prefix to run other than default login sequence 
        expect -  optional - regex, regex to match to return success. ie: expect='SUCCESS'
        listformat - optional - boolean, indicate whether or not returned string buffer is split per lines in a list or single buffer  
        retries - optional - integer, number of times to retry this command after failure  
        retryinterval - optional - integer, number of seconds to sleep between retries after failure 
        cmdtimeout - optional - integer,  number of seconds to wait before giving up on each command retry
        pscb - optional - callback to handle per line output of command, default is: self.check_pshell_output used to fail fast on remote powershell errors
        timeout -optional - integer, number of seconds to wait before giving up on this method (sum of all retries)
        '''
        start = time.time()
        elapsed = 0
        if pscb is None:
            pscb = self.check_pshell_output
        #if no command is provided assume only the prefix is run, usually to test login. 
        if command is None:
            loginoutput=';'
            command = ""
        else:
            loginoutput=' | out-null;'
        
        if cmdprefix is None:
                #Build the power shell command to run on remote proxy...
                cmdprefix = 'powershell -command "&{'+str(ps1source)+' Eutester-New-Euca-QA -hostname ' + hostname + ' ; Eutester-Test-Euca-Login -hostname ' + hostname + ' -password ' + password + loginoutput
        cmd = cmdprefix + str(command) + '}"'
        
        #Attempt to run the command until number of retries is exceeded...
        for attempt in xrange(0,retries):
            self.debug('ps_cmd: cmd:"'+str(cmd)+'", attempt:'+str(attempt)+'/'+str(retries)+', elapsed:'+str(elapsed))
            try:
                try:
                    self.ps_status_msg('    ( Attempt:'+str(attempt)+' )')
                    #
                    output = self.ssh.cmd(cmd,
                                          listformat = listformat,
                                          timeout = cmdtimeout,
                                          cb = pscb )
                    self.debug('Command returned!!!!')
                    self.debug("\nstatus:"+str(output['status']))
                except Exception, e:
                    raise Exception('Error while attempting to execute remote ssh command to proxy, err:'+str(e))
                if output['status'] != 0:
                    raise Exception('Proxied ssh cmd:"'+str(command)+'", proxy returned error code:'+str(output['status']))
                if re.search('FullyQualifiedErrorId',output['output']):
                    raise Exception('Powershell error in output, see logs')
                if expect is not None:
                    expect = str(expect)
                    if re.search(expect,output['output']):
                        self.ps_status_msg('Command was successful')
                        return output['output']
                    else:
                        raise Exception('Could not find text:"'+ expect + '" in command output')
                
                self.ps_status_msg('Command was successful')
                return output['output']
            except Exception, ae:
                self.ps_status_msg('ps_cmd, attempt:'+str(attempt)+', failed:'+str(ae))
                time.sleep(retryinterval)
            finally:
                #Windows ssh doesn't clean up well...
                self.reset_ssh()
            elapsed =  int(time.time()-start)
            if elapsed > timeout:
                raise Exception('ps_cmd timed out after:'+str(elapsed)+'seconds, and "'+str(attempt)+'" attempts')
        raise Exception('Command failed after '+str(attempt+1)+' attempts')
    
    def ps_status_msg(self,msg):
        self.debug('-----------------------------------------------------------------------------------------')
        self.debug(msg)
        self.debug('-----------------------------------------------------------------------------------------')
    
    def check_pshell_output(self,msg):
        ret = sshconnection.SshCbReturn()
        self.debug(str(msg))
        if re.search('FullyQualifiedErrorId',msg):
            raise Exception('Powershell error found in line:'+str(msg))
            ret.stop = True
        return ret
        
    def ps_ephemeral_test(self, host=None, password=None, retries=2, retryinterval=15, cmdtimeout=15, timeout=360):
        self.debug('Running command ps_ephemeral_test...')
        host = host or self.win_instance.public_dns_name
        password = password or self.win_password
        cmd='Eutester-Test-Euca-EphemeralDisk'
        out = self.ps_cmd(host, 
                          password,
                          command=cmd, 
                          retries=retries, 
                          retryinterval=retryinterval, 
                          cmdtimeout=cmdtimeout, 
                          timeout=timeout)
        self.debug('ps_ephemeral_test passed.')
    
    
    def ps_ebs_test(self, host=None, password=None, retries=2, retryinterval=5, cmdtimeout=300, timeout=360):
        self.debug('Running command ps_ebs_test...')
        host = host or self.win_instance.public_dns_name
        password = password or self.win_password
        cmd='Eutester-Test-Euca-EBS'
        out = self.ps_cmd(host, 
                          password,
                          command=cmd, 
                          retries=retries, 
                          retryinterval=retryinterval, 
                          cmdtimeout=cmdtimeout, 
                          timeout=timeout)
        self.debug('ps_ebs_test passed.')

    def ps_get_euca_log(self,host=None, password=None, retries=2, retryinterval=5, cmdtimeout=300, timeout=360):
        self.debug('Running command ps_get_euca_log...')
        host = host or self.win_instance.public_dns_name
        password = password or self.win_password
        cmd='Get-Euca-Log'
        out = self.ps_cmd(host, 
                          password, 
                          command=cmd,
                          retries=retries, 
                          retryinterval=retryinterval, 
                          cmdtimeout=cmdtimeout, 
                          timeout=timeout)
        self.debug('ps_get_euca_log passed.')
        
    
    def ps_hostname_test(self, iname = None, host=None, password=None, retries=2, retryinterval=5, cmdtimeout=300, timeout=360):
        self.debug('Running command ps_hostname_test...')
        host = host or self.win_instance.public_dns_name
        password = password or self.win_password
        if iname is not None:
            cmd='Eutester-Test-Euca-Hostname -hostname '+str(iname)
        else:
            cmd='Eutester-Test-Euca-Hostname'
        out = self.ps_cmd(host, 
                          password,
                          command=cmd, 
                          retries=retries, 
                          retryinterval=retryinterval, 
                          cmdtimeout=cmdtimeout, 
                          timeout=timeout)
        self.debug('ps_hostname_test passed.')
    
    def ps_login_test(self,host=None, password=None, retries=2, retryinterval=5, cmdtimeout=30, timeout=360):
        self.debug('Running command ps_login_test...')
        host = host or self.win_instance.public_dns_name
        password = password or self.win_password
        cmd=None
        out = self.ps_cmd(host, 
                          password, 
                          command=cmd,
                          retries=retries, 
                          retryinterval=retryinterval, 
                          cmdtimeout=cmdtimeout, 
                          timeout=timeout)
        self.debug('ps_get_login_test passed.')
    
    
    def ps_virtio_test(self,host=None, password=None, retries=2, retryinterval=5, cmdtimeout=300, timeout=360):
        self.debug('Running command ps_virtio_test...')
        host = host or self.win_instance.public_dns_name
        password = password or self.win_password
        cmd='Eutester-Test-Euca-VirtIO'
        out = self.ps_cmd(host, 
                          password, 
                          command=cmd,
                          retries=retries, 
                          retryinterval=retryinterval, 
                          cmdtimeout=cmdtimeout, 
                          timeout=timeout)
        self.debug('ps_get_virtio_test passed.')
        
    
    def ps_xenpv_test(self,host=None, password=None, retries=2, retryinterval=5, cmdtimeout=300, timeout=360):
        self.debug('Running command ps_xenpv_test...')
        host = host or self.win_instance.public_dns_name
        password = password or self.win_password
        cmd='Eutester-Test-Euca-XenPV'
        out = self.ps_cmd(host, 
                          password, 
                          command=cmd,
                          retries=retries, 
                          retryinterval=retryinterval, 
                          cmdtimeout=cmdtimeout, 
                          timeout=timeout)
        self.debug('ps_get_xenpv_test passed.')
        
    
    
    