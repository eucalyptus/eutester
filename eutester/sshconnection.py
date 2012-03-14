'''
Created on Mar 7, 2012
@author: clarkmatthew

simple class to establish an ssh session
example usage:
    import sshconnection
    ssh = SshConnection( '192.168.1.1', keypath='/home/testuser/keyfile.pem')
    list = ssh.cmd('ls /dev/sd*',timeout=10)
    print list[0]
'''

import time, os
import paramiko
from threading import Timer
from boto.ec2 import keypair


class SshConnection():
    host = None
    username = None
    password = None
    keypair = None
    keypath = None
    connection = None
    debugmethod = None
    timeout = 60
    retry = 1
    verbose = False
    
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
        
        
        if (self.keypair is not None):
            self.keypath = os.getcwd() + "/" + self.keypair.name + ".pem" 
        if (self.keypath is not None):
            print ( "hostname:"+self.host+"\nkeypath:"+self.keypath)
        else:
            print ( "hostname:"+self.host+"\nuser:"+self.username+"\npassword:"+self.password)
            
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
    
    def ssh_sys_timeout(self,chan,start):
        '''
        callback to be scheduled during ssh cmds which have timed out. 
        chan - paramiko channel to be closed 
        start - time.time() used to calc elapsed time when this fired for debug
        '''
        chan.close()
        elapsed = time.time()-start
        raise CommandTimeoutException("SSH Command timer has fired after scheduled "+str(elapsed).split('.')[0]+" seconds")   
    
     
    def sys(self, cmd, verbose=None, timeout=120):
        '''
        Issue a command cmd and return output in list format
        cmd - mandatory - string representing the command to be run  against the remote ssh session
        verbose - optional - will default to global setting, can be set per cmd() as well here
        timeout - optional - integer used to timeout the overall cmd() operation in case of remote blockingd
        '''
        return self.cmd(cmd, verbose=verbose, timeout=timeout, listformat=True)
    
    
    def cmd(self, cmd, verbose=None, timeout=120, listformat=False):
        """ 
        Runs a command 'cmd' within an ssh connection. 
        Upon success returns a list of lines from the output of the command.
        cmd - mandatory - string representing the command to be run  against the remote ssh session
        verbose - optional - will default to global setting, can be set per cmd() as well here
        timeout - optional - integer used to timeout the overall cmd() operation in case of remote blocking
        listformat - optional - boolean, if set returns output as list of lines, else a single buffer/string
        """
            
        if verbose is None:
            verbose = self.verbose
            
        cmd = str(cmd)
        t = None #used for timer 
        start = time.time()
        output = []
        if verbose:
            self.debug( "[root@" + str(self.host) + "]# " + cmd)
        try:
            tran = self.connection.get_transport()
            chan = tran.open_session()
            chan.get_pty()
            f = chan.makefile()
            t = Timer(timeout, self.ssh_sys_timeout,[chan, start] )
            t.start()
            chan.exec_command(cmd)
            if ( listformat is True):
                #return output as list of lines
                output = f.readlines()
            else:
                #return output as single string buffer
                output = f.read()
            self.debug("done with exec")
        except CommandTimeoutException, cte: 
            elapsed = str(time.time()-start).split('.')[0]
            self.debug("Command ("+cmd+") timed out after " + str(elapsed) + " seconds\nException")     
            raise cte
        finally:
            if (t is not None):
                t.cancel()          
        if verbose:
            elapsed = str(time.time()-start).split('.')[0]
            if (listformat is True):
                self.debug("stdout after "+elapsed+" seconds, cmd=("+cmd+"):\n"+"".join(output))
            else:
                self.debug("stdout after "+elapsed+" seconds, cmd=("+cmd+"):\n"+output)
                
        return output
        
        
    
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
        
        self.debug("ssh_connect args:\nhostname:"+hostname+"\nusername:"+username+"\npassword:"+str(password)+"\nkeypath:"+str(keypath)+"\ntimeout:"+str(timeout)+"\nretry:"+str(retry))

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
        while ( retry >= 0  ):
            retry -= 1 
            try:
                self.debug("Attempting SSH connection: "+username+"@"+hostname )            
                if keypath is None:   
                    self.debug("Using username:"+username+" and password:"+password)
                    ssh.connect(hostname, username="root", password=password, timeout= timeout)
                else:
                    self.debug("Using Keypath:"+keypath)
                    ssh.connect(hostname,  username="root", key_filename=keypath, timeout= timeout)
                break
            except paramiko.ssh_exception.SSHException, se:
                if retry < 0: 
                    self.debug("Failed to connect to "+hostname+", retry in 10 seconds")
                    time.sleep(10)
                    pass
                else:
                    raise se
        self.debug("Returning ssh connection to: "+ hostname)
        return ssh
    
    def close(self):     
        self.connection.close()
        
        
        
class CommandTimeoutException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__ (self):
        return repr(self.value)
    
    
    
    