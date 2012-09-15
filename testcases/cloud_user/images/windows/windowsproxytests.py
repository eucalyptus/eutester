#192.168.23.9



from eutester.sshconnection import SshConnection 
from eutester.eulogger import Eulogger
import time

class WindowsProxyTests():
     
    def __init__(self, 
                  proxy_hostname, 
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
                
    def ps_cmd(self, 
               hostname, 
               password,
               ps1source = '. C:\eutester_profile.ps1;', 
               command=None,
               cmdprefix=None, 
               expect='SUCCESS', 
               listformat=False, 
               retries=2, 
               retryinterval=10, 
               cmdtimeout=30, 
               timeout=360):
        '''
        Send command over ssh connection to power shell proxy server. Proxy server then excutes Power shell command
        against 'hostname' using 'password'. Checks for ssh errors, as well as attempts to match the text 'expect' against the text returned from executing 
        the command. 
        Returns the command output in either a single string buffer or list of lines depending on 'listformat' setting. 
        '''
        start = time.time()
        elapsed = 0
        #if no command is provided assume only the prefix is run, usually to test login. 
        if command is None:
            loginoutput=';'
            command = ""
        else:
            loginoutput=' | out-null;'
        
        if cmdprefix is None:
                #cmdprefix = 'powershell -command "&{New-Euca-QA -hostname ' + hostname + ' | out-null; Test-Euca-Login -hostname ' + hostname + ' -password ' + password + loginoutput
                cmdprefix = 'powershell -command "&{'+str(ps1source)+' Eutester-New-Euca-QA -hostname ' + hostname + ' ; Eutester-Test-Euca-Login -hostname ' + hostname + ' -password ' + password + loginoutput
        cmd = cmdprefix + str(command) + '}"'
        for attempt in xrange(0,retries):
            self.debug('ps_cmd: cmd:"'+str(cmd)+'", attempt:'+str(attempt)+'/'+str(retries)+', elapsed:'+str(elapsed))
            try:
                try:
                    output = self.ssh.cmd(cmd,listformat=listformat,timeout=cmdtimeout)
                    self.debug('Command returned!!!!')
                    self.debug("\nstatus:"+str(output['status']))
                except Exception, e:
                    raise Exception('Error while attempting to execute remote ssh command to proxy, err:'+str(e))
                if output['status'] != 0:
                    raise Exception('Proxied ssh cmd:"'+str(command)+'", proxy returned error code:'+str(output['status']))
                if expect is not None:
                    expect = str(expect)
                    if re.search(expect,output['output']):
                        self.debug('Command was successful')
                        return output['output']
                    else:
                        raise Exception('Could not find text:"'+ expect + '" in command output')
                
                self.debug('Command was successful')
                return output['output']
            except Exception, ae:
                self.debug('ps_cmd, attempt:'+str(attempt)+', failed:'+str(ae))
            elapsed =  int(time.time()-start)
            if elapsed > timeout:
                raise Exception('ps_cmd timed out after:'+str(elapsed)+'seconds, and "'+str(attempt)+'" attempts')
        raise Exception('Command failed after '+str(attempt+1)+' attempts')
        
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
        
    
    
    