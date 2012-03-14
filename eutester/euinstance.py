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
import re

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
        '''
        Used to print debug, defaults to print() but over ridden by self.debugmethod if not None
        msg - mandatory -string, message to be printed
        '''
        if ( self.verbose is True ):
            if ( self.debugmethod is None):
                print(msg)
            else:
                self.debugmethod(msg)
                
    def sys(self, cmd, verbose=False, timeout=120):
        '''
        Issues a command against the ssh connection to this instance
        Returns a list of the lines from stdout+stderr as a result of the command
        cmd - mandatory - string, the command to be executed 
        verbose - optional - boolean flag to enable debug
        timeout - optional - command timeout in seconds 
        '''
        output = []
        if (self.ssh is not None):
            output = self.ssh.sys(cmd, verbose=verbose, timeout=timeout)
            return output
        else:
            raise Exception("Euinstance ssh connection is None")
    
    def found(self, command, regex):
        """ Returns a Boolean of whether the result of the command contains the regex"""
        result = self.sys(command)
        for line in result:
            found = re.search(regex,line)
            if found:
                return True
        return False 
        
    def get_dev_dir(self, match="sd\|xd" ):
        return self.sys("ls -1 /dev/ | grep '"+str(match)+"'" )
    
    def assertFilePresent(self,filepath):
        '''
        Method to check for the presence of a file at 'filepath' on the instance
        filepath - mandatory - string, the filepath to verify
        '''
        if self.sys("stat "+filepath+" &> /dev/null && echo 'good'")[0] != 'good':
            raise Exception("File:"+filepath+" not found on instance:"+self.id)
        self.debug('File '+filepath+' is present on '+self.id)
    
    def get_metadata(self, element_path):
        """Return the lines of metadata from the element path provided"""
        ### TODO= for some reason this logic wasnt working when used inside a unittest testcase
        #if re.search("managed", self.get_network_mode()):
        return self.sys("curl http://169.254.169.254/latest/meta-data/" + element_path)
        #else:
        #    return self.sys("curl http://" + self.get_clc_ip()  + ":8773/latest/meta-data/" + element_path)
    
    def write_random_data_to_vol_get_md5(self, volume, voldev, srcdev='/dev/sda', timepergig=60):
        '''
        Attempts to copy some amount of data into an attached volume, and return the md5sum of that volume
        volume - mandatory - boto volume object of the attached volume 
        voldev - mandatory - string, the device name on the instance where the volume is attached
        srcdev - optional - string, the file to copy into the volume
        timepergig - optional - the time in seconds per gig, used to estimate an adequate timeout period
        '''
        timeout = volume.size * timepergig
        self.assertFilePresent(voldev)
        self.assertFilePresent(srcdev)
        self.sys("dd if="+srcdev+" of="+voldev+" && sync")
        md5 = self.sys("md5sum "+voldev, timeout=timeout)[0]
        md5 = md5.split(' ')[0]
        self.debug("Filled Volume:"+volume.id+" dev:"+voldev+" md5:"+md5)
        return md5
        
    
    
    
    
    
                