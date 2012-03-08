'''
Created on Mar 7, 2012
@author: clarkmatthew
extension of the boto instance class, with added convenience methods + objects
Add common instance test routines to this class

Sample usage:
    testinstance = EuInstance.make_euinstance_from_instance( eutester.run_instances()[0] )
    print testinstance.id
    output = testinstance.sys("ls /dev/xd*") 
    print output[0]
    eutester.sys('ping '+testinstance.ip_address )
    testinstance.sys('yum install ntpd')
'''

from boto.ec2.volume import Volume
from boto.ec2.instance import Instance
import sshconnection
import os
import time


class EuInstance(Instance):
    keypair = None
    keypath = None
    attached_vols = []
    ops = None
    ssh = None
    debugmethod = None
    timeout =  60
    retry = 1

   
    @classmethod
    def make_euinstance_from_instance(cls, 
                                      instance, 
                                      keypair=None, 
                                      keypath=None, 
                                      password=None, 
                                      username="root", 
                                      debugmethod = None, 
                                      verbose=True, 
                                      timeout=60,
                                      retry=1
                                      ):
        '''
        Primary constructor for this class.
        Arguments:
        instance - mandatory- a Boto instance object used to build this euinstance object
        keypair - optional- a boto keypair object used for creating ssh connection to the instance
        password - optional- string used to create ssh connection to this instance as an alternative to keypair 
        username - optional- string used to create ssh connection as an alternative to keypair
        timeout - optional- integer used for ssh connection timeout
        debugmethod - optional - method, used for debug output 
        verbose - optional - boolean to determine if debug is to be printed using debug()
        retry - optional - integer, ssh connection attempts for non-authentication failures
        '''
        newins = EuInstance(instance.connection)
        newins.__dict__ = instance.__dict__
      
        if (keypair is not None):
            keypath = os.getcwd() + "/" + keypair.name + ".pem" 
        newins.keypair = keypair
        newins.keypath = keypath
        if ((keypath is not None) or ((username is not None)and(password is not None))):
            newins.ssh = sshconnection.SshConnection(
                                                    instance.ip_address, 
                                                    keypair=keypair, 
                                                    keypath=keypath,          
                                                    password=password, 
                                                    username=username, 
                                                    timeout=timeout, 
                                                    retry=retry,
                                                    debugmethod=debugmethod,
                                                    verbose=verbose)
    
        
        newins.attached_vols=[] 
        newins.debugmethod = debugmethod
        newins.timeout = timeout
        return newins
    
    def debug(self,msg):
        if ( self.verbose is True ):
            if ( self.debugmethod is None):
                print(msg)
            else:
                self.debugmethod(msg)
                
    def sys(self, cmd, verbose=None, timeout=120):
            if (self.ssh is not None):
                return self.ssh.cmd(cmd, verbose=verbose, timeout=timeout)
            
    def get_dev_dir(self, match="sd\|xd" ):
        return self.sys("ls -1 /dev/ | grep '"+str(match)+"'" )
    
    def assertFilePresent(self,filepath):
        if self.sys("stat "+filepath+" &> /dev/null && echo 'good'")[0] != 'good':
            raise Exception("File:"+filepath+" not found on instance:"+self.id)
        self.debug('File '+filepath+' is present on '+self.id)
    
    def write_random_data_to_vol_get_md5(self, volume, voldev, srcdev='/dev/sda', timepergig=60):
            timeout = volume.size * timepergig
            self.assertFilePresent(voldev)
            self.assertFilePresent(srcdev)
            self.sys("dd if="+srcdev+" of="+voldev+" && sync")
            md5 = self.sys("md5sum "+voldev, timeout=timeout)[0]
            md5 = md5.split(' ')[0]
            self.debug("Filled Volume:"+volume.id+" dev:"+voldev+" md5:"+md5)
            return md5
        
    
    
    
    
    
                