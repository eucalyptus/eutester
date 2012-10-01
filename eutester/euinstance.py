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

from random import randint
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
    rootfs_device = "sda"
    block_device_prefix = "sd"
    virtio_blk = False
    attached_vols = []
    scsidevs = []
    ops = None
    ssh = None
    logger = None
    debugmethod = None
    timeout =  60
    retry = 1
    verbose = True
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
                                      timeout=120,
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
        #newins.set_block_device_prefix()
        newins.set_rootfs_device()
        
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
        '''
        Attempts to connect to an instance via ssh.
        timeout - optional - time in seconds to wait for connection before failure
        '''
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
                    self.sys("")
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
    
    def debug(self,msg,traceback=1,method=None,frame=False):
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
        
    def get_dev_dir(self, match=None ):
        '''
        Attempts to return a list of devices in /dev which match the given grep criteria
        By default will attempt to match self.block_device_prefix if populated, otherwise will try to match sd,vd, and xd device prefixes.
        returns a list of matching dev names. 
        match - optional - string used in grep search of /dev dir on instance
        '''
        retlist = []
        if match is None:
            match = '^sd\|^vd\|^xd|^xvd'
        out = self.sys("ls -1 /dev/ | grep '^"+str(match)+"'" )
        for line in out:
            retlist.append(line.strip())
        return retlist
    
    def assertFilePresent(self,filepath):
        '''
        Method to check for the presence of a file at 'filepath' on the instance
        filepath - mandatory - string, the filepath to verify
        '''
        filepath = str(filepath).strip()
        out = self.ssh.cmd("ls "+filepath)['status']
        self.debug('exit code:'+str(out))
        if out != 0:
            raise Exception("File:"+filepath+" not found on instance:"+self.id)
        self.debug('File '+filepath+' is present on '+self.id)
        
    
    def attach_volume(self, volume,  dev=None, timeout=60):
        if not isinstance(volume, EuVolume):
            euvolume = EuVolume.make_euvol_from_vol(volume)
        return self.attach_euvolume(euvolume,  dev=dev, timeout=timeout)
    
        
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
        #grab a snapshot of our devices before attach for comparison purposes
        dev_list_before = self.get_dev_dir()
        
        dev_list_after = []
        attached_dev = None
        start= time.time()
        elapsed = 0
        if dev is None:
            dev = self.get_free_scsi_dev()
        if (self.tester.attach_volume(self, euvolume, dev, pause=10,timeout=timeout)): 
            #update our block device prefix, detect if virtio is now in use 
            self.set_block_device_prefix()     
            while (elapsed < timeout):
                self.debug("Checking for volume attachment on guest, elapsed time("+str(elapsed)+")")
                dev_list_after = self.get_dev_dir()
                self.debug("dev_list_after:"+" ".join(dev_list_after))
                diff =list( set(dev_list_after) - set(dev_list_before) )
                if len(diff) > 0:
                    devlist = str(diff[0]).split('/')
                    attached_dev = '/dev/'+devlist[len(devlist)-1]
                    euvolume.guestdev = attached_dev.strip()
                    euvolume.clouddev = dev
                    self.debug("Volume:"+str(euvolume.id)+" guest device:"+str(euvolume.guestdev))
                    self.attached_vols.append(euvolume)
                    self.debug(euvolume.id+" Requested dev:"+str(euvolume.clouddev)+", attached to guest device:"+str(euvolume.guestdev))
                    break
                elapsed = int(time.time() - start)
                time.sleep(2)
            #Check to see if this volume has unique data in the head otherwise write some and md5 it
            self.vol_write_random_data_get_md5(euvolume)
        else:
            self.debug('Failed to attach volume:'+str(euvolume.id)+' to instance:'+self.id)
            raise Exception('Failed to attach volume:'+str(euvolume.id)+' to instance:'+self.id)
        if (attached_dev is None):
            self.debug("List after\n"+" ".join(dev_list_after))
            raise Exception('Volume:'+str(euvolume.id)+' attached, but not found on guest'+str(self.id)+' after '+str(elapsed)+' seconds?')
        self.debug('Success attaching volume:'+str(euvolume.id)+' to instance:'+self.id+', cloud dev:'+str(euvolume.clouddev)+', attached dev:'+str(attached_dev))
        return attached_dev
    
    def detach_euvolume(self, euvolume, waitfordev=True, timeout=180):
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
                if (self.tester.detach_volume(euvolume,timeout=timeout)):
                    if waitfordev:
                        self.debug("Wait for device:"+str(dev)+" to be removed on guest...")
                        while (elapsed < timeout):
                            try:
                                #check to see if device is still present on guest
                                self.assertFilePresent(dev)
                            except Exception, e:
                                #if device is not present remove it
                                self.attached_vols.remove(vol)
                                return True
                            time.sleep(10) 
                            elapsed = int(time.time()-start)
                            self.debug("Waiting for device '"+str(dev)+"' on guest to be removed.Elapsed:"+str(elapsed))
                        #one last check, in case dev has changed. 
                        self.debug("Device "+str(dev)+" still present on "+str(self.id)+" checking sync state...")
                        if self.get_dev_md5(dev, euvolume.md5len) == euvolume.md5:
                            raise Exception("Volume("+str(vol.id)+") detached, but device("+str(dev)+") still present on ("+str(self.id)+")")
                        else:
                            #assume the cloud has successfully released the device, guest may have not
                            self.debug(str(self.id)+'previously attached device for vol('+str(euvolume.id)+') no longer matches md5')
                            return True
                    else:
                        self.attached_vols.remove(vol)
                        return True
                        
                else:
                    raise Exception("Volume("+str(vol.id)+") failed to detach from device("+str(dev)+") on ("+str(self.id)+")")
        raise Exception("Detach Volume("+str(euvolume.id)+") not found on ("+str(self.id)+")")
        return True
    
    def get_metadata(self, element_path): 
        """Return the lines of metadata from the element path provided"""
        ### If i can reach the metadata service ip use it to get metadata otherwise try the clc directly
        if self.found("ping -c 1 169.254.169.254", "1 received"):
            return self.sys("curl http://169.254.169.254/latest/meta-data/" + element_path)
        else:
            return self.sys("curl http://" + self.tester.get_ec2_ip()  + ":8773/latest/meta-data/" + element_path)
        
    def set_block_device_prefix(self):
        return self.set_rootfs_device()
        '''
        if self.found("dmesg | grep vda", "vda"):
            self.block_device_prefix = "vd"
            self.virtio_blk = True
            self.rootfs_device = "vda"
        elif self.found("dmesg | grep xvda", "xvda"):
            self.block_device_prefix = "xvd"
            self.virtio_blk = False
            self.rootfs_device = "xvda"
        else:
            self.block_device_prefix = "sd"
            self.virtio_blk = False
            self.rootfs_device = "sda"
            
        '''
    def set_rootfs_device(self):
        if self.found("dmesg | grep vda", "vda"):
            self.rootfs_device = "vda"
            self.virtio_blk = True
        elif self.found("dmesg | grep xvda", "xvda"):
            self.rootfs_device = "xvda"
            self.virtio_blk = False
        else:
            self.rootfs_device = "sda"
            self.virtio_blk = False
            
    
    def get_guestdevs_inuse_by_vols(self):
        retlist = []
        for vol in self.attached_vols:
            retlist.append(vol.guestdev)
        return retlist
    
    
    def get_free_scsi_dev(self, prefix=None,maxdevs=16):
        '''
        The volume attach command requires a cloud level device name that is not currently associated with a volume 
        Note: This is the device name from the clouds perspective, not necessarily the guest's 
        This method attempts to find a free device name to use in the command
        optional - prefix - string, pre-pended to the the device search string
        optional - maxdevs - number use to specify the max device names to iterate over.Some virt envs have a limit of 16 devs. 
        '''
        d='e'
        dev = None
        if prefix is None:
            prefix = self.block_device_prefix
        cloudlist=self.tester.get_volumes(attached_instance=self.id)
        
        for x in xrange(0,maxdevs):
            inuse=False
            #double up the letter identifier to avoid exceeding z
            if d == 'z':
                prefix= prefix+'e'
            dev = "/dev/"+prefix+str(d)
            for avol in self.attached_vols:
                if avol.clouddev == dev:
                    inuse = True
                    continue
            #Check to see if the cloud has a conflict with this device name...
            for vol in cloudlist:
                if (vol.attach_data is not None) and (vol.attach_data.device == dev):
                    inuse = True
                    continue
            if inuse is False:
                self.debug("Instance:"+str(self.id)+" returning available scsi dev:"+str(dev))
                return str(dev)
            else:
                d = chr(ord('e') + x) #increment the letter we append to the device string prefix
                dev = None
        if dev is None:
            raise Exception("Could not find a free scsi dev on instance:"+self.id )
        
    def zero_fill_volume(self,euvolume):
        '''
        zero fills the given euvolume with,returns dd's data/time stat
        ''' 
        voldev = euvolume.guestdev.strip()
        self.assertFilePresent(voldev)
        fillcmd = "dd if=/dev/zero of="+str(voldev)+"; sync"
        return self.time_dd(fillcmd)
    
    def random_fill_volume(self,euvolume,srcdev=None, length=0):
        '''
        Attempts to fill the entie given euvolume with unique non-zero data.
        The srcdev is read from in a set size, and then used to write to the euvolume to populate it. The file 
        helps with both speed up the copy in the urandom case, and adds both some level of randomness another src device as well as 
        allows smaller src devs to be used to fill larger euvolumes by repeatedly reading into the copy. 
        returns dd's data/time stat
        '''
        gb = 1073741824 
        fsize = 10485760 #10mb
        voldev = euvolume.guestdev.strip()
        self.assertFilePresent(voldev)
        if srcdev is None:
            if self.found('ls /dev/urandom', 'urandom'):
                srcdev = '/dev/urandom'
            else:
                #look for the another large device we can read from in random size increments
                srcdev = "/dev/"+str(self.sys("ls -1 /dev | grep 'da$'")[0]).strip()
                fsize = randint(1048576,10485760)
                
        if length <= fsize:
            fillcmd = self.sys("head -c "+str(length)+" "+srcdev+" > "+voldev+"; sync")
        else:
            count = int((euvolume.size*gb)/fsize)
            fillcmd="head -c "+str(fsize)+" "+str(srcdev)+" > /tmp/datafile; x=0; while [ $x -lt "+str(count)+" ]; do cat /tmp/datafile; let x=$x+1; done | dd of="+str(voldev)+"; rm /tmp/datafile; sync"
        return self.time_dd(fillcmd)
    
    
    def time_dd(self,ddcmd):
        '''
        Executes dd command on instance, parses and returns dd's data/time stat
        '''
        time=""
        out = self.sys(ddcmd)
        for line in out:
            line = str(line)
            if re.search('copied',line):
                time=int(str(line.split(',').pop()).split()[0])
        return time
    
    def vol_write_random_data_get_md5(self, euvolume, srcdev=None, length=32, timepergig=90, overwrite=False):
        '''
        Attempts to copy some amount of data into an attached volume, and return the md5sum of that volume
        A brief check of the first 32 bytes is performed to see if this volume has pre-existing non-zero filled data. 
        If pre-existing data is found, and the overwrite flag is not set then the write is not performed. 
        Returns string with MD5 checksum calculated on 'length' bytes from the head of the device. 
        volume - mandatory - boto volume object of the attached volume 
        srcdev - optional - string, the file to copy into the volume
        timepergig - optional - the time in seconds per gig, used to estimate an adequate timeout period
        overwrite - optional - boolean. write to volume regardless of whether existing data is found
        '''
        
        voldev = euvolume.guestdev.strip()  
        #check to see if there's existing data that we should avoid overwriting 
        if overwrite or ( int(self.sys('head -c 32 '+str(voldev)+' | xargs -0 printf %s | wc -c')[0]) == 0):
            self.random_fill_volume(euvolume, srcdev=srcdev, length=length)
        self.debug("Volume has existing data, skipping random data fill")
        #calculate checksum of euvolume attached device for given length
        md5 = self.md5_attached_euvolume(euvolume, timepergig=timepergig,length=length)
        self.debug("Filled Volume:"+euvolume.id+" dev:"+voldev+" md5:"+md5)
        return md5
    
    def md5_attached_euvolume(self, euvolume, timepergig=90,length=None,updatevol=True):
        '''
        Calculates an md5sum of the first 'length' bytes of the dev representing the attached euvolume.
        By default will use the md5len stored within the euvolume. The euvolume will be updated with the
        resulting checksum and length.
        Returns the md5 checksum
        euvolume - mandatory - euvolume object used to calc checksum against
        timepergig - optional - number of seconds used per gig in volume size used in calcuating timeout 
        length - optional - number bytes to read from the head of the device file used in md5 calc
        updatevol - optional - boolean used to update the euvolume data or not
        '''
        if length is None:
            length = euvolume.md5len
        try:
            voldev = euvolume.guestdev
            timeout = euvolume.size * timepergig
            md5 = self.get_dev_md5(voldev, length)
            self.debug("Got MD5 for Volume:"+euvolume.id+" dev:"+voldev+" md5:"+md5)
            if updatevol:
                euvolume.md5=md5
                euvolume.md5len=length
        except Exception, e:
            raise Exception("Failed to md5 attached volume: " +str(e))
        return md5
    
    def get_dev_md5(self, devpath, length): 
        self.assertFilePresent(devpath)
        if length == 0:
            md5 = str(self.sys("md5sum "+voldev, timeout=timeout)[0]).split(' ')[0].strip()
        else:
            md5 = str(self.sys("head -c "+str(length)+" "+str(devpath)+" | md5sum")[0]).split(' ')[0].strip()
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
        if checkvolstatus:
            #update the md5sums per volume before reboot
            bad_vols=self.get_unsynced_volumes()
            if bad_vols != []:
                for bv in bad_vols:
                    self.debug(str(self.id)+'Unsynced volume found:'+str(bv.id))
                raise Exception(str(self.id)+"Could not reboot using checkvolstatus flag due to unsync'd volumes")
        self.reboot()
        time.sleep(waitconnect)
        self.connect_to_instance(timeout=timeout)
        if checkvolstatus:
            badvols= self.get_unsynced_volumes()
            if badvols != []:
                for vol in badvols:
                    msg = msg+"\nVolume:"+vol.id+" Local Dev:"+vol.guestdev
                raise Exception("Missing volumes post reboot:"+str(msg)+"\n")
        self.debug(self.id+" reboot_instance_and_verify Success")
        
    def get_unsynced_volumes(self,euvol_list=None, md5length=32, timepervol=90,min_polls=2, check_md5=False):
        '''
        Returns list of volumes which are:
        -in a state the cloud believes the vol is no longer attached
        -the attached device has changed, or is not found.
        If all euvols are shown as attached to this instance, and the last known local dev is present and/or a local device is found with matching md5 checksum
        then the list will return 'None' as all volumes are successfully attached and state is in sync. 
        By default this method will iterate through all the known euvolumes attached to this euinstance. 
        A subset can be provided in the list argument 'euvol_list'. 
        Returns a list of euvolumes for which a corresponding guest device could not be found, or the cloud no longer believes is attached. 
         
        euvol_list - optional - euvolume object list. Defaults to all self.attached_vols
        md5length - optional - defaults to the length given in each euvolume. Used to calc md5 checksum of devices
        timerpervolume -optional - time to wait for device to appear, per volume before failing
        min_polls - optional - minimum iterations to check guest devs before failing, despite timeout
        check_md5 - optional - find devices by md5 comparision. Default is to only perform this check when virtio_blk is in use.
        '''
        bad_list = []
        vol_list = []
        checked_vdevs = []
        poll_count = 0
        dev_list = self.get_dev_dir()
        found = False

        if euvol_list is not None:
            vol_list.append(euvol_list)
        else:
            vol_list = self.attached_vols
        
            
        for vol in vol_list:
            #first see if the cloud believes this volume is still attached. 
            try: 
                self.debug("Checking volume:"+str(vol.id))
                if (vol.attach_data.instance_id == self.id): #verify the cloud status is still attached to this instance
                    found = False
                    elapsed = 0 
                    start = time.time()
                    #loop here for timepervol in case were waiting for a volume to appear in the guest. ie attaching
                    while (not found) and ((elapsed <= timepervol) or (poll_count < min_polls)):
                        try:
                            poll_count += 1
                            #Ugly... :-(
                            #handle virtio and non virtio cases differently (KVM case needs improvement here).
                            if self.virtio_blk or check_md5:
                                #Do some detective work to see what device name the previously attached volume is using
                                devlist = self.get_dev_dir()
                                for vdev in devlist:
                                    vdev = "/dev/"+str(vdev)
                                    
                                    #if we've already checked the md5 on this dev no need to re-check it. 
                                    if not re.match(vdev," ".join(checked_vdevs)): 
                                        self.debug('Checking '+str(vdev)+" for match against euvolume:"+str(vol.id))
                                        md5 = self.get_dev_md5(vdev, vol.md5len )
                                        self.debug('comparing '+str(md5)+' vs '+str(vol.md5))
                                        if md5 == vol.md5:
                                            self.debug('Found match at dev:'+str(vdev))
                                            found = True
                                            if (vol.guestdev != vdev ):
                                                self.debug("("+str(vol.id)+")Guest dev changed! Updating from:'"+str(vol.guestdev)+"' to:'"+str(vdev)+"'")
                                            else:
                                                self.debug("("+str(vol.id)+")Found local match at previous dev:'"+str(vol.guestdev)+"'")
                                            vol.guestdev = vdev
                                        checked_vdevs.append(vdev) # add to list of devices we've already checked.
                                    if found:
                                        break
                            else:
                                #Not using virtio_blk assume the device will be the same
                                self.assertFilePresent(vol.guestdev.strip())
                                self.debug("("+str(vol.id)+")Found local/volume match dev:"+vol.guestdev.strip())
                                found = True
                        except:pass 
                        if found:
                            break
                        self.debug('Not found sleep and check again...')
                        time.sleep(10)
                        elapsed = int(time.time() - start)
                    if not found:
                        bad_list.append(vol)
                        self.debug("("+str(vol.id)+")volume.guestdev:"+str(vol.guestdev)+", dev not found on guest? Elapsed:"+str(elapsed))
                else:
                    self.debug("("+str(vol.id)+")Error, Volume.attach_data.instance_id:("+str(vol.attach_data.instance_id)+") != ("+str(self.id)+")")
                    bad_list.append(vol)
            except Exception, e:
                    self.debug("Volume:"+str(vol.id)+" is no longer attached to this instance:"+str(self.id)+", error:"+str(e) )
                    bad_list.append(vol)
                    pass
        return bad_list
        
    def verify_attached_vol_cloud_status(self,euvolume ):
        '''
        Confirm that the cloud is showing the state for this euvolume as attached to this instance
        '''
        try:
            euvolume = cloudlist=self.tester.get_volume(volume_id=euvolume.id)
        except Exception, e:
            self.debug("Error in verify_attached_vol_status, try running init_volume_list first")
            raise Exception("Failed to get volume in get_attached_vol_cloud_status, err:"+str(e))
        if euvolume.attach_data.instance_id != self.id:
            self.debug("Error in verify_attached_vol_status, try running init_volume_list first")
            raise Exception("("+str(self.id)+")Cloud status for vol("+str(euvolume.id)+" = not attached to this instance ")
            
            
    def init_volume_list(self, reattach=False, detach=True, timeout=300):
        '''
        This should be used when first creating a euinstance from an instance to insure the euinstance volume state is in sync with the cloud, mainly
        for the case where a euinstance is made from a pre-existing and in-use instance. 
        Method to detect volumes which the cloud believes this guest is using, and attempt to match up the cloud dev with the local guest dev.
        In the case the local dev can not be found the volume will be detached. If the local device is found a euvolume object is created and appended 
        the local attached_vols list. To confirm local state with the cloud state, the options 'reattach', or 'detach' can be used. 
        
        '''
        self.attached_vols = []
        cloudlist = []
        
        #Make sure the volumes we think our attached are in a known good state
        badvols = self.get_unsynced_volumes()
        
        for badvol in badvols:
            try:
                self.detach_euvolume(badvol, timeout=timeout)
            except Exception, e:
               raise Exception("Error in sync_volume_list attempting to detach badvol:"+str(badvol.id)+". Err:"+str(e))
                
        cloudlist=self.tester.ec2.get_all_volumes()
        found = False
        for vol in cloudlist:
            #check to see if the volume is attached to us, but is not involved with the bdm for this instance
            found = False
            if (vol.attach_data.instance_id == self.id) and not ( self.root_device_type == 'ebs' and self.block_device_mapping.current_name != vol.attach_data.device):
                for avol in self.attached_vols:
                    if avol.id == vol.id:
                        self.debug("Volume"+vol.id+" found attached")
                        found = True
                        break
                if not found: 
                    dev = vol.attach_data.device
                    try:
                        self.assertFilePresent(dev)
                        if not detach:
                            evol = EuVolume.make_euvol_from_vol(vol)
                            evol.guestdev = dev
                            evol.clouddev = dev
                            self.attached_vols.append(evol)
                        else:
                            self.tester.detach_volume(vol,timeout=timeout)
                    except Exception,e:
                        if reattach or detach:
                            self.tester.detach_volume(vol,timeout=timeout)
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
            raise Exception(self.id+" not in "+str(state)+" state after elapsed:"+str(elapsed))
        else:
            self.debug(self.id+" went to state:"+str(state))
            if connect:
                self.connect_to_instance(timeout=timeout)
            if checkvolstatus:
                badvols= self.get_unsynced_volumes()
                if badvols != []:
                    for vol in badvols:
                        msg = msg+"\nVolume:"+vol.id+" Local Dev:"+vol.guestdev
                    raise Exception("Missing volumes post reboot:"+str(msg)+"\n")
        self.debug(self.id+" start_instance_and_verify Success")
    
    
    def get_users(self):
        '''
        Attempts to return a list of normal linux users local to this instance.
        Returns a list of all non-root users found within the uid_min/max range who are not marked nologin
        '''
        users =[]
        try:
            uid_min = str(self.sys("grep ^UID_MIN /etc/login.defs | awk '{print $2}'")[0]).strip()
            uid_max = str(self.sys("grep ^UID_MAX /etc/login.defs | awk '{print $2}'")[0]).strip()
            try:
                users = str(self.sys("cat /etc/passwd | grep -v nologin | awk -F: '{ if ( $3 >= "+str(uid_min)+" && $3 <= "+str(uid_max)+" ) print $0}' ")[0]).split(":")[0]
            except IndexError, ie:
                self.debug("No users found, passing exception:"+str(ie))
                pass
            return users
        except Exception, e:
            self.debug("Failed to get local users. Err:"+str(e))
            
    def get_user_password(self,username):
        '''
        Attempts to verify whether or not a user 'username' has a password set or not on this instance. 
        returns true if a password is detected, else false
        
        '''
        password = None
        out = self.sys("cat /etc/passwd | grep '^"+str(username)+"'")
        if out != []:
            self.debug("pwd out:"+str(out[0]))
            if (str(out[0]).split(":")[1] == "x"):
                out = self.sys("cat /etc/shadow | grep '^"+str(username)+"'")
                if out != []:
                    password = str(out[0]).split(":")[1]
                    if password == "" or re.match("^!+$", password ):
                        password = None         
        return password
                                    
                
    def get_user_group_info(self,username, index=3):
        '''
        Attempts to return a list of groups for a specific user on this instance. 
        index is set at the grouplist by default [3], but can be adjust to include the username, password, and group id as well in the list. 
        where the parsed string should be in format 'name:password:groupid1:groupid2:groupid3...' 
        '''
        groups =[]
        out = []
        try:
            out = self.sys("cat /etc/group | grep '^"+str(username)+"'")
            if out != []:
                groups = str( out[0]).strip().split(":")
                #return list starting at group index
                groups = groups[index:len(groups)]
            return groups
        except Exception, e:
            self.debug("No group found for user:"+str(username)+", err:"+str(e))
    
    
    
    
    
        
        
        
        
            
            
                
