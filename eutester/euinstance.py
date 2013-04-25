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
from eutester.taggedresource import TaggedResource
from random import randint
import sshconnection
import sys
import os
import re
import time
import types





class EuInstance(Instance, TaggedResource):
    keypair = None
    keypath = None
    username = None
    password = None
    rootfs_device = "sda"
    block_device_prefix = "sd"
    virtio_blk = False
    bdm_vol = None
    reservation = None
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
    private_addressing = False
    tester = None
    laststate = None
    laststatetime = None
    age_at_state = None
    cmdstart = 0
    auto_connect = True
    security_groups = []
    vmtype_info = None
   
    @classmethod
    def make_euinstance_from_instance(cls, 
                                      instance, 
                                      tester,
                                      debugmethod = None, 
                                      keypair=None, 
                                      keypath=None, 
                                      password=None, 
                                      username="root",  
                                      auto_connect = True,
                                      verbose=True, 
                                      timeout=120,
                                      private_addressing = False,
                                      reservation = None, 
                                      cmdstart=None, 
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
            newins.logger = eulogger.Eulogger(identifier= str(instance.id))
            newins.debugmethod= newins.logger.log.debug
            
        if (keypair is not None):
            if isinstance(keypair,types.StringTypes):
                keyname = keypair
                keypair = tester.get_keypair(keyname)
            else:
                keyname = keypair.name
            keypath = os.getcwd() + "/" + keyname + ".pem"
        newins.keypair = keypair
        newins.keypath = keypath
        newins.password = password
        newins.username = username
        newins.verbose = verbose
        newins.attached_vols=[] 
        newins.timeout = timeout
        newins.retry = retry    
        newins.private_addressing = private_addressing
        newins.reservation = reservation or newins.tester.get_reservation_for_instance(newins)
        newins.security_groups = newins.tester.get_instance_security_groups(newins)
        newins.laststate = newins.state
        newins.cmdstart = cmdstart
        newins.auto_connect = auto_connect
        newins.set_last_status()
        newins.update_vm_type_info()
        #newins.set_block_device_prefix()
        if newins.root_device_type == 'ebs':
            try:
                volume = newins.tester.get_volume(volume_id = newins.block_device_mapping.current_value.volume_id)
                newins.bdm_vol = EuVolume.make_euvol_from_vol(volume, tester=newins.tester,cmdstart=newins.cmdstart)
            except:pass
                
        if newins.auto_connect:
            newins.connect_to_instance(timeout=timeout)
        if newins.ssh:
            newins.set_rootfs_device()
        return newins
    
    def update(self):
        super(EuInstance, self).update()
        self.set_last_status()
    
    def set_last_status(self,status=None):
        self.laststate = self.state
        self.laststatetime = time.time()
        self.age_at_state = self.tester.get_instance_time_launched(self)
        #Also record age from user's perspective, ie when they issued the run instance request (if this is available)
        if self.cmdstart:
            self.age_from_run_cmd = "{0:.2f}".format(time.time() - self.cmdstart) 
        else:
            self.age_from_run_cmd = None
        
        
    
    def printself(self,title=True, footer=True, printmethod=None):
        if self.bdm_vol:
            bdmvol = self.bdm_vol.id
        else:
            bdmvol = None
            
        buf = "\n"
        if title:
            buf += str("-------------------------------------------------------------------------------------------------------------------------------------------------------------------\n")
            buf += str('INST_ID').center(11)+'|'+str('EMI').center(13)+'|'+str('RES_ID').center(11)+'|'+str('LASTSTATE').center(10)+'|'+str('PRIV_ADDR').center(10)+'|'+str('AGE@STATUS').center(13)+'|'+str('VMTYPE').center(12)+'|'+str('BDM_VOL').center(13)+'|'+str('CLUSTER').center(25)+'|'+str('PUB_IP').center(16)+'|'+str('PRIV_IP')+'\n'
            buf += str("-------------------------------------------------------------------------------------------------------------------------------------------------------------------\n")
        buf += str(self.id).center(11)+'|'+str(self.image_id).center(13)+'|'+str(self.reservation.id).center(11)+'|'+str(self.laststate).center(10)+'|'+str(self.private_addressing).center(10)+'|'+str(self.age_at_state).center(13)+'|'+str(self.instance_type).center(12)+'|'+str(bdmvol).center(13)+'|'+str(self.placement).center(25)+'|'+str(self.public_dns_name).center(16)+'|'+str(self.private_ip_address).rstrip()
        if footer:
            buf += str("\n-------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        if printmethod:
            printmethod(buf)
        return buf
        
        
        
        
    
    def reset_ssh_connection(self, timeout=None):
        timeout = timeout or self.timeout
        self.debug('reset_ssh_connection for:'+str(self.id))
        if ((self.keypath is not None) or ((self.username is not None)and(self.password is not None))):
            if self.ssh is not None:
                self.ssh.close()
            self.debug('Connecting ssh '+str(self.id))
            self.ssh = sshconnection.SshConnection(
                                                    self.ip_address,
                                                    keypair=self.keypair, 
                                                    keypath=self.keypath,          
                                                    password=self.password, 
                                                    username=self.username, 
                                                    timeout=timeout,
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
        attempts = 0
        if ((self.keypath is not None) or ((self.username is not None)and(self.password is not None))):
            start = time.time()
            elapsed = 0
            if self.ssh is not None:
                self.ssh.close()
            self.ssh = None
            while (elapsed < timeout):
                attempts += 1
                try:
                    self.reset_ssh_connection()
                    self.debug('Try some sys...')
                    self.sys("")
                except Exception, se:
                    self.debug('Caught exception attempting to reconnect ssh:'+ str(se))
                    elapsed = int(time.time()-start)
                    self.debug('connect_to_instance: Attempts:'+str(attempts)+', elapsed:'+str(elapsed)+'/'+str(timeout))
                    time.sleep(5)
                    pass
                else:
                    break
            if self.ssh is None:
                raise Exception(str(self.id)+":Failed establishing ssh connection to instance, elapsed:"+str(elapsed)+
                                "/"+str(timeout))
        else:
            self.debug("keypath or username/password need to be populated for ssh connection") 
    
    def debug(self,msg,traceback=1,method=None,frame=False):
        '''
        Used to print debug, defaults to print() but over ridden by self.debugmethod if not None
        msg - mandatory -string, message to be printed
        '''
        if ( self.verbose is True ):
            self.debugmethod(msg)

    def sys(self, cmd, verbose=True, code=None, timeout=120):
        '''
        Issues a command against the ssh connection to this instance
        Returns a list of the lines from stdout+stderr as a result of the command
        cmd - mandatory - string, the command to be executed 
        verbose - optional - boolean flag to enable debug
        timeout - optional - command timeout in seconds 
        '''
        output = []
        if (self.ssh is not None):
            output = self.ssh.sys(cmd, verbose=verbose, code=code, timeout=timeout)
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
            match = '^sd\|^vd\|^xd\|^xvd'
        out = self.sys("ls -1 /dev/ | grep '"+str(match)+"'" )
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
        
    
    def attach_volume(self, volume,  dev=None, timeout=60, overwrite=False):
        '''
        Method used to attach a volume to an instance and track it's use by that instance
        required - euvolume - the euvolume object being attached
        required - tester - the eucaops/eutester object/connection for this cloud
        optional - dev - string to specify the dev path to 'request' when attaching the volume to
        optional - timeout - integer- time allowed before failing
        optional - overwrite - flag to indicate whether to overwrite head data of a non-zero filled volume upon attach for md5
        ''' 
        if not isinstance(volume, EuVolume):
            volume = EuVolume.make_euvol_from_vol(volume)
        return self.attach_euvolume(volume,  dev=dev, timeout=timeout, overwrite=overwrite)
    
        
    def attach_euvolume(self, euvolume, dev=None, timeout=60, overwrite=False):
        '''
        Method used to attach a volume to an instance and track it's use by that instance
        required - euvolume - the euvolume object being attached
        required - tester - the eucaops/eutester object/connection for this cloud
        optional - dev - string to specify the dev path to 'request' when attaching the volume to
        optional - timeout - integer- time allowed before failing
        optional - overwrite - flag to indicate whether to overwrite head data of a non-zero filled volume upon attach for md5
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
            if not euvolume.guestdev:
                raise Exception('Device not found on guest after '+str(elapsed)+' seconds')
            #Check to see if this volume has unique data in the head otherwise write some and md5 it
            self.vol_write_random_data_get_md5(euvolume,overwrite=overwrite)
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
        waitfordev - boolean to indicate whether or no to poll guest instance for local device to be removed
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
    
    def get_metadata(self, element_path, prefix='latest/meta-data/'): 
        """Return the lines of metadata from the element path provided"""
        ### If i can reach the metadata service ip use it to get metadata otherwise try the clc directly
        if self.found("ping -c 1 169.254.169.254", "1 received"):
            return self.sys("curl http://169.254.169.254/"+str(prefix)+str(element_path), code=0)
        else:
            return self.sys("curl http://" + self.tester.get_ec2_ip()  + ":8773/"+str(prefix) + str(element_path), code=0)
        
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
        
    
    
    def terminate_and_verify(self,verify_vols=True,volto=30, timeout=300):
        '''
        Attempts to terminate the instance and verify delete on terminate state of an ebs root block dev if any. 
        If flagged will attempt to verify the correct
        state of any volumes attached during the terminate operation. 
        
        :type verify_vols: boolean
        :param verify_vols: boolean used to flag whether or not to check for correct volume state after terminate
        
        :type volto: integer
        :param volto: timeout used for time in seconds to wait for volumes to detach and become available after terminating the instnace
        
        :type timeout: integer
        :param timeout: timeout in seconds when waiting for an instance to go to terminated state. 
        '''
        bad_vols = []
        bad_vol_ids = []
        start = time.time()
        if verify_vols:
            self.debug('Checking euinstance attached volumes states are in sync with clouds...')
            for vol in self.attached_vols:
                try:
                    self.verify_attached_vol_cloud_status(vol)
                except Exception, e: 
                    self.debug('Caught exception verifying attached status for:'+str(vol.id)+", adding to list for post terminate info. Error:"+str(e))
                    bad_vols.append(vol)
                    bad_vol_ids.append(vol.id)
        self.tester.terminate_single_instance(self, timeout=timeout)
        elapsed = int(time.time()-start)
        if self.bdm_vol:
            #check for bfebs backing volume state
            if self.block_device_mapping.current_value.delete_on_termination:
                vol_state='deleted'
            else:
                vol_state='available'
            self.bdm_vol.update()
            while self.bdm_vol.status != vol_state and elapsed < timeout:
                elapsed = int(time.time()-start)
                self.debug('Delete on terminate:'+str(self.block_device_mapping.current_value.delete_on_termination)+', expected state:'+str(vol_state)+', '+str(self.bdm_vol.id)+" in state:"+str(self.bdm_vol.status)+", elapsed:"+str(elapsed)+"/"+str(timeout))
                self.bdm_vol.update()
                time.sleep(5)
        if verify_vols:
            self.debug('Waiting for attached volumes to go to available...')
            while self.attached_vols and (elapsed < timeout): 
                for vol in self.attached_vols:
                    elapsed = int(time.time()-start)
                    vol.update()
                    self.debug(str(self.id)+' terminated, waiting for attached volume:'+str(vol.id)+ ', status:'+str(vol.status))
                    if vol.status == 'available':
                        self.attached_vols.remove(vol)
                if self.attached_vols and (elapsed < timeout):
                        time.sleep(5)
            
            if self.attached_vols or bad_vols:
                attached_vol_error = ""
                if bad_vols:
                    bad_vol_error = 'ERROR: Unsynced volumes found prior to issuing terminate, check test code:'+",".join(bad_vol_ids)
                if self.attached_vols:
                    attached_vol_error += 'ERROR: Volumes did not become available after instance was terminated:'
                    for vol in self.attached_vols:
                        attached_vol_error += str(vol.id)+':'+str(vol.status)+", "                        
                raise Exception(str(self.id)+", volume errors found during instance terminate:\n"+bad_vol_error+"\n"+attached_vol_error )
                
                
        
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
        in_use_cloud = ""
        in_use_guest = ""
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
                    in_use_guest += str(avol.id)+", "
                    continue
            #Check to see if the cloud has a conflict with this device name...
            for vol in cloudlist:
                vol.update()
                if (vol.attach_data is not None) and (vol.attach_data.device == dev):
                    inuse = True
                    in_use_cloud += str(vol.id)+", "
                    continue
            if inuse is False:
                self.debug("Instance:"+str(self.id)+" returning available cloud scsi dev:"+str(dev))
                return str(dev)
            else:
                d = chr(ord('e') + x) #increment the letter we append to the device string prefix
                dev = None
        if dev is None:
            raise Exception("Could not find a free scsi dev on instance:"+self.id+", maxdevs:"+str(maxdevs)+"\nCloud_devs:"+str(in_use_cloud)+"\nGuest_devs:"+str(in_use_guest))
        
    def zero_fill_volume(self,euvolume):
        '''
        zero fills the given euvolume with,returns dd's data/time stat
        ''' 
        voldev = euvolume.guestdev.strip()
        self.assertFilePresent(voldev)
        fillcmd = "dd if=/dev/zero of="+str(voldev)+"; sync"
        return self.time_dd(fillcmd)
    
    def random_fill_volume(self,euvolume,srcdev=None, length=None, timepergig=90):
        '''
        Attempts to fill the entie given euvolume with unique non-zero data.
        The srcdev is read from in a set size, and then used to write to the euvolume to populate it. The file 
        helps with both speed up the copy in the urandom case, and adds both some level of randomness another src device as well as 
        allows smaller src devs to be used to fill larger euvolumes by repeatedly reading into the copy. 
        :param euvolume: the attached euvolume object to write data to
        :param srcdev: the source device to copy data from 
        :param length: the number of bytes to copy into the euvolume
        :returns dd's data/time stat
        '''
        mb = 1048576
        gb = 1073741824 
        fsize = 10485760 #10mb
        if not euvolume in self.attached_vols:
            raise Exception(self.id+" Did not find this in instance's attached list. Can not write to this euvolume")
        
        voldev = euvolume.guestdev.strip()
        self.assertFilePresent(voldev)
        if srcdev is None:
            if self.found('ls /dev/urandom', 'urandom'):
                srcdev = '/dev/urandom'
            else:
                #look for the another large device we can read from in random size increments
                srcdev = "/dev/"+str(self.sys("ls -1 /dev | grep 'da$'")[0]).strip()
                fsize = randint(1048576,10485760)
        if not length:
            timeout = int(euvolume.size) * timepergig
            return self.dd_monitor(ddif=str(srcdev), ddof=str(voldev), ddbs=fsize,timeout=timeout)
        else:
            timeout = timepergig * ((length/gb) or 1) 
            #write the volume id into the volume for starters
            ddcmd = 'echo '+str(euvolume.id)+' | dd of='+str(voldev)
            dd_res_for_id = self.dd_monitor(ddcmd=ddcmd, timeout=timeout)
            len_remaining = length - int(dd_res_for_id['dd_bytes'])
            if len_remaining <= length:
                return dd_res_for_id
            if length < mb:
                return self.dd_monitor(ddif=str(srcdev), ddof=str(voldev), ddbs=length, ddseek=int(dd_res_for_id['dd_bytes']), timeout=timeout)
            else:
                return self.dd_monitor(ddif=str(srcdev), ddof=str(voldev), ddbytes=length, ddseek=int(dd_res_for_id['dd_bytes']), timeout=timeout)
                
            
    
    def time_dd(self,ddcmd, timeout=90, poll_interval=1, tmpfile=None):
        '''
        (Added for legacy support, use dd_monitor instead) Executes dd command on instance, parses and returns stats on dd outcome
        '''
        return self.dd_monitor(ddcmd=ddcmd, poll_interval=poll_interval, tmpfile=tmpfile)
        
    def dd_monitor(self, ddif=None, ddof=None, ddcount=None, ddbs=1024, ddbytes=None, ddcmd=None, ddseek=None, timeout=300, poll_interval=1, tmpfile=None):
        '''
        Executes dd command on instance, monitors and displays ongoing status, and returns stats dict for dd outcome
        :type ddif: str
        :param ddif: Interface to read data in from
        
        :type ddof: str
        :param ddof: Interface to write data to
        
        :type ddcount: int
        :param ddcount: Number or count of block size (ddbs) to read/write
        
        :type ddbs: int
        :param ddbs: Block size used for  reads/writes
        
        :type ddbytes: int
        :param ddbytes: Number of bytes to be roughly read/write (note: used as ddbytes/ddbs = count) 
        
        :type ddcmd: str
        :param ddcmd: String representing a preformed dd comand to be executed and monitored
        
        :type ddseek: int
        :param ddseek: length of ddof file to seek before writing
        
        :type timeout: int
        :param timeout: Number of seconds to wait before timing out on dd cmd. 
        
        :type poll_interval: int
        :param poll_interval: Number of seconds to pause between polling dd and updating status
        
        :type tmpfile: str
        :param tmpfile: temp file used on remote instance to redirect dd's stderr to in order to nohup dd. 
        
        :rtype: dict
        :returns: dict containing dd stats
        '''
        
        mb = 1048576 #bytes per mb
        gig = 1073741824 #bytes per gig
        #this tmp file will be created on remote instance to write stderr from dd to...
        if not tmpfile:
            tstamp = time.time()
            tmpfile = '/tmp/eutesterddcmd.'+str(int(tstamp))
        #init return dict 
        ret = {
               'dd_records_in' : 0,
               'dd_records_out' : 0,
               'dd_bytes' : 0,
               'dd_mb' : 0,
               'dd_gig' : 0,
               'dd_elapsed' : 0,
               'dd_rate' : 0,
               'dd_units' : "",
               'dd_full_rec_in' : 0,
               'dd_full_rec_out' : 0,
               'dd_partial_rec_in' : 0,
               'dd_partial_rec_out' : 0,
               'test_time' : 0,
               'test_rate' : 0,
               'ddcmd' : "" }
        dd_units = 0
        elapsed = 0
        done = False
        infobuf = None
        start = time.time()
        if ddcmd:
            ddcmd = ddcmd
        else:
            if not ddif or not ddof:
                raise Exception('dd_monitor needs ddif and ddof, or a preformed ddcmd string')
            ddbs_str = str(' bs='+str(ddbs)+' ') or ""
            if ddcount:
                ddcount_str = str(' count='+str(ddcount)+' ')
            elif ddbytes and ddbs:
                ddcount_str = str(' count='+str(ddbytes/ddbs)+' ')
            else:
                ddcount_str = ''
            if ddseek:
                ddseek_str = str(' seek='+str(ddseek)+' ')
            else:
                 ddseek_str = ''
            ddcmd = str('dd if='+str(ddif)+' of='+str(ddof)+str(ddseek_str)+str(ddbs_str)+str(ddcount_str))
            ret['ddcmd'] = ddcmd
        '''
        Due to the ssh psuedo tty, this is done in an ugly manner to get output of future usr1 signals 
        for dd status updates and allow this to run with nohup in the background. Added sleep so cmd is nohup'd 
        before tty is terminated (maybe?)
        '''
        cmd = 'nohup '+str(ddcmd)+' 2> '+str(tmpfile)+' & echo $! && sleep 2'
        #Execute dd command and store echo'd pid from output
        dd_pid = self.sys(cmd)[0]
        
        #Form the table headers for printing dd status...
        linediv = '\n----------------------------------------------------------------------------------------------------------------------------\n'
        databuf = str('BYTES').ljust(15)
        databuf += '|'+str('MBs').center(15)
        databuf += '|'+str('GIGs').center(8)
        
        timebuf = '|'+str('DD TIME').center(10)
        timebuf += '|'+str('TEST TIME').center(10)
        
        ratebuf = '|'+str('DD RATE').center(12)
        ratebuf += '|'+str('TEST RATE').center(12)
        
        recbuf = '|'+str('REC_IN').center(18)
        recbuf += '|'+str('REC_OUT').center(18)
        
        info_header = str('DD DATA INFO').ljust(len(databuf))
        info_header += '|' + str('DD TIME INFO').center(len(timebuf)-1) 
        info_header += '|' + str('DD RATE INFO').center(len(ratebuf)-1)
        info_header += '|' + str('DD RECORDS FULL/PARTIAL INFO').center(len(recbuf)-1)
        
        buf = linediv
        buf += info_header
        buf += linediv
        buf += databuf + timebuf + ratebuf + recbuf
        buf += linediv
        sys.stdout.write(buf)
        sys.stdout.flush()
        
        #Keep getting and printing dd status until done...
        while not done and (elapsed < timeout):
            #send sig usr1 to have dd process dump status to stderr redirected to tmpfile
            output = self.ssh.cmd('kill -USR1 '+str(dd_pid), verbose=False)
            cmdstatus = int(output['status'])
            if cmdstatus != 0:
                done = True
                #if the command returned error, process is done
                out = self.sys('cat '+str(tmpfile)+"; rm -f "+str(tmpfile),code=0, verbose=False)
            else:
                #if the above command didn't error out then dd ps is still running, grab status from tmpfile, and clear it
                out= self.sys('cat '+str(tmpfile)+" && echo '' > "+str(tmpfile)+ ' 2>&1 > /dev/null', code=0, verbose=False)
            for line in out:
                line = str(line)
                try:
                    if re.search('records in',line):
                        ret['dd_records_in'] = str(line.split()[0]).strip()
                        ret['dd_full_rec_in'] = str(ret['dd_records_in'].split("+")[0].strip())
                        #dd_full_rec_in = int(dd_full_rec_in)
                        ret['dd_partial_rec_in'] = str(ret['dd_records_in'].split("+")[1].strip())
                        #dd_partial_rec_in = int(dd_partial_rec_in)
                    elif re.search('records out', line):
                        ret['dd_records_out'] = str(line.split()[0]).strip()
                        ret['dd_full_rec_out'] = str(ret['dd_records_out'].split("+")[0].strip())
                        #dd_ful_rec_out = int(dd_full_rec_out)
                        ret['dd_partial_rec_out'] = str(ret['dd_records_out'].split("+")[1].strip())
                        #dd_partial_rec_out = int(dd_partial_rec_out)
                    elif re.search('copied',line):
                        #123456789 bytes (123 MB) copied, 12.34 s, 123.45 MB/s
                        summary = line.split()
                        ret['dd_bytes'] = int(summary[0])
                        ret['dd_mb'] = float("{0:.2f}".format(ret['dd_bytes']/float(mb)))
                        ret['dd_gig'] = float("{0:.2f}".format(ret['dd_bytes']/float(gig)))
                        ret['dd_elapsed'] = float(summary[5])
                        ret['dd_rate'] = float(summary[7])
                        ret['dd_units'] = str(summary[8])
                except Exception, e:
                    #catch any exception in the data parsing and show it as info/debug later...
                    tb = self.tester.get_traceback()
                    infobuf = '\n\nCaught exception while processing line:"'+str(line)+'"'
                    infobuf += '\n'+str(tb)+"\n"+str(e)+'\n'
            elapsed = float(time.time()-start)
            ret['test_rate'] = float("{0:.2f}".format(ret['dd_mb'] / elapsed ))
            ret['test_time'] = "{0:.4f}".format(elapsed)
            #Create and format the status output buffer, then print it...
            buf = str(ret['dd_bytes']).ljust(15)
            buf += '|'+str(ret['dd_mb']).center(15)
            buf += '|'+str(ret['dd_gig']).center(8)
            buf += '|'+str(ret['dd_elapsed']).center(10)
            buf += '|'+str(ret['test_time']).center(10)
            buf += '|'+str(str(ret['dd_rate'])+" "+str(ret['dd_units'])).center(12)
            buf += '|'+str(str(ret['test_rate'])+" "+str('MB/s')).center(12)
            buf += '|'+str("F:"+str(ret['dd_full_rec_in'])+" P:"+str(ret['dd_partial_rec_in'])+" ").center(18)
            buf += '|'+str("F:"+str(ret['dd_full_rec_out'])+" P:"+str(ret['dd_partial_rec_out'])).center(18)
            sys.stdout.write("\r\x1b[K"+str(buf))
            sys.stdout.flush()
            time.sleep(poll_interval)
        sys.stdout.write(linediv)
        sys.stdout.flush()
        elapsed = int(time.time()-start)
        if not done:
            #Attempt to kill dd process...
            self.sys('kill '+str(dd_pid))
            raise Exception('dd_monitor timed out before dd cmd completed, elapsed:'+str(elapsed)+'/'+str(timeout))
        else:
            #sync to ensure writes to dev
            self.sys('sync', code=0)
            elapsed = int(time.time()-start)
        #if we have any info from exceptions caught during parsing, print that here...
        if infobuf:
            print infobuf
        #if we didn't transfer any bytes of data, assume the cmd failed and wrote to stderr now in outbuf...
        if not ret['dd_bytes']:
            if out:
                outbuf = "\n".join(out)
            raise Exception('Did not transfer any data using dd cmd:'+str(ddcmd)+"\nstderr: "+str(outbuf))
        self.debug('Done with dd, copied '+str(ret['dd_bytes'])+' over elapsed:'+str(elapsed))
        return ret
    
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
        if overwrite or ( int(self.sys('head -c '+str(length)+ ' '+str(voldev)+' | xargs -0 printf %s | wc -c')[0]) == 0):
            
            self.random_fill_volume(euvolume, srcdev=srcdev, length=length)
        else:
            self.debug("Volume has existing data, skipping random data fill")
        #calculate checksum of euvolume attached device for given length
        md5 = self.md5_attached_euvolume(euvolume, timepergig=timepergig,length=length)
        self.debug("Filled Volume:"+euvolume.id+" dev:"+voldev+" md5:"+md5)
        euvolume.md5 = md5
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
            md5 = self.get_dev_md5(voldev, length,timeout)
            self.debug("Got MD5 for Volume:"+euvolume.id+" dev:"+voldev+" md5:"+md5)
            if updatevol:
                euvolume.md5=md5
                euvolume.md5len=length
        except Exception, e:
            raise Exception("Failed to md5 attached volume: " +str(e))
        return md5
    
    def get_dev_md5(self, devpath, length, timeout=60): 
        self.assertFilePresent(devpath)
        if length == 0:
            md5 = str(self.sys("md5sum "+devpath, timeout=timeout)[0]).split(' ')[0].strip()
        else:
            md5 = str(self.sys("head -c "+str(length)+" "+str(devpath)+" | md5sum")[0]).split(' ')[0].strip()
        return md5
        
    def reboot_instance_and_verify(self,waitconnect=30, timeout=300, connect=True, checkvolstatus=False, pad=5):
        '''
        Attempts to reboot an instance and verify it's state post reboot. 
        waitconnect-optional-integer representing seconds to wait before attempting to connect to instance after reboot
        timeout-optional-integer, seconds. If a connection has failed, this timer is used to determine a retry
        onnect- optional - boolean to indicate whether an ssh session should be established once the expected state has been reached
        checkvolstatus - optional -boolean to be used to check volume status post start up
        '''
        msg=""
        self.debug('Attempting to reboot instance:'+str(self.id)+', check attached volume state first')
        uptime = int(self.sys('cat /proc/uptime')[0].split()[1].split('.')[0])
        elapsed = 0
        start = time.time()
        if checkvolstatus:
            #update the md5sums per volume before reboot
            bad_vols=self.get_unsynced_volumes()
            if bad_vols != []:
                for bv in bad_vols:
                    self.debug(str(self.id)+'Unsynced volume found:'+str(bv.id))
                raise Exception(str(self.id)+"Could not reboot using checkvolstatus flag due to unsync'd volumes")
        self.debug('Rebooting now...')
        self.reboot()
        time.sleep(waitconnect)
        self.connect_to_instance(timeout=timeout)
        elapsed = int(time.time()-start)
        newuptime = int(self.sys('cat /proc/uptime')[0].split()[1].split('.')[0])
        #Check to see if new uptime is at least 'pad' less than before, allowing for some pad 
        if (newuptime - (uptime+elapsed)) > pad:
            raise Exception("Instance uptime does not represent a reboot. Orig:"+str(uptime)+", New:"+str(newuptime)+", elapsed:"+str(elapsed))
        if checkvolstatus:
            badvols= self.get_unsynced_volumes()
            if badvols != []:
                for vol in badvols:
                    msg = msg+"\nVolume:"+vol.id+" Local Dev:"+vol.guestdev
                raise Exception("Missing volumes post reboot:"+str(msg)+"\n")
        self.debug(self.id+" reboot_instance_and_verify Success")
        
        
    def attach_euvolume_list(self,list,intervoldelay=0, timepervol=90, md5len=32):
        '''
        Attempts to attach a list of euvolumes. Due to limitations with KVM and detecting the location/device
        name of the volume as attached on the guest, MD5 sums are used... 
        -If volumes contain an md5 will wait intervoldelay seconds
        before attempting to attach the next volume in the list. 
        -If the next volume in the list does not have an MD5, the next volume will not be attached until
        this volume is detected and an md5sum is populated in the euvolume. 
        
        :param list: List of volumes to be attached, if volumes are not of type euvolume they will be converted
        :param intervoldelay : integer representing seconds between each volume attach attempt
        :param timepervol: time to wait for volume to attach before failing
        :param md5len: length from head of block device to read when calculating md5
        
        '''
        for euvol in list:
            if not isinstance(euvol, EuVolume): # or not euvol.md5:
                list[list.index(euvol)] = EuVolume.make_euvol_from_vol(euvol, self.tester)
        for euvol in list:
            dev = self.get_free_scsi_dev()
            if euvol.md5:
                #Monitor volume to attached, dont write/read head for md5 use existing. Check md5 sum later in get_unsynced_volumes. 
                if (self.tester.attach_volume(self, euvol, dev, pause=10,timeout=timepervol)):
                    self.attached_vols.append(euvol)
                else:
                    raise Exception('attach_euvolume_list: Test Failed to attach volume:'+str(euvol.id))
            else:
                #monitor volume to attached and write unique string to head and record it's md5sum 
                self.attach_euvolume(euvol, dev, timeout=timepervol)
            if intervoldelay:
                time.sleep(intervoldelay)
        start = time.time()
        elapsed = 0 
        badvols = self.get_unsynced_volumes(list, md5length=md5len, timepervol=timepervol, check_md5=True)
        if badvols:
            buf = ""
            for bv in badvols:
                buf += str(bv.id)+","
            raise Exception("Volume(s) were not found on guest:"+str(buf))
        
        
    def get_unsynced_volumes(self,euvol_list=None, md5length=32, timepervol=90,min_polls=2, check_md5=False):
        '''
        Description: Returns list of volumes which are:
        -in a state the cloud believes the vol is no longer attached
        -the attached device has changed, or is not found.
        If all euvols are shown as attached to this instance, and the last known local dev is present and/or a local device is found with matching md5 checksum
        then the list will return 'None' as all volumes are successfully attached and state is in sync. 
        By default this method will iterate through all the known euvolumes attached to this euinstance. 
        A subset can be provided in the list argument 'euvol_list'. 
        Returns a list of euvolumes for which a corresponding guest device could not be found, or the cloud no longer believes is attached. 
         
        :param euvol_list: - optional - euvolume object list. Defaults to all self.attached_vols
        :param md5length: - optional - defaults to the length given in each euvolume. Used to calc md5 checksum of devices
        :param timerpervolume: -optional - time to wait for device to appear, per volume before failing
        :param min_polls: - optional - minimum iterations to check guest devs before failing, despite timeout
        :param check_md5: - optional - find devices by md5 comparision. Default is to only perform this check when virtio_blk is in use.
        '''
        bad_list = []
        vol_list = []
        checked_vdevs = []
        poll_count = 0
        dev_list = self.get_dev_dir()
        found = False

        if euvol_list is not None:
            vol_list.extend(euvol_list)
        else:
            vol_list = self.attached_vols
        self.debug("Checking for volumes whos state is not in sync with our instance's test state...")
        for vol in vol_list:
            #first see if the cloud believes this volume is still attached. 
            try: 
                self.debug("Checking volume:"+str(vol.id))
                if (vol.attach_data.instance_id == self.id): #verify the cloud status is still attached to this instance
                    self.debug("Cloud beleives volume:"+str(vol.id)+" is attached to:"+str(self.id)+", check for guest dev...")
                    found = False
                    elapsed = 0 
                    start = time.time()
                    checked_vdevs = []
                    #loop here for timepervol in case were waiting for a volume to appear in the guest. ie attaching
                    while (not found) and ((elapsed <= timepervol) or (poll_count < min_polls)):
                        try:
                            poll_count += 1
                            #Ugly... :-(
                            #handle virtio and non virtio cases differently (KVM case needs improvement here).
                            if self.virtio_blk or check_md5:
                                self.debug('Checking any new devs for md5:'+str(vol.md5))
                                #Do some detective work to see what device name the previously attached volume is using
                                devlist = self.get_dev_dir()
                                for vdev in devlist:
                                    vdev = "/dev/"+str(vdev)
                                    
                                    #if we've already checked the md5 on this dev no need to re-check it. 
                                    if not vdev in checked_vdevs: 
                                        self.debug('Checking '+str(vdev)+" for match against euvolume:"+str(vol.id))
                                        md5 = self.get_dev_md5(vdev, vol.md5len )
                                        self.debug('comparing '+str(md5)+' vs '+str(vol.md5))
                                        if md5 == vol.md5:
                                            self.debug('Found match at dev:'+str(vdev))
                                            found = True
                                            if (vol.guestdev != vdev ):
                                                self.debug("("+str(vol.id)+")Found dev match. Guest dev changed! Updating from previous:'"+str(vol.guestdev)+"' to:'"+str(vdev)+"'")
                                            else:
                                                self.debug("("+str(vol.id)+")Found dev match. Previous dev:'"+str(vol.guestdev)+"', Current dev:'"+str(vdev)+"'")
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
                        self.debug('Local device for volume not found. Sleeping and checking again...')
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
            if (vol.attach_data.instance_id == self.id) and not ( self.root_device_type == 'ebs' and self.bdm_vol.id != vol.id):
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
            if elapsed % 10 == 0 :
                self.debug(str(self.id)+"wait for stop, in state:"+str(self.state)+",time remaining:"+str(elapsed)+"/"+str(timeout) )
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
            if elapsed % 10 == 0 :
                self.debug(str(self.id)+"wait for start, in state:"+str(self.state)+",time remaining:"+str(elapsed)+"/"+str(timeout) )
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



    def mount_attached_volume(self,
                           volume,
                           mkfs_cmd="mkfs.ext3",
                           mountdir="/mnt",
                           name=None):
        """
        Attempts to mount a block device associated with an attached volume.
        Attempts to mkfs, and mkdir for mount if needed.

        :param volume: euvolume obj
        :param mkfs_cmd: string representing mkfs cmd, defaults to 'mkfs.ext3'
        :param mountdir: dir to mount, defaults to '/mnt'
        :param name: name of dir create within mountdir to mount volume, defaults to volume's id
        :return: string representing path to volume's mounted dir
        """
        dev = volume.guestdev
        name = name or volume.id
        mountdir = mountdir.rstrip("/")+"/"
        if not dev:
            raise Exception(str(volume.id) + ': Volume guest device was not set, is this volume attached?')
        mounted_dir = self.get_volume_mounted_dir(volume)
        if mounted_dir:
            return mounted_dir
        try:
            self.sys('blkid -o value -s TYPE ' + str(dev) + '*', code=0)
        except:
            self.sys(mkfs_cmd + " " + dev, code=0)
        mount_point = mountdir+name
        try:
            self.assertFilePresent(mount_point)
        except:
            self.sys('mkdir -p ' + mount_point, code=0)
        self.sys('mount ' + dev + ' ' + mount_point, code = 0)
        return mount_point





    def get_volume_mounted_dir(self, volume):
        """
        Attempts to fetch the dir/mount point for a given block-guestdev or a euvolume that contains attached guestdev
        information.

        :param volume: attached euvolume
        :param guestdev: local block device path
        :return: string representing path to mounted dir, or None if not found
        """
        mount_dir = None
        guestdev = volume.guestdev
        if not guestdev:
            raise Exception('No guest device found or provided for to check for mounted state')
        try:
            mount_dir = self.sys('mount | grep ' + str(guestdev), code=0)[0].split()[2]
        except Exception, e:
            self.debug('Mount point for ' + str(guestdev) + 'not found:' + str(e))
            return mount_dir
        return mount_dir



    def update_vm_type_info(self):
        self.vmtype_info =  self.tester.get_vm_type_from_zone(self.placement,self.instance_type)
        return self.vmtype_info

    def get_ephemeral_dev(self):
        """
        Attempts to find the block device path on this instance

        :return: string representing path to ephemeral block device
        """
        ephem_name = None
        dev_prefixs = ['s','v','xd','xvd']
        if not self.root_device_type == 'ebs':
            try:
                self.assertFilePresent('/dev/' + str(self.rootfs_device))
                return self.rootfs_device
            except:
                ephem_name = 'da'
        else:
            ephem_name = 'db'
        devs = self.get_dev_dir()
        for prefix in dev_prefixs:
            if str(prefix+ephem_name) in devs:
                return str(prefix+ephem_name)
        raise Exception('Could not find ephemeral device?')

    def get_blockdev_size_in_bytes(self,devpath):
        bytes = self.sys('blockdev --getsize64 ' + str(devpath), code=0)[0]
        return int(bytes)


    def check_ephemeral_against_vmtype(self):
        gb = 1073741824
        size = self.vmtype_info.disk
        ephemeral_dev = self.get_ephemeral_dev()
        block_size = self.get_blockdev_size_in_bytes('/dev/' + ephemeral_dev)
        gbs = block_size / gb
        self.debug('Ephemeral check: ephem_dev:'
                   + str(ephemeral_dev)
                   + ", bytes:"
                   + str(block_size)
                   + ", gbs:"
                   + str(gbs)
                   + ", vmtype size:"
                   + str(size))
        if gbs != size:
            raise Exception('Ephemeral check failed. ' + str(ephemeral_dev) + ' Blocksize: '
                            + str(gbs) + "gb (" + str(block_size) + "bytes)"
                            + ' != vmtype size:' +str(size) + "gb")
        else:
            self.debug('check_ephemeral_against_vmtype, passed')


    def get_memtotal_in_mb(self):
        kb_to_mb = 1024
        return long(self.sys('cat /proc/meminfo | grep MemTotal',code=0)[0].split()[1]) / kb_to_mb

    def check_ram_against_vmtype(self, pad=32):
        total_ram = self.get_memtotal_in_mb()
        self.debug('Ram check: vm_ram:' + str(self.vmtype_info.ram)
                   + "mb vs memtotal:" + str(total_ram)
                   + "mb. Diff:" + str(self.vmtype_info.ram - total_ram)
                   + "mb, pad:" + str(pad) + "mb")
        if not ((self.vmtype_info.ram - total_ram) <= pad):
            raise Exception('Ram check failed. vm_ram:' + str(self.vmtype_info.ram)
                            + " vs memtotal:" + str(total_ram) + ". Diff is greater than allowed pad:" + str(pad) + "mb")
        else:
            self.debug('check_ram_against_vmtype, passed')


    
        
        
        
        
            
            
                
