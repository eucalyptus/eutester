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
#from eutester import euvolume
from eutester.euvolume import EuVolume
from eutester import eulogger

import sshconnection
import os
import re
import time
import re
import eulogger


class EuInstance(Instance):
    keypair = None
    keypath = None
    username = None
    password = None
    attached_vols = []
    scsidevs = []
    ops = None
    ssh = None
    logger = None
    debugmethod = None
    timeout =  60
    retry = 1
    verbose=True
    ssh = None
    tester = None


   
    @classmethod
    def make_euinstance_from_instance(cls, 
                                      instance, 
                                      tester,
                                      debugmethod = None, 
                                      keypair=None, 
                                      keypath=None, 
                                      password=None, 
                                      username="root",  
                                      verbose=True, 
                                      timeout=60,
                                      retry=2
                                      ):
        '''
        Primary constructor for this class. Note: to avoid an ssh session within this method, provide keys, username/pass later.
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
        newins.tester = tester
        
        newins.debugmethod = debugmethod
        if newins.debugmethod is None:
            newins.logger = eulogger.Eulogger(identifier= str(instance.id) + "-" + str(instance.ip_address))
            newins.debugmethod= newins.logger.log.debug
            
        if (keypair is not None):
            keypath = os.getcwd() + "/" + keypair.name + ".pem" 
        newins.keypair = keypair
        newins.keypath = keypath
        newins.password = password
        newins.username = username
        newins.verbose = verbose
        newins.attached_vols=[] 
        newins.timeout = timeout
        newins.retry = retry    
        newins.connect_to_instance(timeout=timeout) 
        return newins
    
    def reset_ssh_connection(self):
        if ((self.keypath is not None) or ((self.username is not None)and(self.password is not None))):
            if self.ssh is not None:
                self.ssh.close()
            self.ssh = sshconnection.SshConnection(
                                                    self.public_dns_name, 
                                                    keypair=self.keypair, 
                                                    keypath=self.keypath,          
                                                    password=self.password, 
                                                    username=self.username, 
                                                    timeout=self.timeout, 
                                                    retry=self.retry,
                                                    debugmethod=self.debugmethod,
                                                    verbose=self.verbose)
        else:
            self.debug("keypath or username/password need to be populated for ssh connection") 
            
    
    def connect_to_instance(self, timeout=60):
        self.debug("Attempting to reconnect_to_instance:"+self.id)
        if ((self.keypath is not None) or ((self.username is not None)and(self.password is not None))):
            start = time.time()
            elapsed = 0
            if self.ssh is not None:
                self.ssh.close()
            self.ssh = None
            while (elapsed < timeout):
                try:
                    self.reset_ssh_connection()
                except Exception, se:
                    self.debug('Caught exception attempting to reconnect ssh'+ str(se))
                    elapsed = int(time.time()-start)
                    self.debug('retrying ssh connection, elapsed:'+str(elapsed))
                    time.sleep(5)
                    pass
                else:
                    break
            if self.ssh is None:
                raise Exception(str(self.id)+":Failed establishing ssh connection in reconnect")
        else:
            self.debug("keypath or username/password need to be populated for ssh connection") 
    
    def debug(self,msg):
        '''
        Used to print debug, defaults to print() but over ridden by self.debugmethod if not None
        msg - mandatory -string, message to be printed
        '''
        if ( self.verbose is True ):
                self.debugmethod(msg)

                
    def sys(self, cmd, verbose=True, timeout=120):
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
        
    def get_dev_dir(self, match="sd\|vd\|xd" ):
        return self.sys("ls -1 /dev/ | grep '"+str(match)+"'" )
    
    def assertFilePresent(self,filepath):
        '''
        Method to check for the presence of a file at 'filepath' on the instance
        filepath - mandatory - string, the filepath to verify
        '''
        if not self.found("stat "+filepath+" &> /dev/null && echo 'good'", 'good'):
            raise Exception("File:"+filepath+" not found on instance:"+self.id)
            return False
        self.debug('File '+filepath+' is present on '+self.id)
        
    
    def attach_volume(self, volume, tester, dev=None, timeout=60):
        if not isinstance(volume, EuVolume):
            euvolume = EuVolume.make_euvol_from_vol(volume)
        return self.attach_euvolume(euvolume, tester=tester, dev=dev, timeout=timeout)
    
        
    def attach_euvolume(self, euvolume, dev=None, timeout=60):
        '''
        Method used to attach a volume to an instance and track it's use by that instance
        required - euvolume - the euvolume object being attached
        required - tester - the eucaops/eutester object/connection for this cloud
        optional - dev - string to specify the dev path to 'request' when attaching the volume to
        ''' 
        if not isinstance(euvolume, EuVolume):
            raise Exception("Volume needs to be of type euvolume, try attach_volume() instead?")
        
        self.debug("Attempting to attach volume:"+str(euvolume.id)+" to instance:" +str(self.id)+" to dev:"+ str(dev))
        dev_list_before = self.get_dev_dir()
        #self.debug("list before\n"+"".join(dev_list_before))
        dev_list_after = []
        attached_dev = None
        start= time.time()
        elapsed = 0
        if dev is None:
            dev = self.get_free_scsi_dev()
        if (self.tester.attach_volume(self, euvolume, dev,pause=10)):     
            while (elapsed < timeout):
                self.debug("Checking for volume attachment on guest, elapsed time("+str(elapsed)+")")
                dev_list_after = self.get_dev_dir()
                diff =list( set(dev_list_after) - set(dev_list_before) )
                if len(diff) > 0:
                    attached_dev = diff[0]
                    euvolume.guestdev = attached_dev
                    euvolume.clouddev = dev
                    self.attached_vols.append(euvolume)
                    self.debug(euvolume.id+" Requested dev:"+str(euvolume.clouddev)+", attached to guest device:"+str(euvolume.guestdev))
                    break
                elapsed = int(time.time() - start)
                time.sleep(2)
        else:
            self.debug('Failed to attach volume:'+str(euvolume.id)+' to instance:'+self.id)
        if (attached_dev is None):
            self.debug("List after\n"+"".join(dev_list_after))
            raise Exception('Volume:'+str(euvolume.id)+' attached, but not found on guest'+str(self.id)+' after '+str(elapsed)+' seconds?')
        self.debug('Success attaching volume:'+str(euvolume.id)+' to instance:'+self.id+' attached dev:'+str(attached_dev))
        return attached_dev
    
    def detach_euvolume(self, euvolume, timeout=60):
        '''
        Method used to detach detach a volume to an instance and track it's use by that instance
        required - euvolume - the euvolume object being deattached
        optional - timeout - integer seconds to wait before timing out waiting for the volume to detach 
        '''
        start = time.time()
        elapsed = 0 
        for vol in self.attached_vols:
            if vol.id == euvolume.id:
                dev = vol.guestdev
                if (self.tester.detach_volume(euvolume)):
                    while (elapsed < timeout):
                        if (self.sys('ls -1'+dev, timeout=timeout) == []):
                            self.attached_vols.remove(vol)
                            return
                        else:
                            time.sleep(5) 
                        elapsed = time.time()-start
                    raise Exception("Volume("+str(vol.id)+") detached, but device("+str(dev)+") still present on ("+str(self.id)+")")
                else:
                    raise Exception("Volume("+str(vol.id)+") failed to detach from device("+str(dev)+") on ("+str(self.id)+")")
        raise Exception("Detach Volume("+str(euvolume.id)+") not found on ("+str(self.id)+")")
        return True
    
    def get_metadata(self, element_path): 
        """Return the lines of metadata from the element path provided"""
        if self.config:
            isManaged = re.search("managed", self.tester.get_network_mode())
            if not isManaged:
                return self.sys("curl http://" + self.tester.get_clc_ip()  + ":8773/latest/meta-data/" + element_path)
            
        return self.sys("curl http://169.254.169.254/latest/meta-data/" + element_path)
        
        
    
    def get_guestdevs_inuse_by_vols(self):
        retlist = []
        for vol in self.attached_vols:
            retlist.append(vol.guestdev)
        return retlist
    
    
    def get_free_scsi_dev(self, prefix='sd',maxdevs=16):
        '''
        The volume attach command requires a cloud level device name that is not currently associated with a volume 
        Note: This is the device name from the clouds perspective, not necessarily the guest's 
        This method attempts to find a free device name to use in the command
        optional - prefix - string, pre-pended to the the device search string
        optional - maxdevs - number use to specify the max device names to iterate over.Some virt envs have a limit of 16 devs. 
        '''
        d='e'
        dev = None
        for x in xrange(0,maxdevs):
            inuse=False
            #double up the letter identifier to avoid exceeding z
            if d == 'z':
                prefix= prefix+'e'
            dev = "/dev/"+prefix+str(d)
            for vols in self.attached_vols:
                if vols.clouddev == dev:
                    inuse = True
                    continue
            if inuse is False:
                self.debug("Instance:"+str(self.id)+" returning available scsi dev:"+str(dev))
                return dev
            else:
                d = chr(ord('e') + x) #increment the letter we append to the device string prefix
                dev = None
        if dev is None:
            raise Exception("Could not find a free scsi dev on instance:"+self.id )
        
    
    def write_random_data_to_vol_get_md5(self, euvolume, voldev, srcdev='/dev/sda', timepergig=60):
        '''
        Attempts to copy some amount of data into an attached volume, and return the md5sum of that volume
        volume - mandatory - boto volume object of the attached volume 
        voldev - mandatory - string, the device name on the instance where the volume is attached
        srcdev - optional - string, the file to copy into the volume
        timepergig - optional - the time in seconds per gig, used to estimate an adequate timeout period
        '''
        timeout = euvolume.size * timepergig
        self.assertFilePresent(voldev)
        self.assertFilePresent(srcdev)
        self.sys("dd if="+srcdev+" of="+voldev+" && sync")
        md5 = self.sys("md5sum "+voldev, timeout=timeout)[0]
        md5 = md5.split(' ')[0]
        self.debug("Filled Volume:"+euvolume.id+" dev:"+voldev+" md5:"+md5)
        return md5
        
    def reboot_instance_and_verify(self,waitconnect=30, timeout=300, connect=True, checkvolstatus=False):
        '''
        Attempts to reboot an instance and verify it's state post reboot. 
        waitconnect-optional-integer representing seconds to wait before attempting to connect to instance after reboot
        timeout-optional-integer, seconds. If a connection has failed, this timer is used to determine a retry
        onnect- optional - boolean to indicate whether an ssh session should be established once the expected state has been reached
        checkvolstatus - optional -boolean to be used to check volume status post start up
        '''
        msg=""
        self.debug('Attempting to reboot instance:'+str(self.id))
        self.reboot()
        time.sleep(waitconnect)
        self.connect_to_instance(timeout=timeout)
        if checkvolstatus:
            badvols= self.get_unsynced_volumes()
            if badvols is not None:
                for vol in badvols:
                    msg = msg+"\nVolume:"+vol.id+" Local Dev:"+vol.guestdev
                raise Exception("Missing volumes post reboot:"+str(msg)+"\n")
        self.debug(self.id+" reboot_instance_and_verify Success")
        
    def get_unsynced_volumes(self,euvol_list=None, timepervol=30):
        '''
        Returns list of volumes which are no longer attached, and/or the attached device has changed, or is not found.
        If all euvols are shown as attached to this instance, and the last known local dev is present then the list will
        return 'None' as all volumes are successfully attached and state is in sync. 
        By default this method will iterate through all the known euvolumes attached to this euinstance. 
        A subset can be provided in the list argument 'euvol'. 
        vol - optional - euvolume object. If provided, this is the only volume to be verified. 
        '''
        bad_list = []
        vol_list = []
        dev_list = self.get_dev_dir()
        
        if euvol_list is not None:
            vol_list.append(euvol_list)
        else:
            vol_list = self.attached_vols
            
        for vol in vol_list:
            try: 
                self.debug("Checking volume:"+str(vol.id))
                if (vol.attach_data.instance_id == self.id):
                    match = 0 
                    elapsed = 0 
                    start = time.time()
                    while (match == 0):
                        try:
                            self.assertFilePresent('/dev/'+vol.guestdev.strip())
                            self.debug("Found local/volume match dev:"+vol.guestdev.strip())
                            match = 1
                        except: 
                            if (elapsed < timepervol):
                                time.sleep(5)
                            else:
                                bad_list.append(vol)
                                self.debug("volume.guestdev:"+str(vol.guestdev)+",device not found on guest? Elapsed:"+str(elapsed))
                        elapsed = int(time.time() - start)
                else:
                    self.debug("Error, Volume.attach_data.instance_id:("+str(vol.attach_data.instance_id)+") != ("+str(self.id)+")")
                    bad_list.append(vol)
            except Exception, e:
                    self.debug("Volume:"+str(vol.id)+" is no longer attached to this instance:"+str(self.id)+", error:"+str(e) )
                    bad_list.append(vol)
                    pass
            
        if bad_list != []:
            return bad_list
    
    def init_volume_list(self, reattach=False, detach=True):
        '''
        Method to detect volumes which the cloud believes this guest is using, and attempt to match up the cloud dev with the local guest dev.
        In the case the local dev can not be found the volume will be detached. If the local device is found a euvolume object is created and appended 
        the local attached_vols list. To confirm local state with the cloud state, the options 'reattach', or 'detach' can be used. 
        This should be used when first creating a euinstance from an instance to insure the euinstance volume state is in sync with the cloud. 
        '''
        self.attached_vols = []
        cloudlist = []
        cloudlist=self.tester.ec2.get_all_volumes()
        for vol in cloudlist:
            #check to see if the volume is attached to us, but is not involved with the bdm for this instance
            if (vol.attach_data.instance_id == self.id) and (self.block_device_mapping.current_name != vol.attach_data.device):
                dev = vol.attach_data.device
                try:
                    self.assertFilePresent(dev)
                    if not detach:
                        evol = EuVolume.make_euvol_from_vol(vol)
                        evol.guestdev = dev
                        evol.clouddev = dev
                        self.attached_vols.append(evol)
                    else:
                        self.tester.detach_volume(vol)
                except Exception,e:
                    if reattach or detach:
                        self.tester.detach_volume(vol)
                    if reattach:
                        dev = self.get_free_scsi_dev()
                        self.attach_volume(self, self, vol,dev )
                
                
        
        
    def stop_instance_and_verify(self, timeout=120, state='stopped', failstate='terminated'):
        '''
        Attempts to stop instance and verify the state has gone to stopped state
        timeout -optional-time to wait on instance to go to state 'state' before failing
        state -optional-the expected state to signify success, default is stopped
        failstate -optional-a state transition that indicates failure, default is terminated
        '''
        self.debug(self.id+" Attempting to stop instance...")
        start = time.time()
        elapsed = 0
        self.stop()
        while (elapsed < timeout):
            time.sleep(2)
            self.update()
            if self.state == state:
                break
            if self.state == failstate:
                raise Exception(str(self.id)+" instance went to state:"+str(self.state)+" while stopping")
            elapsed = int(time.time()- start)
        if self.state != state:
            raise Exception(self.id+" state: "+str(self.state)+" expected:"+str(state)+", after elapsed:"+str(elapsed))
        self.debug(self.id+" stop_instance_and_verify Success")
        
    
    def start_instance_and_verify(self, timeout=300, state = 'running', failstate='terminated', connect=True, checkvolstatus=False):
        '''
        Attempts to start instance and verify state, and reconnects ssh session
        timeout -optional-time to wait on instance to go to state 'state' before failing
        state -optional-the expected state to signify success, default is running
        failstate -optional-a state transition that indicates failure, default is terminated
        connect- optional - boolean to indicate whether an ssh session should be established once the expected state has been reached
        checkvolstatus - optional -boolean to be used to check volume status post start up
        '''
        self.debug(self.id+" Attempting to start instance...")
        msg=""
        start = time.time()
        elapsed = 0
        self.start()
        while (elapsed < timeout):
            time.sleep(2)
            self.update()
            if self.state == state:
                break
            if self.state == failstate:
                raise Exception(str(self.id)+" instance went to state:"+str(self.state)+" while starting")
              
            elapsed = int(time.time()- start)
        if self.state != state:
            raise Exception(self.id+" not in stopped state after elapsed:"+str(elapsed))
        else:
            self.debug(self.id+" went to state:"+str(state))
            if connect:
                self.connect_to_instance(timeout=timeout)
            if checkvolstatus:
                badvols= self.get_unsynced_volumes()
                if badvols is not None:
                    for vol in badvols:
                        msg = msg+"\nVolume:"+vol.id+" Local Dev:"+vol.guestdev
                    raise Exception("Missing volumes post reboot:"+str(msg)+"\n")
        self.debug(self.id+" start_instance_and_verify Success")
    
                