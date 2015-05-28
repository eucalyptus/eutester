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
@author: clarkmatthew
extension of the boto instance class, with added convenience methods + objects
Add common instance test routines to this class

Examples:
from eucaops import Eucaops
from eutester.windows_instance import WinInstance
tester = Eucaops(credpath='eucarc-10.111.5.80-eucalyptus-admin')
wins = WinInstance.make_euinstance_from_instance(tester.get_instances(idstring='i-89E13DA8')[0], tester=tester, keypair='test')
vol = tester.get_volume(status='available', zone=wins.placement)
wins.attach_volume(vol)



'''
from boto.ec2.instance import Instance
from eutester import Eutester
#from eucaops import Eucaops
from eutester.euvolume import EuVolume
from eutester import eulogger
from eutester.euinstance import EuInstance
from eutester.taggedresource import TaggedResource
from boto.ec2.instance import InstanceState
from boto.ec2.networkinterface import NetworkInterface
from boto.exception import EC2ResponseError
from random import randint
from datetime import datetime
from prettytable import PrettyTable
import winrm_connection
import socket
import sys
import os
import re
import time
import copy
import types
import operator
get_line = Eutester.get_line


class WinInstanceDiskType():
    gigabyte = 1073741824
    megabyte = 1048576
    def __init__(self, win_instance, wmic_dict):
        self.check_dict_requires(wmic_dict)
        self.__dict__ =  self.convert_numbers_in_dict(copy.copy(wmic_dict))
        self.win_instance = win_instance
        self.size_in_gb = self.get_size_in_gb()
        self.size_in_mb = self.get_size_in_mb()
        self.size = long(self.size or 0)
        self.last_updated = time.time()
        self.setup()

    def setup(self):
        raise Exception('Not Implemented')

    def check_dict_requires(self, wmic_dict):
        raise Exception('Not Implemented')

    def convert_numbers_in_dict(self, dict):
        #convert strings representing numbers to ints
        for key in dict:
            value = str(dict[key])
            if (re.search("\S", str(dict[key])) and not re.search("\D", str(dict[key]))):
                dict[key] = long(dict[key])
        return dict

    def get_partition_ids(self):
        retlist = []
        for part in self.disk_partitions:
            retlist.append(part.deviceid)
        return retlist

    def get_logicaldisk_ids(self):
        retlist = []
        for part in self.disk_partitions:
            retlist.extend(part.get_logicaldisk_ids())
        return retlist

    def get_size_in_gb(self):
        '''
        Attempts to convert self.size from bytes to gigabytes as well as round up > .99 to account for a differences
        in how the size is represented
        '''
        self.size = int(self.size or 0)
        gigs = self.size / self.gigabyte
        if (self.size % self.gigabyte) /float(self.gigabyte) > .99:
            gigs += 1
        return gigs

    def get_size_in_mb(self):
        '''
        Attempts to convert self.size from bytes to gigabytes as well as round up > .99 to account for a differences
        in how the size is represented
        '''
        self.size = int(self.size or 0)
        mb = self.size / self.megabyte
        if (self.size % self.megabyte) /float(self.megabyte) > .99:
            mb += 1
        return mb

    def print_self(self):
        self.get_summary(printmethod=self.win_instance.debug)

    def get_summary(self, printheader=True, printmethod=None):
        raise Exception('Method not implemented')


    def print_self_full(self, printmethod=None):
        '''
        formats and prints self.dict
        '''
        self.win_instance.print_dict(dict=self.__dict__, printmethod=printmethod)



class WinInstanceDiskDrive(WinInstanceDiskType):

    def setup(self):
        if not hasattr(self, 'serialnumber'):
            self.serialnumber = ''
        if not hasattr(self, 'caption'):
            self.caption = ''
            if hasattr(self, 'model'):
                self.caption = self.model
            else:
                self.model = self.caption
        self.cygwin_scsi_drive = self.win_instance.get_cygwin_scsi_dev_for_windows_drive(windisk=self)
        self.update_ebs_info()
        self.disk_partitions = []

    def check_dict_requires(self, wmic_dict):
        if not ('deviceid' in wmic_dict and
                'size' in wmic_dict and
                ('caption' in wmic_dict  or 'model in wmic_dict') and
                'index' in wmic_dict):
            raise Exception('wmic_dict passed does not contain needed attributes; deviceid, size, caption, and index')


    def get_partition_ids(self):
        retlist = []
        for part in self.disk_partitions:
            retlist.append(part.deviceid)
        return retlist

    def get_logicaldisk_ids(self):
        retlist = []
        for part in self.disk_partitions:
            retlist.extend(part.get_logicaldisk_ids())
        return retlist

    def update_md5_info_from_ebs(self):
        self.md5 = None
        self.md5len = None
        for vol in self.win_instance.attached_vols:
            if vol.guestdev == self.deviceid:
                if not vol.md5:
                    vol.md5len = 1024
                    vol.md5 = self.win_instance.get_dev_md5(self.cygwin_scsi_drive, vol.md5len)
                self.md5 = vol.md5
                self.md5len = vol.md5len
                break

    def update_ebs_info_from_serial_number(self):
        '''
        Attempts to parse the serial number field from an EBS volume and find the correlating ebs volume
        example format: vol-81C13EA4-dev-sdg
        '''
        if re.match("^vol-", self.serialnumber):
            split = self.serialnumber.split('-')
            self.ebs_volume = str(split[0]) + "-" + str(split[1])
            self.ebs_cloud_dev = "/" + str(split[2]) + "/" + str(split[3])
        else:
            self.ebs_volume = ''
            self.ebs_cloud_dev = ''


    def update_ebs_info(self):
        self.update_ebs_info_from_serial_number()
        if not self.ebs_volume:
            if self.index == 0 and self.win_instance.root_device_type == 'ebs':
                bdm = self.win_instance.block_device_mapping[self.win_instance.root_device_name]
                self.ebs_volume = bdm.volume_id
            else:
                for vol in self.win_instance.attached_vols:
                    if vol.guestdev == self.deviceid:
                        self.ebs_volume = vol.id
                        break
        if not self.ebs_cloud_dev and self.ebs_volume:
            volume = self.win_instance.tester.get_volume(volume_id=self.ebs_volume)
            if hasattr(volume,'attach_data') and volume.attach_data:
                self.ebs_cloud_dev = volume.attach_data.device
        self.update_md5_info_from_ebs()




    def get_summary(self, printheader=True, printmethod=None):
        buf = ""
        deviceid = 20
        size = 16
        sizegb = 7
        ebsvol = 12
        serialnumber = 24
        caption = 36
        part_count = 6
        logical_ids = 8
        cygdrive = 10
        md5 = 32
        header = "DISKDRIVE DEV ID".center(deviceid) + "|" + \
                 "SIZE B".center(size) + "|" + \
                 "SIZE GB".center(sizegb) + "|" + \
                 "EBS VOL".center(ebsvol) + "|" + \
                 "CAPTION".center(caption) + "|" + \
                 "PARTS".center(part_count) + "|" + \
                 "LOGICAL".center(logical_ids) + "|" + \
                 "CYGDRIVE".center(cygdrive) + "|" + \
                 "SERIAL NUMBER".center(serialnumber) + "|" + \
                 "MD5 CHECK SUM".center(md5) + "|"

        summary = str(self.deviceid).center(deviceid) + "|" + \
                  str(self.size).center(size) + "|" + \
                  str(self.size_in_gb).center(sizegb) + "|" + \
                  str(self.ebs_volume).center(ebsvol) + "|" + \
                  str(self.caption).center(caption) + "|" + \
                  str(self.partitions).center(part_count) + "|" + \
                  str(",".join(str(x) for x in self.get_logicaldisk_ids())).center(logical_ids) + "|" + \
                  str(self.cygwin_scsi_drive).center(cygdrive) + "|" + \
                  str(self.serialnumber).center(serialnumber) + "|" + \
                  str(self.md5).center(md5) + "|"

        length = len(header)
        if len(summary) > length:
            length = len(summary)
        line = get_line(length)
        if printheader:
            buf += line + header + line
        buf += summary + line
        if printmethod:
            printmethod(buf)
        return buf


class WinInstanceDiskPartition(WinInstanceDiskType):

    def setup(self):
        #self.cygwin_scsi_drive = self.win_instance.get_cygwin_scsi_dev_for_windows_drive(drive_id=self.deviceid)
        self.logicaldisks = []
        #Set values in case 'brief' was used when fetching partitions
        if not hasattr(self,'deviceid'):
            self.deviceid = self.name
        if not hasattr(self,'bootable'):
            self.bootable = self.bootpartition
        if not hasattr(self,'diskindex'):
            self.diskindex = self.get_disk_index_from_name()

    def check_dict_requires(self, wmic_dict):
        if not ('name' in wmic_dict and
                'size' in wmic_dict and
                'bootpartition' in wmic_dict and
                'index' in wmic_dict):
            raise Exception('wmic_dict passed does not contain needed attributes; deviceid, size, index and bootable')


    def get_disk_index_from_name(self):
        diskindex = None
        diskindexstring = self.name.split(',')[0]
        if re.search('disk', diskindexstring, re.IGNORECASE):
            diskindex = int(diskindexstring.split('#')[1])
        return diskindex

    def get_logicaldisk_ids(self):
        retlist = []
        for disk in self.logicaldisks:
            retlist.append(disk.deviceid)
        return retlist

    def get_summary(self, printheader=True, printmethod=None):
        buf = ""
        deviceid = 24
        size = 16
        sizegb = 12
        sizemb = 12
        bootable = 10
        header = "PARTITION DEV ID".center(deviceid) + "|" + \
                 "SIZE B".center(size) + "|" + \
                 "SIZE GB".center(sizegb) + "|" + \
                 "SIZE MB".center(sizemb) + "|" + \
                 "BOOTABLE".center(bootable) + "|"

        summary = str(self.deviceid).center(deviceid) + "|" + \
                  str(self.size).center(size) + "|" + \
                  str(self.size_in_gb).center(sizegb) + "|" + \
                  str(self.size_in_mb).center(sizemb) + "|" + \
                  str(self.bootable).center(bootable) + "|"

        length = len(header)
        if len(summary) > length:
            length = len(summary)
        line = get_line(length)
        if printheader:
            buf += line + header + line
        buf += summary + line
        if printmethod:
            printmethod(buf)
        return buf


class WinInstanceLogicalDisk(WinInstanceDiskType):

    def setup(self):
        self.cygwin_scsi_drive = self.win_instance.get_cygwin_scsi_dev_for_windows_drive(windisk=self)
        self.partition = None

    def check_dict_requires(self, wmic_dict):
        if not ('deviceid' in wmic_dict and
                'size' in wmic_dict and
                'description' in wmic_dict and
                'freespace' in wmic_dict and
                'filesystem' in wmic_dict):
            raise Exception('wmic_dict passed does not contain needed attributes; deviceid, size, and description')

    def get_summary(self, printheader=True, printmethod=None):
        buf = ""
        deviceid = 24
        size = 16
        freespace = 16
        filesystem = 24
        description = 30
        cygdrive = 10
        header = "LOGICAL DEV ID".center(deviceid) + "|" + \
                 "SIZE".center(size) + "|" + \
                 "FREE SPACE".center(freespace) + "|" + \
                 "FILE SYSTEM".center(filesystem) + "|" + \
                 "DESCRIPTION".center(description) + "|" + \
                 "CYGDRIVE".center(cygdrive) + "|"
        summary = str(self.deviceid).center(deviceid) + "|" + \
                  str(self.size).center(size) + "|" + \
                  str(self.freespace).center(freespace) + "|" + \
                  str(self.filesystem).center(filesystem) + "|" + \
                  str(self.description).center(description) + "|" + \
                  str(self.cygwin_scsi_drive).center(cygdrive) + "|"
        length = len(header)
        if len(summary) > length:
            length = len(summary)
        line = get_line(length)
        if printheader:
            buf += line + header + line
        buf += summary + line
        if printmethod:
            printmethod(buf)
        return buf


class WinInstance(EuInstance, TaggedResource):
    gigabyte = 1073741824
    megabyte = 1048576

    @classmethod
    def make_euinstance_from_instance(cls,
                                      instance,
                                      tester,
                                      debugmethod = None,
                                      keypair=None,
                                      keypath=None,
                                      password=None,
                                      username="Administrator",
                                      auto_connect = True,
                                      verbose=True,
                                      timeout=120,
                                      private_addressing = False,
                                      reservation = None,
                                      cmdstart=None,
                                      try_non_root_exec=True,
                                      winrm_port='5985',
                                      winrm_protocol='http',
                                      rdp_port='3389',
                                      rootfs_device = "sda",
                                      block_device_prefix = "sd",
                                      bdm_root_vol = None,
                                      virtio_blk = True,
                                      cygwin_path = None,
                                      disk_update_interval=10,
                                      retry=2,
                                      brief=False
                                      ):
        '''
        Primary constructor for this class. Note: to avoid an ssh session within this method, provide keys, username/pass later.
        Arguments:
        instance - mandatory- a Boto instance object used to build this euinstance object
        keypair - optional- a boto keypair object used for creating ssh connection to the instance
        username - optional- string used to create ssh connection as an alternative to keypair
        password - optional- string used to create ssh connection to this instance as an alternative to keypair
        exec_password -optional -string used for su or sudo where prompted for password, will default to 'password'
        auto_connect -optional -boolean, if True will attempt to automatically create an ssh session for this instance
        try_non_root_exec -optional -boolean, if True will attempt to use sudo if available else su -c to execute privileged commands
        timeout - optional- integer used for ssh connection timeout
        debugmethod - optional - method, used for debug output
        verbose - optional - boolean to determine if debug is to be printed using debug()
        retry - optional - integer, ssh connection attempts for non-authentication failures
        '''
        newins = WinInstance(instance.connection)
        newins.__dict__ = instance.__dict__
        newins.tester = tester
        newins.winrm_port = winrm_port
        newins.rdp_port = rdp_port
        newins.bdm_root_vol = None
        newins.winrm_protocol = winrm_protocol
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
            newins.keypath = keypath or os.getcwd() + "/" + keyname + ".pem"
        newins.keypair = keypair
        newins.password = password
        newins.username = username
        newins.verbose = verbose
        newins.attached_vols=[]
        newins.timeout = timeout
        newins.virtio_blk  = virtio_blk
        newins.disk_update_interval = disk_update_interval
        newins.retry = retry
        newins.brief = brief
        newins.rootfs_device =  rootfs_device
        newins.block_device_prefix = block_device_prefix
        newins.private_addressing = private_addressing
        newins.reservation = reservation or newins.get_reservation()
        if newins.reservation:
            newins.security_groups = newins.tester.get_instance_security_groups(newins)
        else:
            newins.security_groups = None
        newins.laststate = newins.state
        newins.cmdstart = cmdstart
        newins.auto_connect = auto_connect
        newins.set_last_status()
        newins.update_vm_type_info()
        newins.cygwin_path = cygwin_path
        newins.system_info = None
        newins.diskdrives = []
        newins.disk_partitions = []
        newins.logicaldisks = []
        newins.cygwin_dev_map  = {}
        #newins.set_block_device_prefix()
        if newins.root_device_type == 'ebs':
            try:
                volume = newins.tester.get_volume(volume_id = newins.block_device_mapping.get(newins.root_device_name).volume_id)
                newins.bdm_root_vol = EuVolume.make_euvol_from_vol(volume, tester=newins.tester,cmdstart=newins.cmdstart)
            except:pass
        newins.winrm = None
        if newins.auto_connect and newins.state == 'running':
            newins.connect_to_instance(timeout=timeout)
        return newins

    def update(self, validate=False, dry_run=False,
               err_state='terminated', err_code=-1):
        ret = None
        tb = ""
        retries = 2
        for x in xrange(0, retries):
            try:
                #send with validation True, fail later...
                ret = super(WinInstance, self).update(validate=True,
                                                      dry_run=dry_run)
                break
            except ValueError:
                if validate:
                    raise
                tb = self.tester.get_traceback()
                self.debug('Failed to update instance. Attempt:{0}/{1}'
                           .format(x, retries))
        if not ret:
            failmsg = 'Failed to update instance. Instance may no longer ' \
                      'be present on system"{0}"'.format(self.id)
            self.debug('{0}\n{1}'.format(tb, failmsg))
            self.debug('{0} setting fake state to:"{1}"'.format(self.id,
                                                                err_state))
            state = InstanceState(name=err_state, code=err_code)
            self._state = state
            ret = self.state
        self.set_last_status()
        return ret


    @property
    def age(self):
        launchtime = self.tester.get_datetime_from_resource_string(self.launch_time)
        #return the elapsed time in seconds
        return (time.mktime(datetime.utcnow().utctimetuple()) -
                time.mktime(launchtime.utctimetuple()))

    def update_vm_type_info(self):
        self.vmtype_info =  self.tester.get_vm_type_from_zone(self.placement,self.instance_type)
        return self.vmtype_info


    def set_last_status(self,status=None):
        self.laststate = self.state
        self.laststatetime = time.time()
        self.age_at_state = self.tester.get_instance_time_launched(self)
        #Also record age from user's perspective, ie when they issued the run instance request (if this is available)
        if self.cmdstart:
            self.age_from_run_cmd = "{0:.2f}".format(time.time() - self.cmdstart)
        else:
            self.age_from_run_cmd = None

    def print_dict(self, dict=None, printmethod=None):
        '''
        formats and prints
        '''
        printmethod = printmethod or self.debug
        buf = "\n"
        dict = dict or self.__dict__
        longest_key = 0
        for key in dict:
            if len(key) > longest_key:
                longest_key = len(key)
        for key in dict:
            buf += str(key).ljust(longest_key) + " -----> :" + str(dict[key]) + "\n"
        printmethod(buf)

    def get_password(self,
                     private_key_path=None,
                     key=None,
                     dir=None,
                     exten=".pem",
                     encoded=True,
                     force_update=False):
        '''
        :param private_key_path: private key file used to decrypt password
        :param key: name of private key
        :param dir: Path to private key
        :param exten: extension of private key
        :param encoded: boolean of whether string returned from server is
                        Base64 encoded
        :return: decrypted password
        '''
        if self.password is None or force_update:
            self.password = self.tester.get_windows_instance_password(
                self,
                private_key_path=private_key_path,
                key=key,
                dir=dir,
                exten=exten,
                encoded=encoded)
        return self.password


    def reset_ssh_connection(self, timeout=None):
        # todo: Remove ssh reference from this method, use something like
        # reset_instance_connection, etc..
        self.debug('Note ssh not implemented at this time, using winrm for '
                   'shell access instead...')
        return self.reset_winrm_connection(timeout=timeout)

    def reset_winrm_connection(self, timeout=None, force=False):
        # todo:
        timeout = timeout or self.timeout
        self.debug('reset_winrm_connection for:'+str(self.id))
        self.get_password(force_update=True)
        if self.username is None or self.password is None:
            #Allow but warn here as this may be a valid negative test
            self.debug('Warning username and/or password were None in '
                       'winrm connnection?')
        # Create a new winrm interface if this is a new instance or
        # an attribute has changed...
        try:
            #Check the port in order to provide debug if the connection fails
            self.test_port_status(port=self.winrm_port, ip=self.ip_address)
        except:pass
        if force or not (self.winrm and \
                         self.winrm.hostname == self.ip_address and \
                         self.winrm.username == self.username and \
                         self.winrm.password == self.password):
            if self.winrm:
                self.winrm.close_shell()
            self.winrm = winrm_connection.Winrm_Connection(
                hostname = self.ip_address,
                username = self.username,
                password = self.password,
                port = self.winrm_port,
                protocol = self.winrm_protocol,
                debug_method = self.debug,
                verbose=True
                )


    def get_reservation(self):
        res = None
        try:
            res = self.tester.get_reservation_for_instance(self)
        except Exception, e:
            self.update()
            self.debug('Could not get reservation for instance in state:' +
                       str(self.state) + ", err:" + str(e))
        return res


    def connect_to_instance(self, wait_for_boot=180, timeout=120):
        '''
        Attempts to connect to an instance via ssh.
        :params wait_for_boot: time to wait, allowing guest to boot before
                               attempting to poll for ports active status
        :params timeout: -optional - time in seconds to wait when polling
                         port(s) status(s) before failure

        '''
        self.debug("{0}connect_to_instance starting.\nwait_for_boot:{1} "
                   "seconds\ntimeout from boot:{2}{3}"
                   .format(get_line(), wait_for_boot, timeout, get_line()))
        try:
            self.poll_for_port_status_with_boot_delay(waitforboot=wait_for_boot,
                                                      timeout=timeout)
        except Exception, e:
            self.debug('Warning failed to poll port status:' + str(e))
        self.debug("Attempting to create connection to instance:" + self.id)
        attempts = 0
        start = time.time()
        elapsed = 0
        if self.winrm is not None:
            self.winrm.close_shell()
        self.winrm = None
        while (elapsed < timeout):
            attempts += 1
            try:
                self.update()
                self.reset_winrm_connection()
                self.debug('Try some sys...')
                self.sys("whoami")
            except Exception, se:
                tb = self.tester.get_traceback()
                self.debug('Caught exception attempting to connect '
                           'winrm shell:\n'+ str(tb) + str(se))
                elapsed = int(time.time()-start)
                self.debug('connect_to_instance: Attempts:' + str(attempts) +
                           ', elapsed:'+str(elapsed)+'/'+str(timeout))
                if self.winrm is not None:
                    self.winrm.close_shell()
                    self.winrm = None
                time.sleep(5)
                pass
            else:
                break
        elapsed = int(time.time()-start)
        if self.winrm is None:
            self.get_connection_debug()
            raise RuntimeError(str(self.id) +
                               ":Failed establishing management connection to "
                               "instance, elapsed:" + str(elapsed) +
                               "/" + str(timeout))
        self.debug('Connect_to_instance updating attached volumes/disk '
                   'info for vols: ' + str(self.attached_vols))
        if self.brief:
            self.update_system_info()
        else:
            self.update_system_and_disk_info()
            self.init_attached_volumes()
        self.debug("{0}connect_to_instance completed{1}"
                   .format(get_line(), get_line()))

    def get_connection_debug(self):
        # Add network debug/diag info here...
        # First show arp cache from local machine
        # todo Consider getting info from relevant euca components:
        # - iptables info
        # - route info
        # - instance xml
        try:
            # Show local ARP info...
            arp_out = "\nLocal ARP cache for instance ip: " \
                      + str(self.ip_address) + "\n"
            arp_fd = os.popen('arp ' + str(self.ip_address))
            for line in arp_fd:
                arp_out += line
            self.debug(arp_out)
        except Exception as AE:
            self.log.debug('Failed to get arp info:' + str(AE))
        try:
            self.tester.get_console_output(self)
        except Exception as CE:
            self.log.debug('Failed to get console output:' + str(CE))

    def update_root_device_diskdrive(self):
        if not self.root_device_type == 'ebs':
            return
        for disk in self.diskdrives:
            if disk.index == 0:
                if disk.ebs_volume:
                    for vol in self.attached_vols:
                        if vol.id == disk.ebs_volume:
                            if not disk.md5:
                                disk.update_md5_info_from_ebs()
                            return
                    volume = self.tester.get_volume(volume_id=disk.ebs_volume)
                    if not isinstance(volume, EuVolume):
                        volume = EuVolume.make_euvol_from_vol(volume, self.tester)
                    volume.guestdev = disk.deviceid
                    volume.md5len = 1024
                    volume.md5 = self.get_dev_md5(disk.cygwin_scsi_drive, volume.md5len)
                    if not self.get_volume_from_attached_list_by_id(volume.id):
                        self.debug("{0} updating with root vol:{1}{2}"
                                   .format(get_line(),
                                           volume.id,
                                           get_line()))
                        self.attached_vols.append(volume)
                    disk.update_md5_info_from_ebs()
                    return

    def get_volume_from_attached_list_by_id(self, volume_id):
        for vol in self.attached_vols:
            if vol.id == volume_id:
                return vol


    def update_system_and_disk_info(self):
        try:
            self.update_system_info()
        except Exception, sie:
            tb = self.tester.get_traceback()
            self.debug(str(tb) + "\nError updating system info:" + str(sie))
        try:
            self.update_disk_info()
            self.update_root_device_diskdrive()
            self.print_partition_summary()
            self.print_logicaldisk_summary()
            self.print_diskdrive_summary()
        except Exception, ude:
            tb = self.tester.get_traceback()
            self.debug(str(tb) + "\nError updating disk info:" + str(ude))


    def has_sudo(self):
        return False


    def debug(self,msg,traceback=1,method=None,frame=False):
        '''
        Used to print debug, defaults to print() but over ridden by self.debugmethod if not None
        msg - mandatory -string, message to be printed
        '''
        if ( self.verbose is True ):
            self.debugmethod(msg)

    def sys(self, cmd, verbose=True, code=None, include_stderr=False, enable_debug=False, timeout=None):
        '''
        Issues a command against the ssh connection to this instance
        Returns a list of the lines from stdout+stderr as a result of the command
        cmd - mandatory - string, the command to be executed
        verbose - optional - boolean flag to enable debug
        timeout - optional - command timeout in seconds
        '''
        if (self.winrm is None):
            raise Exception("WinInstance winrm connection is None")
        return self.winrm.sys(command=cmd, include_stderr=include_stderr, timeout=timeout, verbose=verbose, code=code)




    def test_rdp_port_status(self, ip=None, port=3389, timeout=10):
        '''
        Description: Attempts to test that the host is accepting tcp connections to the RDP port
        '''
        ip = ip or self.ip_address
        return self.test_port_status(ip=ip, port=port, timeout=timeout)


    def test_port_status(self, port, ip=None, timeout=5, tcp=True, verbose=True):
        ip = ip or self.ip_address
        return self.tester.test_port_status(ip, int(port), timeout=timeout, tcp=tcp, verbose=verbose)

    def poll_for_port_status_with_boot_delay(self, interval=15, ports=[], socktimeout=5,timeout=180, waitforboot=300):
        '''
        Make sure some time has passed before we test on the guest side before running guest test...

        '''
        launch_seconds = self.tester.get_instance_time_launched(self)
        sleeptime =  0 if launch_seconds > waitforboot else (waitforboot - launch_seconds)
        self.debug("Instance was launched "+str(launch_seconds)+" seconds ago, waiting:"+str(sleeptime)+" for instance to boot")
        time.sleep(sleeptime)
        return self.poll_for_ports_status(ports,
                                          ip=self.ip_address,
                                          interval=interval,
                                          socktimeout=socktimeout,
                                          timeout=timeout)

    def wait_for_time_since_launch(self,waitforboot=420):
        '''
        When using larger instance store images, this can allow for the delays caused by image size/transfer.
        '''
        boot_seconds = self.tester.get_instance_time_launched(self)
        sleeptime =  0 if boot_seconds > waitforboot else (waitforboot - boot_seconds)
        self.debug("Instance was launched "+str(boot_seconds)+"/"+str(waitforboot) + " seconds ago, waiting:"+str(sleeptime)+" for instance to boot")
        start = time.time()
        elapsed = 0
        print "Waiting for Windows to fully boot:",
        while elapsed < sleeptime:
            print "Waiting for Windows to fully boot:"+str(sleeptime-elapsed),
            time.sleep(5)
            elapsed=int(time.time()-start)
        self.debug("test_wait_for_instance_boot: done waiting, instance up for "+str(waitforboot)+" seconds")

    def poll_for_ports_status(self, ports=[], ip=None, interval=10, socktimeout=5, timeout=180):
        ip = ip or self.ip_address
        ports = ports or [self.rdp_port, self.winrm_port]
        start = time.time()
        elapsed = 0
        attempt = 0
        while elapsed < timeout:
            attempt +=1
            self.debug('test_poll_for_ports_status, ports: ' + ",".join(str(x) for x in ports) + ", attempt:"  + str(attempt))
            for port in ports:
                if elapsed < timeout:
                    try:
                        self.debug('Trying ip:port:' + str(self.ip_address) + ':' + str(port) + ", elapsed:" + str(elapsed))
                        self.test_port_status(ip=ip, port=int(port), timeout=5)
                        return
                    except socket.error, se:
                        self.debug('test_ports_status failed socket error:'+str(se[0]))
                        #handle specific errors here, for now just for debug...
                        ecode=se[0]
                        if ecode == socket.errno.ETIMEDOUT or ecode == "timed out":
                            self.debug("test_poll_for_ports_status: Connect "+str(ip)+":" +str(port)+ " timed out retrying. Time remaining("+str(timeout-elapsed)+")")
                    except Exception, e:
                        tb = self.tester.get_traceback()
                        self.debug(tb)
                        self.debug('test_poll_for_ports_status:'+str(ip)+':'+str(port)+' FAILED after attempts:'+str(attempt)+', elapsed:'+str(elapsed)+', err:'+str(e) )
            elapsed = int(time.time() -start)
            if elapsed < timeout:
                time.sleep(interval)

        raise Exception('test_poll_for_ports_status:'+str(ip)+':'+str(port)+' FAILED after attempts:'+str(attempt)+', elapsed:'+str(elapsed)+' seconds')

    def init_attached_volumes(self):
        self.debug('init_attahced_volumes... attached_vols: ' + str(self.attached_vols))
        syncdict = self.sync_attached_volumes_with_clouds_view()
        if syncdict['errors']:
            errmsg = 'Errors syncing guest volumes with cloud at init:' + ",".join(str(e) for e in syncdict['errors'])
            errmsg += 'Failed to sync guest volumes with cloud at init:' + ",".join(str(x) for x in syncdict['badvols'])
            self.debug(errmsg)
            time.sleep(60)
            raise Exception(errmsg)

    def sync_attached_volumes_with_clouds_view(self):
        self.debug(get_line() +
                   "Starting sync_attached_volumes_with_clouds_view"
                   + get_line() )
        badvols = []
        errors = []
        ret = {'errors':errors, 'badvols':badvols}
        #Get a list of volumes that the cloud believes are currently attached
        cloud_volumes = self.tester.get_volumes(attached_instance=self.id)
        #Make a copy of a list of volumes this instance thinks are currenlty attached
        locallist = copy.copy(self.attached_vols)
        self.debug('Cloud list:' + str(cloud_volumes))
        self.debug('Local list:' + str(locallist))

        for vol in cloud_volumes:
            for local_vol in locallist:
                if local_vol.id == vol.id:
                    locallist.remove(local_vol)
            if not isinstance(vol, EuVolume):
                vol = EuVolume.make_euvol_from_vol(vol, self.tester)
            try:
                self.update_volume_guest_info(volume=vol)
            except Exception, e:
                badvols.append(vol)
                errors.append(vol.id + ' Error syncing with cloud:' + str (e) + '. \n')
        for local_vol in locallist:
            badvols.append(local_vol)
            errors.append(local_vol.id + ' Error unattached volume found in guests attach list. \n')
        self.debug(get_line() +
                   "Finishing sync_attached_volumes_with_clouds_view"
                   + get_line() )
        return ret



    def update_system_info(self):
        '''
        Gather basic system info for this windows instance object and store in self.system_info
        Example:
        # print wins.system_info.OS_NAME
          'Microsoft Windows 7 Professional'
        '''
        currentkey = None
        swap = re.compile('([!@#$%^&*. ])')
        info = self.sys('systeminfo')
        if self.system_info:
            system_info = self.system_info
        else:
            system_info = type('obj', (object,),{})
        if info:
            for line in info:
                if re.match("^\w.+:", line):
                    linevals = line.split(':')
                    currentkey = linevals.pop(0)
                    #clean up the key string...
                    currentkey = re.sub('[()]', '', currentkey)
                    currentkey = re.sub(swap, '_', currentkey)
                    currentkey = currentkey.lower()
                    value = ":".join(str(x) for x in linevals) or ""
                    setattr(system_info, currentkey, str(value).strip())
                elif currentkey:
                    #this is an additional value to our previous key
                    prev_value = getattr(system_info, currentkey)
                    if not isinstance(prev_value, types.ListType):
                        updated_value = [prev_value]
                    updated_value.append(str(line).strip())
                    setattr(system_info, currentkey, updated_value)
        self.system_info = system_info

    def get_cygwin_path(self, prefix="c:\\"):
        if self.cygwin_path:
            return self.cygwin_path
        path = None
        self.debug('Trying to find cygwin path...')
        out = self.sys('dir ' + str(prefix) + ' /B')
        for line in out:
            if re.search('cygwin', line):
                path = str(prefix) + str(line.strip()) + "\\"
                self.cygwin_path = path
                break
        return path

    def cygwin_curl(self, url, connect_timeout=30):
        cygpath = self.get_cygwin_path()
        if cygpath is None:
            raise Exception('Could not find cygwin path on guest for curl?')
        curl = cygpath + 'bin\curl.exe --connect-timeout ' + str(connect_timeout) + ' '
        return self.sys(curl + str(url), code=0, timeout=connect_timeout)



    def get_metadata(self, element_path='', prefix='latest/meta-data/', use_cygwin=True):
        """Return the lines of metadata from the element path provided"""
        ### If i can reach the metadata service ip use it to get metadata otherwise try the clc directly
        try:
            if use_cygwin:
                return self.cygwin_curl("http://169.254.169.254/"+str(prefix)+str(element_path), connect_timeout=10)
            else:
                return self.sys("curl --connect-timeout 10 http://169.254.169.254/"+str(prefix)+str(element_path), code=0)
        except:
            if use_cygwin:
                return self.cygwin_curl("http://" + self.tester.get_ec2_ip()  + ":8773/"+str(prefix) + str(element_path))
            else:
                return self.sys("curl http://" + self.tester.get_ec2_ip()  + ":8773/"+str(prefix) + str(element_path), code=0)


    def print_diskdrive_summary(self,printmethod=None):
        printmethod = printmethod or self.debug
        if not self.diskdrives:
            printmethod('No disk drives to print?')
            return
        disklist = copy.copy(self.diskdrives)
        buf = (disklist.pop()).get_summary()
        for disk in disklist:
            buf += disk.get_summary(printheader=False)
        printmethod(buf)

    def print_partition_summary(self,printmethod=None):
        printmethod = printmethod or self.debug
        if not self.disk_partitions:
            printmethod('No disk partitions to print?')
            return
        partlist = copy.copy(self.disk_partitions)
        buf = (partlist.pop()).get_summary()
        for part in partlist:
            buf += part.get_summary(printheader=False)
        printmethod(buf)

    def print_logicaldisk_summary(self,printmethod=None):
        printmethod = printmethod or self.debug
        if not self.logicaldisks:
            printmethod('No disk disk_partitions to print?')
            return
        disklist = copy.copy(self.logicaldisks)
        buf = (disklist.pop()).get_summary()
        for disk in disklist:
            buf += disk.get_summary(printheader=False)
        printmethod(buf)


    def update_disk_info(self , forceupdate=False):
        if self.diskdrives:
            if not forceupdate and (time.time() - self.diskdrives[0].last_updated) <= self.disk_update_interval:
                return
        self.debug('Fetching updated disk info...')
        self.diskdrives = []
        self.disk_partitions = []
        self.logicaldisks = []
        self.diskdrives =  self.get_updated_diskdrive_info()
        self.disk_partitions = self.get_updated_partition_info()
        self.logicaldisks = self.get_updated_logicaldisk_info()
        self.associate_diskdrives_to_partitions()
        self.associate_partitions_to_logicaldrives()

    def get_updated_diskdrive_info(self):
        '''
        Populate self.diskdrives with WinInstanceDisk objects containing info parsed from wmic command.
        Since wmic doesn't seem to use delimeters this method attempts to derive the lengh of each column/header
        in order to parse out the info per disk.
        :pararm force: boolean. Will force an update, otherwise this method will wait a minimum of
        self.disk_update_interval before updating again.
        '''
        #cmd = "wmic diskdrive get  /format:textvaluelist.xsl"
        self.debug('Getting updated diskdrive info...')
        cmd = "wmic diskdrive list full"

        diskdrives = []
        for disk_dict in self.get_parsed_wmic_command_output(cmd):
            try:
                diskdrives.append(WinInstanceDiskDrive(self,disk_dict))
            except Exception, e:
                tb = self.tester.get_traceback()
                self.debug('Error attempting to create WinInstanceDiskDrive from following dict:')
                self.print_dict(dict=disk_dict)
                raise Exception(str(tb) + "\n Error attempting to create WinInstanceDiskDrive:" + str(e))
        self.debug('get_updated_diskdrive_info, Done')
        return diskdrives


    def get_updated_partition_info(self):
        '''
        Populate self.diskdrives with WinInstanceDisk objects containing info parsed from wmic command.
        Since wmic doesn't seem to use delimeters this method attempts to derive the lengh of each column/header
        in order to parse out the info per disk.
        :pararm force: boolean. Will force an update, otherwise this method will wait a minimum of
        self.disk_update_interval before updating again.
        '''
        self.debug('Getting udpated partition info...')
        cmd = "wmic partition list brief /format:textvaluelist.xsl"

        disk_partitions = []
        for part_dict in self.get_parsed_wmic_command_output(cmd):
            try:
                disk_partitions.append(WinInstanceDiskPartition(self,part_dict))
            except Exception, e:
                tb = self.tester.get_traceback()
                self.debug('Error attempting to create WinInstanceDiskPartition from following dict:')
                self.print_dict(dict=part_dict)
                raise Exception(str(tb) + "\n Error attempting to create WinInstanceDiskPartition:" + str(e))
        self.debug('get_updated_partition_info, Done')
        return disk_partitions


    def get_updated_logicaldisk_info(self):
        self.debug('Getting updated logicaldisk info...')
        cmd ='wmic logicaldisk list /format:textvaluelist.xsl'
        logicaldisks = []
        for part_dict in self.get_parsed_wmic_command_output(cmd):
            try:
                logicaldisks.append(WinInstanceLogicalDisk(self,part_dict))
            except Exception, e:
                tb = self.tester.get_traceback()
                self.debug('Error attempting to create WinInstanceLogicalDisk from following dict:')
                self.print_dict(dict=part_dict)
                raise Exception(str(tb) + "\n Error attempting to create WinInstanceLogicalDisk:" + str(e))
        self.debug('get_updated_logicaldisk_info, Done')
        return logicaldisks


    def associate_diskdrives_to_partitions(self):
        for disk in self.diskdrives:
            disk.disk_partitions = []
            for part in self.disk_partitions:
                if part.diskindex == disk.index:
                    disk.disk_partitions.append(part)

    def associate_partitions_to_logicaldrives(self, verbose=False):
        for part in self.disk_partitions:
            drive_id = None
            part.logicaldisks = []
            cmd = 'wmic partition where (DeviceID="Disk #' + str(part.diskindex) + \
                  ', Partition #' + str(part.index) + '") assoc /assocclass:Win32_LogicalDiskToPartition'
            output = self.sys(cmd, verbose=verbose, code=0)
            for line in output:
                if re.search('Win32_LogicalDisk.DeviceID',line):
                    try:
                        drive_id =  str(line.split()[0].split('=')[1]).replace('"','').strip()
                    except Exception, e:
                        tb = self.tester.get_traceback()
                        self.debug(str(tb)+ "\nError getting logical drive info:" + str(e))
                    if drive_id:
                        for disk in self.logicaldisks:
                            if re.match(disk.deviceid, drive_id):
                                part.logicaldisks.append(disk)
                                disk.partition = part
                                break

    def get_cygwin_scsi_dev_for_windows_drive(self, windisk=None, drive_id=""):
        '''
        param windisk: WinInstanceDiskType object. windisk.deviceid is used to look up the associated cygwin device
        param drive_id: String representing the deviceid. Can be used instead of passing a WinInstanceDiskType
        '''
        windisk_classname = ""
        update = False
        retries = 2
        if windisk:
            drive_id = windisk.deviceid
            windisk_classname = str(windisk.__class__).split('.').pop()
            #If this is a disk drive allow a retry which set the force update flag, otherwise don't force and retry
            if isinstance(windisk,WinInstanceDiskDrive):
                update = True
        if not drive_id:
            raise Exception('WinInstanceDiskType or string w/ device id not provided')

        self.debug('Attempting to get cygwin dev for windows drive:' + str(drive_id))
        self.update_cygwin_windows_device_map()
        for retry in xrange(0, retries):
            for device in self.cygwin_dev_map:
                if re.search("dev", device):
                    win_dev = str(self.cygwin_dev_map[device].split('\\').pop()).strip().upper()
                    formated_drive_id = str(drive_id.split('\\').pop()).strip().upper()
                    #self.debug('Attempt to match:"' + str(win_dev) + '" with "' + str(formated_drive_id) + '"')
                    if formated_drive_id == win_dev:
                        #self.debug('Found match')
                        return device
            if update:
                self.update_cygwin_windows_device_map(force_update=True)
            else:
                break
        self.debug('WARNING: Could not find cygwin device for type:"' + str(windisk_classname) + '", deviceid:' + str(drive_id))
        return ""

    def get_parsed_wmic_command_output(self, wmic_command, verbose=False):
        '''
        Attempts to parse a wmic command using "/format:textvaluelist.xsl" for key value format into a list of
        dicts.
        :param wmic_command: string representing the remote wmic command to be run
        :returns : list of dict(s) created from the parsed key value output of the command.
                   Note keys will be in lowercase

        '''
        self.debug('get_parsed_wmic_command_output, command:' + str(wmic_command))
        ret_dicts = []
        output = self.sys(wmic_command, verbose=verbose, code=0)
        newdict = {}
        for line in output:
            if not re.match(r"^\w",line):
                #If there is a blank line(s) then the previous object is complete
                if newdict:
                    ret_dicts.append(newdict)
                    newdict = {}
            else:
                splitline = line.split('=')
                key = str(splitline.pop(0)).lower()
                if len(splitline) > 1:
                    value = "=".join(str(x) for x in splitline)
                else:
                    if splitline:
                        value = splitline.pop()
                    else:
                        value = ''
                newdict[key] = value
        return ret_dicts

    def get_logicaldisk_ids(self, forceupdate=False):
        '''
        :param forceupdate: boolean, to force an update of logical disks detected on the guest. Otherwise updates are
                throttled to self.disk_update_interval
        :returns list of device ids (ie: [A:,C:,D:]
        '''
        ret = []
        self.update_disk_info(forceupdate=forceupdate)
        for disk in self.logicaldisks:
            ret.append(disk.deviceid)
        return ret

    def get_diskdrive_ids(self, drivelist=None, forceupdate=False):
        '''
        :param forceupdate: boolean, to force an update of logical disks detected on the guest. Otherwise updates are
                throttled to self.disk_update_interval
        :returns list of device ids ie: ['\\.\PHYSICALDRIVE0','\\.\PHYSICALDRIVE1,'\\.\PHYSICALDRIVE2']
        '''
        ret = []
        if not drivelist:
            self.update_disk_info(forceupdate=forceupdate)
            drivelist = self.diskdrives
        for disk in drivelist:
            ret.append(disk.deviceid)
        return ret

    def get_diskdrive_by_deviceid(self, deviceid):
        for disk in self.diskdrives:
            if disk.deviceid == deviceid:
                return disk


    def found(self, command, regex):
        """ Returns a Boolean of whether the result of the command contains the regex"""
        result = self.sys(command)
        for line in result:
            found = re.search(regex,line)
            if found:
                return True
        return False

    def assertFilePresent(self,filepath):
        '''
        Raise exception if file not found at filepath on remote guest. dirs '\' need to be represented as '\\'
        '''
        self.sys('dir ' + str(filepath), code=0)

    def assertCygwinFilePresent(self, filepath):
        self.cygwin_cmd('ls ' + str(filepath), code=0)


    def attach_volume(self, volume,  dev=None, timeout=180, overwrite=False):
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


    def attach_euvolume(self, euvolume, dev=None, timeout=180, overwrite=False):
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

        self.debug('Disk drive summary before attach attempt:')
        self.print_logicaldisk_summary()
        self.print_diskdrive_summary()
        self.debug("Attempting to attach volume:"+str(euvolume.id)+" to instance:" +str(self.id)+" to dev:"+ str(dev))
        #grab a snapshot of our devices before attach for comparison purposes
        diskdrive_list_before = self.get_diskdrive_ids()
        use_serial = False
        for disk in self.diskdrives:
            if re.search('vol-', disk.serialnumber):
                use_serial = True
                break
        attached_dev = None
        start= time.time()
        elapsed = 0
        if dev is None:
            #update our block device prefix
            dev = self.get_free_scsi_dev()
        if (self.tester.attach_volume(self, euvolume, dev, pause=10,timeout=timeout)):
            if euvolume.attach_data.device != dev:
                raise Exception('Attached device:' + str(euvolume.attach_data.device) +
                                ", does not equal requested dev:" + str(dev))
            #Find device this volume is using on guest...
            euvolume.guestdev = None
            while (not euvolume.guestdev and elapsed < timeout):
                #Since all hypervisors may not support serial number info, check for an incremental diff in the
                # list of physical diskdrives on this guest.
                self.debug("Checking for volume attachment on guest, elapsed time("+str(elapsed)+")")
                diskdrive_list_after = self.get_diskdrive_ids(forceupdate=True)
                self.print_logicaldisk_summary()
                self.print_diskdrive_summary()
                self.debug("dev_list_after:"+" ".join(diskdrive_list_after))
                diff =list( set(diskdrive_list_after) - set(diskdrive_list_before) )
                if len(diff) > 0:
                    self.debug('Got Diff in drives:' + str(diff))
                    for disk in self.diskdrives:
                        if re.search('vol-', disk.serialnumber):
                            use_serial = True
                        if euvolume.id == disk.ebs_volume:
                            attached_dev = disk.deviceid
                            euvolume.guestdev = attached_dev
                            self.debug("Volume:"+str(euvolume.id)+" guest device by serialnumber:"+str(euvolume.guestdev))
                            break
                    if not use_serial:
                        attached_dev = str(diff[0])
                        euvolume.guestdev = attached_dev.strip()
                        self.debug("Volume:"+str(euvolume.id)+"found guest device by diff:"+str(euvolume.guestdev))
                    if attached_dev:
                        euvolume.guestdev = attached_dev
                        attached_vol = self.get_volume_from_attached_list_by_id(euvolume.id)
                        self.attached_vols.append(euvolume)
                        self.debug(euvolume.id+": Requested dev:"+str(euvolume.attach_data.device)+", attached to guest device:"+str(euvolume.guestdev))
                        break
                elapsed = int(time.time() - start)
                time.sleep(2)
            if not euvolume.guestdev or not attached_dev:
                raise Exception('Device not found on guest after '+str(elapsed)+' seconds')
        else:
            self.debug('Failed to attach volume:'+str(euvolume.id)+' to instance:'+self.id)
            raise Exception('Failed to attach volume:'+str(euvolume.id)+' to instance:'+self.id)
        if (attached_dev is None):
            self.debug("List after\n"+" ".join(diskdrive_list_after))
            raise Exception('Volume:'+str(euvolume.id)+' attached, but not found on guest'+str(self.id)+' after '+str(elapsed)+' seconds?')
        #Store the md5sum of this diskdrive in the euvolume...
        disk = self.get_diskdrive_by_deviceid(attached_dev)
        euvolume.md5len = 1024
        euvolume.md5 = self.get_dev_md5(devpath=disk.cygwin_scsi_drive, length=euvolume.md5len)
        #update the volume and instances information about the attachment...
        self.update_volume_guest_info(volume=euvolume,md5=euvolume.md5, md5len=euvolume.md5len, guestdev=euvolume.guestdev)
        self.debug('Success attaching volume:'+str(euvolume.id)+' to instance:'+self.id +
                   ', cloud dev:'+str(euvolume.attach_data.device)+', attached dev:'+str(attached_dev) +
                    ", elapsed:" + str(elapsed))
        try:
            self.rescan_disks(timeout=20)
        except Exception, e:
            self.debug('Warning. Error while trying to rescan disks after attaching volume. Error: ' + str(e))
        euvolume.printself(printmethod=self.debug)
        disk.print_self()
        return attached_dev


    def get_guest_dev_for_volume(self, volume, forceupdate=False):
        use_serial = False
        self.update_disk_info(forceupdate=forceupdate)
        for disk in self.diskdrives:
            if re.search('vol-', disk.serialnumber):
                use_serial = True
                break

        if not isinstance(volume, EuVolume):
            volume = EuVolume.make_euvol_from_vol(volume=volume, tester=self.tester)


    def get_disk_drive_by_id(self, deviceid):
        self.update_system_info()
        for disk in self.diskdrives:
            if disk.deviceid == deviceid:
                return disk
        return None


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
                if avol.attach_data.device == dev:
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


    def detach_euvolume(self, euvolume, waitfordev=True, timeout=180):
        '''
        Method used to detach detach a volume to an instance and track it's use by that instance
        required - euvolume - the euvolume object being deattached
        waitfordev - boolean to indicate whether or no to poll guest instance for local device to be removed
        optional - timeout - integer seconds to wait before timing out waiting for the volume to detach
        '''
        start = time.time()
        elapsed = 0
        found = True
        for vol in self.attached_vols:
            if vol.id == euvolume.id:
                dev = vol.guestdev
                if (self.tester.detach_volume(euvolume,timeout=timeout)):
                    if waitfordev:
                        self.debug("Cloud has detached" + str(vol.id) + ", Wait for device:"+str(dev)+" to be removed on guest...")
                        while (elapsed < timeout):
                            diskdrive_ids = []
                            try:
                                disk_drives = self.get_updated_diskdrive_info()
                                for disk in disk_drives:
                                    if dev == disk.deviceid:
                                        found = True
                                        break
                                    found = False
                                    self.debug('Diskdrive associated with ' + str(vol.id) + ' has been removed from guest.')
                                    #if device is not present remove it
                                    self.attached_vols.remove(vol)

                            except Exception, de:
                                self.debug('Warning, error getting diskdrive id during detach:' + str(de))
                            if not found:
                                try:
                                    self.rescan_disks(timeout=20)
                                except Exception, re:
                                    self.debug('Warning: Error while trying to rescan disks after detaching volume:' + str(re))
                                try:
                                    self.update_disk_info()
                                except Exception, ue:
                                    self.debug('Warning: Error while trying to update disk info:' + str(ue))
                                try:
                                    self.print_diskdrive_summary()
                                except: pass
                                self.debug('Volume:' + str(vol.id) + ', detached, and no longer found on guest at:' + str(dev))
                                vol.set_volume_detached_tags()
                                return True
                            time.sleep(10)
                            elapsed = int(time.time()-start)
                            diskdrive_ids = self.get_diskdrive_ids(drivelist=disk_drives)
                            self.debug('Current disk drives on guest:' + ",".join(str(x) for x in diskdrive_ids))
                            self.debug("Waiting for device '"+str(dev)+"' on guest to be removed.Elapsed:"+str(elapsed))

                    else:
                        self.attached_vols.remove(vol)
                        vol.set_volume_detached_tags()
                        return True
                else:
                    raise Exception("Volume("+str(vol.id)+") failed to detach from device("+str(dev)+") on ("+str(self.id)+")")

        raise Exception("Detach Volume("+str(euvolume.id)+") not found on ("+str(self.id)+")")
        return False

    def check_hostname(self):
        if not hasattr(self, 'system_info'):
            self.update_system_info()
        if hasattr(self, 'system_info') and hasattr(self.system_info, 'host_name'):
            if self.id.upper() == self.system_info.host_name.upper():
                self.debug('Hostname:' + str(self.id) + ", instance.id:" + str(self.system_info.host_name))
            else:
                raise Exception('check_hostname failed: hostname:' + str(self.system_info.host_name).upper() +
                                " != id:" + str(self.id).upper())
        else:
            raise Exception('check_hostname failed: System_info.hostname not populated')

    def get_process_list_brief(self):
        '''
        Returns a list of dicts representing the processes running on the remote guest. Each service is represented by a
        dict containing information about the service.
        '''
        cmd = "wmic process list brief /format:textvaluelist.xsl"
        return self.get_parsed_wmic_command_output(cmd)

    def get_process_list_full(self):
        '''
        Returns a list of dicts representing the processes running on the remote guest. Each service is represented by a
        dict containing information about the service.
        '''
        cmd = "wmic process list full"
        return self.get_parsed_wmic_command_output(cmd)

    def get_process_by_name(self,process_name):
        '''
        Attempts to lookup a service on the remote guest.
        param service_name: string. The name of the service to get info
        returns a dict representing the information returned from the remote guest
        '''
        cmd = 'wmic process ' + str(process_name) + ' get /format:textvaluelist.xsl'
        result = self.get_parsed_wmic_command_output(cmd)
        if result:
            return result[0]

    def get_services_list_brief(self):
        '''
        Returns a list of dicts representing the services from the remote guest. Each service is represented by a
        dict containing information about the service.
        '''
        cmd = 'wmic service list brief /format:textvaluelist.xsl'
        return self.get_parsed_wmic_command_output(cmd)

    def get_services_list_full(self):
        '''
        Returns a list of dicts representing the services from the remote guest. Each service is represented by a
        dict containing information about the service.
        '''
        cmd = 'wmic service list full'
        return self.get_parsed_wmic_command_output(cmd)

    def get_service_by_name(self,service_name):
        '''
        Attempts to lookup a service on the remote guest.
        param service_name: string. The name of the service to get info
        returns a dict representing the information returned from the remote guest
        '''
        cmd = 'wmic service ' + str(service_name) + ' get /format:textvaluelist.xsl'
        result = self.get_parsed_wmic_command_output(cmd)
        if result:
            return result[0]

    def get_memtotal_in_mb(self):
        return long(self.system_info.total_physical_memory.split()[0].replace(',',''))

    def get_memtotal_in_gb(self):
        return long(self.get_memtotal_in_mb()/1024)

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

    def check_ephemeral_against_vmtype(self):
        gb = self.gigabyte
        size = self.vmtype_info.disk
        ephemeral_dev = self.get_ephemeral_dev()
        block_size = self.get_blockdev_size_in_bytes(ephemeral_dev)
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
        return ephemeral_dev

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
                return str('/dev/'+prefix+ephem_name)
        raise Exception('Could not find ephemeral device?')


    def cygwin_cmd(self, cmd, timeout=120, verbose=False, code=None):
        cmd = self.get_cygwin_path() + '\\bin\\bash.exe --login -c "' + str(cmd) + '"'
        return self.sys(cmd,timeout=timeout, verbose=verbose, code=code)

    def get_dev_md5(self, devpath, length, timeout=60):
        self.assertCygwinFilePresent(devpath)
        if length == 0:
            md5 = str(self.cygwin_cmd('md5sum ' + devpath, timeout=timeout)[0]).split(' ')[0].strip()
        else:
            md5 = str(self.cygwin_cmd("head -c " + str(length) + " " + str(devpath) + " | md5sum")[0]).split(' ')[0].strip()
        return md5


    def update_cygwin_windows_device_map(self, prefix='/dev/*', force_update=False):
        cygwin_dev_map = {}
        if not force_update:
            if self.cygwin_dev_map:
                if time.time() - self.cygwin_dev_map['last_updated'] <= 30:
                    cygwin_dev_map = self.cygwin_dev_map
        if not cygwin_dev_map:
            self.debug('Updating cygwin to windows device mapping...')
            output = self.cygwin_cmd("for DEV in " + prefix + " ; do printf $DEV=$(cygpath -w $DEV); echo ''; done",
                                     verbose=False, code=0)
            for line in output:
                if re.match(prefix, line):
                    split = line.split('=')
                    key = split.pop(0)
                    if split:
                        value = split.pop()
                    else:
                        value = ''
                    cygwin_dev_map[key]=value
            cygwin_dev_map['last_updated'] = time.time()
            self.cygwin_dev_map = cygwin_dev_map
            self.debug('Updated cygwin to windows device mapping')
        return cygwin_dev_map


    def rescan_disks(self, timeout=20):
        '''
        Attempts to rescan disks on the guest. This may help expedite updates/discovery when attaching/detaching
        volumes to the guest. This has also been found to hang post device removal so is used with a 20 second
        command timeout as the default.
        param timeout: integer. Seconds to wait on command before failing
        '''
        scriptname = 'eutester_diskpart_script'
        self.sys('(echo rescan && echo list disk ) > ' + str(scriptname), code=0)
        self.sys('diskpart /s ' + str(scriptname), code=0, timeout=timeout)


    def get_diskdrive_for_volume(self, volume):
        if not self.is_volume_attached_to_this_instance(volume):
            return None
        ret_disk = None
        for disk in self.diskdrives:
            disk.update_ebs_info()
            if disk.ebs_volume == volume.id:
                ret_disk = disk
        if not ret_disk:
            ret_disk = self.find_diskdrive_for_volume_by_serial_number(volume, force_check=True)
        if not ret_disk:
            if hasattr(volume,'md5') and volume.md5:
                ret_disk = self.find_diskdrive_for_volume_by_md5(volume, force_check=True)
        return ret_disk



    def find_diskdrive_for_volume_by_md5(self, volume, md5=None, length=None, force_check=False):
        if not force_check and not self.is_volume_attached_to_this_instance(volume):
            return None
        if not isinstance(volume, EuVolume):
            volume = EuVolume.make_euvol_from_vol(volume=volume,tester=self.tester)
        md5 = md5 or volume.md5
        if not md5:
            return None
        length = length or volume.md5len
        for disk in self.diskdrives:
            if disk.cygwin_scsi_drive:
                disk_md5 = self.get_dev_md5(disk.cygwin_scsi_drive, length=length)
                if disk_md5 == md5:
                    volume.guestdev = disk.deviceid
                    volume.md5 = disk_md5
                    volume.md5len = length
                    disk.ebs_volume = volume.id
                    return disk
        return None



    def find_diskdrive_for_volume_by_serial_number(self, volume, serial_number=None, force_check=False):
        '''
        Attempt to iterate through all the diskdrives were aware of. If a diskdrive is found with a serial_number
        associated with the volume, return that diskdrive obj..
        example serial number format: vol-81C13EA4-dev-sdg

        :param volume: volume obj to use for deriving the serial_number
        :param serial_number: string. Optional. The string representing the serial # to match.
        :returns WinInstanceDiskDrive if found, else None
        '''
        if not force_check and not self.is_volume_attached_to_this_instance(volume):
            return None
        if not serial_number:
            serial_number = volume.id + volume.attach_data.device.replace('/','-')
        for disk in self.diskdrives:
            if disk.serialnumber == serial_number:
                return disk
        return None



    def is_volume_attached_to_this_instance(self, volume):
        '''
        Attempts to look up volume state per cloud to confirm the cloud believe the state of this volume is attached
        to this instance. This does not verify the guest/hypervisor also belives the volume is attached.
        :param volume: volume obj.
        :returns boolean
        '''
        try:
            volume.update()
        except EC2ResponseError as ER:
            if ER.status == 400 and ER.error_code == 'InvalidVolume.NotFound':
                volume.status = 'deleted'
        if hasattr(volume, 'attach_data') and volume.attach_data and (volume.attach_data.instance_id == self.id):
            self.debug('Volume:' + str(volume.id) + " is attached to this instance: " + str(self.id) + " per cloud perspective")
            return True
        else:
            self.debug('Volume:' + str(volume.id) + " is NOT attached to this instance: " + str(self.id) + " per cloud perspective")
            return False



    def update_volume_guest_info(self, volume, md5=None, md5len=None, guestdev=None):
        self.debug("{0} update_volume_guest_info: {1} {2}"
                   .format(get_line(), volume, get_line()))
        if not self.is_volume_attached_to_this_instance(volume):
            raise Exception('Volume not attached to this instance')
        disk = None
        if not self.get_volume_from_attached_list_by_id(volume.id):
            self.attached_vols.append(volume)
        volume.guestdev = guestdev or volume.guestdev
        if md5:
            if not md5len:
                raise Exception('Must provide md5len if providing the md5')
            volume.md5 = md5
            volume.md5len = md5len
        else:
            disk = self.get_diskdrive_for_volume(volume)
            if not disk:
                raise Exception('Could not find diskdrive for volume when attempting to update volume guest info:' + str(volume))
            volume.md5len = md5len or 1024
            volume.md5 = self.get_dev_md5(disk.cygwin_scsi_drive, volume.md5len)
        if not guestdev:
            volume.guestdev = disk.deviceid
        disk = disk or self.get_diskdrive_for_volume(volume)
        disk.update_ebs_info()
        volume.update_volume_attach_info_tags(md5=volume.md5, md5len=volume.md5len, instance_id=self.id, guestdev=volume.guestdev)
        return volume

    def get_unsynced_volumes(self, check_md5=True):
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
        retdict = self.sync_attached_volumes_with_clouds_view()
        bad_list.extend(retdict['badvols'])
        return bad_list



    def reboot_instance_and_verify(self,
                                   waitconnect=60,
                                   timeout=600,
                                   wait_for_ports=180,
                                   connect=True,
                                   checkvolstatus=False,
                                   pad=5,
                                   uptime_retries=3):
        '''
        Attempts to reboot an instance and verify it's state post reboot.
        waitconnect-optional-integer representing seconds to wait before attempting to connect to instance after reboot
        timeout-optional-integer, seconds. If a connection has failed, this timer is used to determine a retry
        connect- optional - boolean to indicate whether an ssh session should be established once the expected state has been reached
        checkvolstatus - optional -boolean to be used to check volume status post start up
        '''
        msg=""
        newuptime = None
        attempt = 0
        def get_safe_uptime():
            uptime = None
            try:
                uptime = self.get_uptime()
            except: pass
            return uptime
        self.debug('Attempting to reboot instance:'+str(self.id)+', check attached volume state first')
        uptime = self.tester.wait_for_result( get_safe_uptime, None, oper=operator.ne)
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
        try:
            self.poll_for_ports_status(ports=[3389,5589], timeout=wait_for_ports)
        except:
            self.debug('Failed to poll winrm and rdp ports after ' + str(wait_for_ports) + ' seconds, try to connect anyways...')
        timeout=timeout - int(time.time()-start)
        while (elapsed < timeout):
            self.connect_to_instance(timeout=timeout)
            #Wait for the system to provide a valid response for uptime, early connections may not
            newuptime = self.tester.wait_for_result( get_safe_uptime, None, oper=operator.ne)
            elapsed = int(time.time()-start)
            #Check to see if new uptime is at least 'pad' less than before, allowing for some pad
            if (newuptime - (uptime+elapsed)) > pad:
                err_msg = "Instance uptime does not represent a reboot. Orig:"+str(uptime)+\
                          ", New:"+str(newuptime)+", elapsed:"+str(elapsed)+"/"+str(timeout)
                if elapsed > timeout:
                    raise Exception(err_msg)
                else:
                    self.debug(err_msg)
            else:
                self.debug("Instance uptime indicates a reboot. Orig:"+str(uptime)+\
                          ", New:"+str(newuptime)+", elapsed:"+str(elapsed))
                break
        if checkvolstatus:
            badvols= self.get_unsynced_volumes()
            if badvols != []:
                for vol in badvols:
                    msg = msg+"\nVolume:"+vol.id+" Local Dev:"+vol.guestdev
                raise Exception("Missing volumes post reboot:"+str(msg)+"\n")
        self.debug(self.id+" reboot_instance_and_verify Success")


    def get_uptime(self):
        if not hasattr(self, 'system_info'):
            self.update_system_info()
        if hasattr(self.system_info, 'system_boot_time'):
            return self._get_uptime_from_system_boot_time()
        elif hasattr(self.system_info, 'system_up_time'):
            return self._get_uptime_from_system_up_time()
        else:
            tb = self.tester.get_traceback()
            raise Exception(str(tb) + '\nCould not get system boot or up time from system_info')

    def _get_uptime_from_system_boot_time(self):
            #11/18/2013, 3:15:39 PM
        if not hasattr(self, 'system_info'):
            self.update_system_info()
        splitdate = self.system_info.system_boot_time.split()
        datestring = splitdate[0]
        timestring = splitdate[1]
        ampm = splitdate[2]
        month, day, year = datestring.replace(',',"").split('/')
        hours, minutes, seconds = timestring.split(':')
        if ampm == 'PM':
            hours = int(hours) + 12
        datetimestring = str(year) + " " + \
                         str(month) + " " + \
                         str(day) + " " + \
                         str(hours) + " " + \
                         str(minutes) + " " + \
                         str(seconds)
        dt = datetime.strptime(datetimestring, "%Y %m %d %H %M %S")
        return int(time.time() - time.mktime(dt.timetuple()))
    
    def _get_uptime_from_system_up_time(self):
        #0 Days, 0 Hours, 6 Minutes, 39 Seconds
        if not hasattr(self, 'system_info'):
            self.update_system_info()
        uptime_string = self.system_info.system_up_time
        days = 0
        hours = 0
        minutes = 0
        seconds = 0
        split = uptime_string.split(',')
        for part in split:
            time_string = ""
            if re.search('Days', part, re.IGNORECASE):
                time_string = str(part.split()[0]).strip()
                days = int(time_string or 0)
            elif re.search('Hours', part, re.IGNORECASE):
                time_string = str(part.split()[0]).strip()
                hours = int(time_string or 0)
            elif re.search('Minutes', part, re.IGNORECASE):
                time_string = str(part.split()[0]).strip()
                minutes = int(time_string or 0)
            elif re.search('Seconds', part, re.IGNORECASE):
                time_string = str(part.split()[0]).strip()
                seconds = int(time_string or 0)
        self.debug("Days:" +str(days)+', Hours:'+ str(hours) + ", Minutes:" + str(minutes) + ", Seconds:" + str(seconds))
        uptime = (days * 86400) + (hours * 3600) + (minutes * 60) + seconds
        return uptime


    def stop_instance_and_verify(self, timeout=200, state='stopped',
                                 failstate='terminated', check_vols=True):
        '''
        Attempts to stop instance and verify the state has gone to
        stopped state
        :param timeout; -optional-time to wait on instance to go to state 'state' before failing
        :param state: -optional-the expected state to signify success, default is stopped
        :param failstate: -optional-a state transition that indicates failure, default is terminated
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
                raise Exception(str(self.id) + " instance went to state:" +
                                str(self.state) + " while stopping")
            elapsed = int(time.time()- start)
            if elapsed % 10 == 0 :
                self.debug(str(self.id) + " wait for stop, in state:" +
                           str(self.state) + ",time remaining:" +
                           str(elapsed) + "/" + str(timeout) )
        if self.state != state:
            raise Exception(self.id + " state: " + str(self.state) +
                            " expected:" + str(state) +
                            ", after elapsed:" + str(elapsed))
        if check_vols:
            for volume in self.attached_vols:
                try:
                    volume.update()
                except EC2ResponseError as ER:
                    if ER.status == 400 and ER.error_code == 'InvalidVolume.NotFound':
                        volume.status = 'deleted'
                if volume.status != 'in-use':
                    raise Exception(str(self.id) + ', Volume ' +
                                    str(volume.id) + ':' + str(volume.status)
                                    + ' state did not remain in-use '
                                      'during stop')
        self.debug(self.id + " stop_instance_and_verify Success")


    def start_instance_and_verify(self, timeout=300, state = 'running',
                                  failstates=['terminated'], failfasttime=30,
                                  connect=True, checkvolstatus=True):
        '''
        Attempts to start instance and verify state, and reconnects ssh session
        :param timeout: -optional-time to wait on instance to go to state
                        'state' before failing
        :param state: -optional-the expected state to signify success,
                        default is running
        :param failstate: -optional-a state transition that indicates failure,
                          default is terminated
        :param connect: -optional - boolean to indicate whether an ssh
                        session should be established once the expected state
                        has been reached
        :param checkvolstatus: -optional -boolean to be used to check volume
                               status post start up
        '''
        self.debug(self.id+" Attempting to start instance...")
        if checkvolstatus:
            for volume in self.attached_vols:
                try:
                    volume.update()
                except EC2ResponseError as ER:
                    if ER.status == 400 and ER.error_code == 'InvalidVolume.NotFound':
                        volume.status = 'deleted'
                if checkvolstatus:
                    if volume.status != 'in-use':
                        raise Exception(str(self.id) + ', Volume ' + str(volume.id) + ':' + str(volume.status)
                                        + ' state did not remain in-use during stop'  )
        self.debug("\n"+ str(self.id) + ": Printing Instance 'attached_vol' list:\n")
        self.tester.show_volumes(self.attached_vols)
        msg=""
        start = time.time()
        elapsed = 0
        self.update()
        #Add fail fast states...
        if self.state == 'stopped':
            failstates.extend(['stopped','stopping'])
        self.start()

        while (elapsed < timeout):
            elapsed = int(time.time()- start)
            self.update()
            self.debug(str(self.id) + " wait for start, in state:" +
                       str(self.state) + ",time remaining:" + str(elapsed) +
                       "/"+str(timeout) )
            if self.state == state:
                break
            if elapsed >= failfasttime:
                for failstate in failstates:
                    if self.state == failstate:
                        raise Exception(str(self.id) +
                                        " instance went to state:" +
                                        str(self.state) + " while starting")
            time.sleep(10)
        if self.state != state:
            raise Exception(self.id + " not in " + str(state) +
                            " state after elapsed:" + str(elapsed))
        else:
            self.debug(self.id + " went to state:" + str(state))
            if connect:
                self.connect_to_instance(timeout=timeout)
            if checkvolstatus:
                badvols= self.get_unsynced_volumes(check_md5=True)
                if badvols != []:
                    for vol in badvols:
                        msg = msg + "\nVolume:" + vol.id + " Local Dev:" +\
                              vol.guestdev
                    raise Exception("Missing volumes post reboot:" + str(msg) +
                                    "\n")
        self.debug(self.id+" start_instance_and_verify Success")














