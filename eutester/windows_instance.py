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
'''
from boto.ec2.instance import Instance
from eutester import Eutester
from eucaops import Eucaops
from eutester.euvolume import EuVolume
from eutester import eulogger
from eutester.taggedresource import TaggedResource
from random import randint
import winrm_connection
import socket
import sys
import os
import re
import time
import copy
import types
import operator


class WinInstanceDiskDrive():
    gigabyte = 1073741824
    def __init__(self, win_instance, wmic_dict):
        if not ('deviceid' in wmic_dict and
                'size' in wmic_dict and
                'serialnumber' in wmic_dict and
                'caption' in wmic_dict and
                'index' in wmic_dict):
            raise Exception('wmic_dict passed does not contain needed attributes; deviceid, size, and description')
        self.__dict__ = self.convert_ints_in_dict(copy.copy(wmic_dict))
        self.win_instance = win_instance
        self.size_in_gb = self.get_size_in_gb()
        self.update_ebs_info_from_serial_number()

    def convert_ints_in_dict(self, dict):
        #convert strings representing numbers to ints
        for key in dict:
            value = str(dict[key])
            if (re.search("\S", str(dict[key])) and not re.search("\D", str(dict[key]))):
                dict[key] = int(dict[key])
        return dict


    def get_size_in_gb(self):
        '''
        Attempts to convert self.size from bytes to gigabytes as well as round up > .99 to account for a differences
        in how the size is represented
        '''
        gigs = self.size / self.gigabyte
        if (self.size % self.gigabyte) /float(self.gigabyte) > .99:
            gigs += 1
        return gigs


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


    def print_self(self):
        self.get_summary(printmethod=self.win_instance.debug)

    def get_summary(self, printheader=True, printmethod=None):
        buf = ""
        deviceid = 24
        size = 16
        sizegb = 12
        serialnumber = 24
        caption = 30
        header = "DEVICEID".center(deviceid) + "|" + \
                 "SIZE B".center(size) + "|" + \
                 "SIZE GB".center(sizegb) + "|" + \
                 "SERIAL NUMBER".center(serialnumber) + "|" + \
                 "CAPTION".center(caption) + "|"
        summary = str(self.deviceid).center(deviceid) + "|" + \
                  str(self.size).center(size) + "|" + \
                  str(self.size_in_gb).center(sizegb) + "|" + \
                  str(self.serialnumber).center(serialnumber) + "|" + \
                  str(self.caption).center(caption) + "|"
        length = len(header)
        if len(summary) > length:
            length = len(summary)
        line = self.get_line(length)
        if printheader:
            buf += line + header + line
        buf += summary + line
        if printmethod:
            printmethod(buf)
        return buf

    def get_line(self, length):
        line = ""
        for x in xrange(0,int(length)):
            line += "-"
        return "\n" + line + "\n"


    def print_self_full(self, printmethod=None):
        '''
        formats and prints self.dict
        '''
        self.win_instance.print_dict(dict=self.__dict__, printmethod=printmethod)




class WinInstance(Instance, TaggedResource):

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
                                      exec_password=None,
                                      winrm_port='5985',
                                      winrm_protocol='http',
                                      rdp_port='3389',
                                      rootfs_device = "sda",
                                      block_device_prefix = "sd",
                                      bdm_root_vol = None,
                                      attached_vols = [],
                                      virtio_blk = True,
                                      disk_update_interval=5,
                                      retry=2
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
        assert  isinstance(tester, Eucaops)
        newins.tester = tester
        newins.winrm_port = winrm_port
        newins.rdp_port = rdp_port
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
        newins.keypair = keypair
        newins.keypath = keypath or os.getcwd() + "/" + keyname + ".pem"

        newins.password = password
        newins.username = username
        newins.exec_password = exec_password or password
        newins.verbose = verbose
        newins.attached_vols=attached_vols
        newins.timeout = timeout
        newins.virtio_blk  = virtio_blk
        newins.disk_update_interval = disk_update_interval
        newins.retry = retry
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
        newins.system_info = None
        newins.disk_drives = []
        newins.logical_disks = []
        newins.disk_partitions = []
        #newins.set_block_device_prefix()
        if newins.root_device_type == 'ebs':
            try:
                volume = newins.tester.get_volume(volume_id = newins.block_device_mapping.get(newins.root_device_name).volume_id)
                newins.bdm_root_vol = EuVolume.make_euvol_from_vol(volume, tester=newins.tester,cmdstart=newins.cmdstart)
            except:pass
        else:
            newins.bdm_root_vol = None
        newins.winrm = None
        if newins.auto_connect:
            newins.connect_to_instance(timeout=timeout)
            newins.update_diskinfo()
            newins.update_system_info()
        return newins

    def update(self):
        super(WinInstance, self).update()
        self.set_last_status()

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
        for key in self.__dict__:
            if len(key) > longest_key:
                longest_key = len(key)
        for key in self.__dict__:
            buf += str(key).ljust(longest_key) + " -----> :" + str(self.__dict__[key]) + "\n"
        printmethod(buf)

    def printself(self,title=True, footer=True, printmethod=None):
        if self.bdm_root_vol:
            bdmvol = self.bdm_root_vol.id
        else:
            bdmvol = None
        reservation_id = None
        if self.reservation:
            reservation_id = self.reservation.id

        buf = "\n"
        if title:
            buf += str("-------------------------------------------------------------------------------------------------------------------------------------------------------------------\n")
            buf += str('INST_ID').center(11)+'|'+str('EMI').center(13)+'|'+str('RES_ID').center(11)+'|'+str('LASTSTATE').center(10)+'|'+str('PRIV_ADDR').center(10)+'|'+str('AGE@STATUS').center(13)+'|'+str('VMTYPE').center(12)+'|'+str('ROOT_VOL').center(13)+'|'+str('CLUSTER').center(25)+'|'+str('PUB_IP').center(16)+'|'+str('PRIV_IP')+'\n'
            buf += str("-------------------------------------------------------------------------------------------------------------------------------------------------------------------\n")
        buf += str(self.id).center(11)+'|'+str(self.image_id).center(13)+'|'+str(reservation_id).center(11)+'|'+str(self.laststate).center(10)+'|'+str(self.private_addressing).center(10)+'|'+str(self.age_at_state).center(13)+'|'+str(self.instance_type).center(12)+'|'+str(bdmvol).center(13)+'|'+str(self.placement).center(25)+'|'+str(self.ip_address).center(16)+'|'+str(self.private_ip_address).rstrip()
        if footer:
            buf += str("\n-------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        if printmethod:
            printmethod(buf)
        return buf


    def get_password(self, private_key_path=None, key=None, dir=None, exten=".pem", encoded=True):
        '''
        :param private_key_path: private key file used to decrypt password
        :param key: name of private key
        :param dir: Path to private key
        :param exten: extension of private key
        :param encoded: boolean of whether string returned from server is Base64 encoded
        :return: decrypted password
        '''
        if self.password is None:
            self.password = self.tester.get_windows_instance_password(self,
                                                                      private_key_path=private_key_path,
                                                                      key=key,
                                                                      dir=dir,
                                                                      exten=exten,
                                                                      encoded=encoded)
        return self.password


    def reset_ssh_connection(self, timeout=None):
        # todo: Remove ssh reference from this method, use something like reset_instance_connection, etc..
        self.debug('Note ssh not implemented at this time, using winrm for shell access instead...')
        return self.reset_winrm_connection(timeout=timeout)

    def reset_winrm_connection(self, timeout=None, force=False):
        # todo:
        timeout = timeout or self.timeout
        self.debug('reset_winrm_connection for:'+str(self.id))
        if self.password is None:
            self.get_password()
        if self.username is None or self.password is None:
            #Allow but warn here as this may be a valid negative test
            self.debug('Warning username and/or password were None in winrm connnection?')
        #Create a new winrm interface if this is a new instance or an attribute has changed...
        if force or not (self.winrm and \
                         self.winrm.hostname == self.ip_address and \
                         self.winrm.username == self.username and \
                         self.winrm.password == self.password):
            if self.winrm:
                self.winrm.close_shell()
            self.winrm = winrm_connection.Winrm_Connection(hostname = self.ip_address,
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
            self.debug('Could not get reservation for instance in state:' + str(self.state) + ", err:" + str(e))
        return res


    def connect_to_instance(self, wait_for_boot=180, timeout=120):
        '''
        Attempts to connect to an instance via ssh.
        wait_for_boot=time to wait, allowing guest to boot before attempting to poll for ports active status
        timeout - optional - time in seconds to wait when polling port(s) status(s) before failure

        '''
        try:
            self.poll_for_port_status_with_boot_delay(waitforboot=wait_for_boot, timeout=timeout)
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
                self.debug('Caught exception attempting to connect winrm shell:'+ str(se))
                elapsed = int(time.time()-start)
                self.debug('connect_to_instance: Attempts:'+str(attempts)+', elapsed:'+str(elapsed)+'/'+str(timeout))
                if self.winrm is not None:
                    self.winrm.close_shell()
                    self.winrm = None
                time.sleep(5)
                pass
            else:
                break
        elapsed = int(time.time()-start)
        if self.winrm is None:
            raise Exception(str(self.id)+":Failed establishing ssh connection to instance, elapsed:"+str(elapsed)+
                            "/"+str(timeout))


    def has_sudo(self):
        return False



    def debug(self,msg,traceback=1,method=None,frame=False):
        '''
        Used to print debug, defaults to print() but over ridden by self.debugmethod if not None
        msg - mandatory -string, message to be printed
        '''
        if ( self.verbose is True ):
            self.debugmethod(msg)

    def sys(self, cmd, verbose=True, code=None, include_stderr=False, enable_debug=False, timeout=120):
        '''
        Issues a command against the ssh connection to this instance
        Returns a list of the lines from stdout+stderr as a result of the command
        cmd - mandatory - string, the command to be executed
        verbose - optional - boolean flag to enable debug
        timeout - optional - command timeout in seconds
        '''
        if (self.winrm is None):
            raise Exception("WinInstance winrm connection is None")
        return self.winrm.sys(command=cmd, include_stderr=include_stderr, timeout=None, code=code)




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
            time.sleep(interval)
            elapsed = int(time.time() -start)
        raise Exception('test_poll_for_ports_status:'+str(ip)+':'+str(port)+' FAILED after attempts:'+str(attempt)+', elapsed:'+str(elapsed)+' seconds')


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
                    currentkey = currentkey.upper()
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


    def get_metadata(self, element_path, prefix='latest/meta-data/'):
        """Return the lines of metadata from the element path provided"""
        ### If i can reach the metadata service ip use it to get metadata otherwise try the clc directly
        try:
            self.sys("ping -c 1 169.254.169.254", code=0, verbose=False)
            return self.sys("curl http://169.254.169.254/"+str(prefix)+str(element_path), code=0)
        except:
            return self.sys("curl http://" + self.tester.get_ec2_ip()  + ":8773/"+str(prefix) + str(element_path), code=0)


    def print_disk_drive_summary(self,printmethod=None):
        printmethod = printmethod or self.debug
        if not self.disk_drives:
            printmethod('No disk drives to print?')
            return
        disklist = copy.copy(self.disk_drives)
        buf = (disklist.pop()).get_summary()
        for disk in disklist:
            buf += disk.get_summary(printheader=False)
        printmethod(buf)


    def update_diskinfo(self, forceupdate=False):
        '''
        Populate self.disk_drives with WinInstanceDisk objects containing info parsed from wmic command.
        Since wmic doesn't seem to use delimeters this method attempts to derive the lengh of each column/header
        in order to parse out the info per disk.
        :pararm force: boolean. Will force an update, otherwise this method will wait a minimum of
        self.disk_update_interval before updating again.
        '''
        cmd = "wmic diskdrive get  /format:textvaluelist.xsl"
        if self.disk_drives:
            if not forceupdate and (time.time() - self.disk_drives[0].last_updated) <= self.disk_update_interval:
                return
        for disk_dict in self.get_parsed_wmic_command_output(cmd):
            try:
                self.disk_drives.append(WinInstanceDiskDrive(self,disk_dict))
            except Exception, e:
                tb = self.tester.get_traceback()
                self.debug('Error attempting to create WinInstanceDiskDrive from following dict:')
                self.print_dict(dict=disk_dict)
                raise Exception(str(tb) + "\n Error attempting to create WinInstanceDiskDrive:" + str(e))


    def get_parsed_wmic_command_output(self, wmic_command, verbose=False):
        '''
        Attempts to parse a wmic command using "/format:textvaluelist.xsl" for key value format into a list of
        dicts.
        :param wmic_command: string representing the remote wmic command to be run
        :returns : list of dict(s) created from the parsed key value output of the command.
                   Note keys will be in lowercase

        '''
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
                    value = splitline.pop() or ''
                newdict[key] = value
        return ret_dicts

    def get_logical_disk_ids(self, forceupdate=False):
        '''
        :param forceupdate: boolean, to force an update of logical disks detected on the guest. Otherwise updates are
                throttled to self.disk_update_interval
        :returns list of device ids (ie: [A:,C:,D:]
        '''
        ret = []
        self.update_disk_info(forceupdate=forceupdate)
        for disk in self.logical_disks:
            ret.append(disk.deviceid)
        return ret

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

        self.debug("Attempting to attach volume:"+str(euvolume.id)+" to instance:" +str(self.id)+" to dev:"+ str(dev))
        #grab a snapshot of our devices before attach for comparison purposes
        dev_list_before = self.get_logical_disk_ids(forceupdate=True)

        dev_list_after = []
        attached_dev = None
        start= time.time()
        elapsed = 0
        if dev is None:
            #update our block device prefix, detect if virtio is now in use
            dev = self.get_free_scsi_dev()
        if (self.tester.attach_volume(self, euvolume, dev, pause=10,timeout=timeout)):
            if euvolume.attach_data.device != dev:
                raise Exception('Attached device:' + str(euvolume.attach_data.device) +
                                ", does not equal requested dev:" + str(dev))
            #Find device this volume is using on guest...
            euvolume.guestdev = None
            while (not euvolume.guestdev and elapsed < timeout):
                self.debug("Checking for volume attachment on guest, elapsed time("+str(elapsed)+")")
                dev_list_after = self.get_logical_disk_ids()
                self.debug("dev_list_after:"+" ".join(dev_list_after))
                diff =list( set(dev_list_after) - set(dev_list_before) )
                if len(diff) > 0:
                    devlist = str(diff[0]).split('/')
                    attached_dev = '/dev/'+devlist[len(devlist)-1]
                    euvolume.guestdev = attached_dev.strip()
                    self.debug("Volume:"+str(euvolume.id)+" guest device:"+str(euvolume.guestdev))
                    self.attached_vols.append(euvolume)
                    self.debug(euvolume.id+" Requested dev:"+str(euvolume.attach_data.device)+", attached to guest device:"+str(euvolume.guestdev))
                    break
                elapsed = int(time.time() - start)
                time.sleep(2)
            if not euvolume.guestdev or not attached_dev:
                raise Exception('Device not found on guest after '+str(elapsed)+' seconds')
            self.debug(str(euvolume.id) + "Found attached to guest at dev:" +str(euvolume.guestdev) +
                       ', after elapsed:' +str(elapsed))
        else:
            self.debug('Failed to attach volume:'+str(euvolume.id)+' to instance:'+self.id)
            raise Exception('Failed to attach volume:'+str(euvolume.id)+' to instance:'+self.id)
        if (attached_dev is None):
            self.debug("List after\n"+" ".join(dev_list_after))
            raise Exception('Volume:'+str(euvolume.id)+' attached, but not found on guest'+str(self.id)+' after '+str(elapsed)+' seconds?')
        #Check to see if this volume has unique data in the head otherwise write some and md5 it
        #self.vol_write_random_data_get_md5(euvolume,overwrite=overwrite)
        self.debug('Success attaching volume:'+str(euvolume.id)+' to instance:'+self.id+', cloud dev:'+str(euvolume.attach_data.device)+', attached dev:'+str(attached_dev))
        return attached_dev


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

















