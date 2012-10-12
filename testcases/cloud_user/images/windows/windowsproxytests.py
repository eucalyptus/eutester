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
        '''
        Description: Help class to execute remote powershell cmdlets over an ssh connection in order to 
                    test Windows Instance functionality within the cloud.
                    
        :type proxy_host: string
        :param proxy_host: The ip address or FQDN hostname of the windows server to connect via ssh, and exectute the powershell commands on.
        
        :type proxy_username: string
        :param proxy_username: The username used for created the remote ssh session, and executing the powershell cmdlets
        
        :type proxy_password: string
        :param proxy_passwrd: The password used fro creating the remote ssh session. 
        
        :type proxy_keypath: string
        :param proxy_keypath: The path to the ssh keyfile used for establishing the ssh session to the remote powershell server. 
        
        :type timeout: integer
        :param timeout: Timeout to be used as a default for method timeouts. ie  timeout used for establising an ssh session to powershell server. 
        
        :type retry:
        :param retry: Used to define the amount of times to retry a failed method before giving up. 
        
        :type debugmethod: method
        :param debugmethod: A method which can be pass and used for self.debug
        
        :type verbose: boolean
        :param verbose: A boolean to flag on or off debug messages. 
        
        :type win_instance: instance object
        :param win_instance: instance object used as the default target for running tests against
        
        :type win_keypath: string
        :param win_keypath: A string representing the path to the keyfile used when launching the win_instance instance. 
                            This is used for building the password to win_instance if necessarry. 
                            See ec2ops for get_windows_instance_password method
        
        :type win_password: string
        :param win_password: The cloud generated password associated with win_instance. See ec2ops for get_windows_instance_password method
         
        '''
        
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
               listformat=False, 
               retries=1, 
               retryinterval=10, 
               cmdtimeout=30, 
               pscb = None,
               exitcode=0,
               timeout=360):
        '''
        Description: Issues a powershell command on a remote windows server over ssh. (ie the windows server is running cygwin, etc).
                    Send command over ssh connection to power shell proxy server. Proxy server then excutes Power shell command
                    against 'hostname' using 'password'. Checks for ssh errors, and command exit status code.  
                    the command. 
                    Returns the command output in either a single string buffer or list of lines depending on 'listformat' setting. 
                    
        :type hostname: string
        :param hostname: mandatory - string, hostname or ip addr of instance
        
        :type password: string
        :param password: mandatory - string, windows Administrator password derived from instance
        
        :type ps1source: string
        :param ps1source: optional - string, in ". <filename;" form. A prefix to source a given powershell script for cmdlets default: '. C:\eutester_profile.ps1;'
        
        :type command: string
        :param command: optional - string, command/cmdlet to run after the login sequence. 
        
        :type cmdprefix: string
        :param cmdprefix: optional - string, command prefix to run other than default login sequence 
        
        :type listformat: boolean
        :param listformat: optional - boolean, indicate whether or not returned string buffer is split per lines in a list or single buffer  
        
        :type retries: integer
        :param retries: optional - integer, number of times to retry this command after failure  
        
        :type retryinterval: integer
        :param retryinterval: optional - integer, number of seconds to sleep between retries after failure 
        
        :type cmdtimeout: integer
        :param cmdtimeout: optional - integer,  number of seconds to wait before giving up on each command retry
        
        :type exitcode: integer
        :param exitcode: optional - integer, exit code to check remote command return value against, default = 0. 
        
        :type pscb: method
        :param pscb: optional - callback to handle per line output of command, default is: self.check_pshell_output used to fail fast on remote powershell errors
        
        :type timeout: integer
        :param timeout: optional - integer, number of seconds to wait before giving up on this method (sum of all retries)
        
        :rtype: string
        :returns: The string buffer containing stdout/err of the remote powershell session. 
        '''
        start = time.time()
        elapsed = 0
        #if pscb is None:
        #    pscb = self.check_pshell_output
        #if no command is provided assume only the prefix is run, usually to test login. 
        if command is None:
            loginoutput=';'
            command = ""
        else:
            loginoutput=' | out-null;'
        
        if cmdprefix is None:
                #Build the power shell command to run on remote proxy...
                cmdprefix = 'echo "\n" | powershell -command "&{'+str(ps1source)+' Eutester-New-Euca-QA -hostname ' + hostname + ' ; Eutester-Test-Euca-Login -hostname ' + hostname + ' -password ' + password + loginoutput
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
                    raise Exception('Error while attempting to execute remote ssh command to proxy,\nError:'+str(e))
                if output['status'] != exitcode:
                    raise Exception('Proxied ssh cmd:"'+str(command)+'", proxy returned error code:'+str(output['status']))
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
        ret.buf = msg
        if re.search('FullyQualifiedErrorId',msg):
            raise Exception('Powershell error found in line:'+str(msg))
            ret.stop = True
        return ret
        
    def ps_check_powershell(self, echomsg='YES powershell is working'):
        '''
        Description: Tests basic rmote connection and powershell functionality using echo like cmdlet
                    Basic echo function to test the remote proxy's powershell status
                    
        :type echomsg: string
        :param echomsg: optional string to be echoed by remote powershell cmdlet
        
        :rtype: string
        :returns: The string buffer containing stdout/err of the remote powershell session. 
        '''
        echomsg = "'"+str(echomsg)+"'"
        cmdprefix = 'echo "\n" | powershell -command "&{. C:\eutester_profile.ps1; Eutester-echo -word '+str(echomsg)
        out = self.ps_cmd("test", 
                          "test",
                          command=None,
                          cmdprefix=cmdprefix, 
                          retries=1, 
                          retryinterval=5, 
                          cmdtimeout=10, 
                          timeout=20)
        return out
            
    
    def ps_ephemeral_test(self, host=None, password=None, retries=2, retryinterval=15, cmdtimeout=15, timeout=360):
        '''
        Description: ps_phemeral_test  Intends to verify the ephemeral storage on a windows instance by executing 
                     remote powershell cmdlets against a running instance. 
        
        :type host: string
        :param host: The FQDN or IP address of the windows instance to perform remote powershell scripts against
        
        :type password: string
        :param password: The 'Administrator' password for the remote windows instance. 
        
        :type retries: integer
        :param retries: The number of times to retry the powershell cmdlet upon failure
        
        :type retryinterval: integer
        :param retryinterval: The number of seconds to wait between retrying a failed powershell cmdlet

        :type cmdtimeout: integer
        :param cmdtimeout: The number of seconds to wait for the remote ssh session to return when executing the remote cmdlet. 
        
        :rtype: string
        :returns: The string buffer containing stdout/err of the remote powershell session. 
        '''
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
        return out
    
    
    def ps_ebs_test(self, host=None, password=None, retries=2, retryinterval=5, cmdtimeout=300, timeout=360):
        '''
        Description: Attempts to validate the attached EBS volume state and format on the remote windows guest.
        
        :type host: string
        :param host: The FQDN or IP address of the windows instance to perform remote powershell scripts against
        
        :type password: string
        :param password: The 'Administrator' password for the remote windows instance. 
        
        :type retries: integer
        :param retries: The number of times to retry the powershell cmdlet upon failure
        
        :type retryinterval: integer
        :param retryinterval: The number of seconds to wait between retrying a failed powershell cmdlet

        :type cmdtimeout: integer
        :param cmdtimeout: The number of seconds to wait for the remote ssh session to return when executing the remote cmdlet. 
        
        :rtype: string
        :returns: The string buffer containing stdout/err of the remote powershell session. 
        '''
        self.debug('Running command ps_ebs_test...')
        self.debug("Warning, ebs_test may not work on a 32bit guest...")
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
        return out

    def ps_get_euca_log(self,host=None, password=None, retries=2, retryinterval=5, cmdtimeout=300, timeout=360):
        '''
        Description: Execute powershell command to get related Eucalyptus test logs
        
        :type host: string
        :param host: The FQDN or IP address of the windows instance to perform remote powershell scripts against
        
        :type password: string
        :param password: The 'Administrator' password for the remote windows instance. 
        
        :type retries: integer
        :param retries: The number of times to retry the powershell cmdlet upon failure
        
        :type retryinterval: integer
        :param retryinterval: The number of seconds to wait between retrying a failed powershell cmdlet

        :type cmdtimeout: integer
        :param cmdtimeout: The number of seconds to wait for the remote ssh session to return when executing the remote cmdlet. 
        
        :rtype: string
        :returns: The string buffer containing stdout/err of the remote powershell session. 
        '''
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
        return out
        
    
    def ps_hostname_test(self, iname = None, host=None, password=None, retries=2, retryinterval=5, cmdtimeout=300, timeout=360):
        '''
        Description: Verify that a hostname on the Windows instance has been set via eucalyptus
        
        :type host: string
        :param host: The FQDN or IP address of the windows instance to perform remote powershell scripts against
        
        :type password: string
        :param password: The 'Administrator' password for the remote windows instance. 
        
        :type retries: integer
        :param retries: The number of times to retry the powershell cmdlet upon failure
        
        :type retryinterval: integer
        :param retryinterval: The number of seconds to wait between retrying a failed powershell cmdlet

        :type cmdtimeout: integer
        :param cmdtimeout: The number of seconds to wait for the remote ssh session to return when executing the remote cmdlet. 
        
        :rtype: string
        :returns: The string buffer containing stdout/err of the remote powershell session. 
        '''
        self.debug('Running command ps_hostname_test...')
        host = host or self.win_instance.public_dns_name
        password = password or self.win_password
        iname = iname or self.win_instance.id
        if iname is not None:
            cmd='Eutester-Test-Euca-Hostname -hostname '+str(iname)
        
        out = self.ps_cmd(host, 
                          password,
                          command=cmd, 
                          retries=retries, 
                          retryinterval=retryinterval, 
                          cmdtimeout=cmdtimeout, 
                          timeout=timeout)
        self.debug('ps_hostname_test passed.')
        return out
    
    def ps_login_test(self,host=None, password=None, retries=2, retryinterval=5, cmdtimeout=30, timeout=360):
        '''
        Description: Verify that the windows instance can be logged into using user Administrator and 
                    the Cloud generated password
        
        :type host: string
        :param host: The FQDN or IP address of the windows instance to perform remote powershell scripts against
        
        :type password: string
        :param password: The 'Administrator' password for the remote windows instance. 
        
        :type retries: integer
        :param retries: The number of times to retry the powershell cmdlet upon failure
        
        :type retryinterval: integer
        :param retryinterval: The number of seconds to wait between retrying a failed powershell cmdlet

        :type cmdtimeout: integer
        :param cmdtimeout: The number of seconds to wait for the remote ssh session to return when executing the remote cmdlet. 
        
        :rtype: string
        :returns: The string buffer containing stdout/err of the remote powershell session. 
        '''
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
        return out
    
    
    def ps_virtio_test(self,host=None, password=None, retries=2, retryinterval=5, cmdtimeout=300, timeout=360):
        '''
        Description: Run Powershell Virtio Test on remote Windows instance
        
        :type host: string
        :param host: The FQDN or IP address of the windows instance to perform remote powershell scripts against
        
        :type password: string
        :param password: The 'Administrator' password for the remote windows instance. 
        
        :type retries: integer
        :param retries: The number of times to retry the powershell cmdlet upon failure
        
        :type retryinterval: integer
        :param retryinterval: The number of seconds to wait between retrying a failed powershell cmdlet

        :type cmdtimeout: integer
        :param cmdtimeout: The number of seconds to wait for the remote ssh session to return when executing the remote cmdlet. 
        
        :rtype: string
        :returns: The string buffer containing stdout/err of the remote powershell session. 
        '''
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
        return out
        
    
    def ps_xenpv_test(self,host=None, password=None, retries=2, retryinterval=5, cmdtimeout=300, timeout=360):
        '''
        Description:Run Xen powershell test on remote Windows instance 
        
        :type host: string
        :param host: The FQDN or IP address of the windows instance to perform remote powershell scripts against
        
        :type password: string
        :param password: The 'Administrator' password for the remote windows instance. 
        
        :type retries: integer
        :param retries: The number of times to retry the powershell cmdlet upon failure
        
        :type retryinterval: integer
        :param retryinterval: The number of seconds to wait between retrying a failed powershell cmdlet

        :type cmdtimeout: integer
        :param cmdtimeout: The number of seconds to wait for the remote ssh session to return when executing the remote cmdlet. 
        
        :rtype: string
        :returns: The string buffer containing stdout/err of the remote powershell session. 
        '''
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
        return out
        
    
    
    