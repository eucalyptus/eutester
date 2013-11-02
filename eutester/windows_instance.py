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


class WinInstanceDisk():
    def __init__(self,deviceid, size, description, freespace ):
        self.deviceid = deviceid
        self.size = size
        self.description = description
        self.freespace = freespace


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



    def update_disk_info(self):
        self.logical_disks =[]
        new_info = []
        header_list = []
        diskinfo = self.sys('wmic logicaldisk get size,freespace,deviceid,description')
        header_line = diskinfo.pop(0)
        headers = header_line.split()
        for x in xrange(0,len(headers)-1):
            if x < len(headers)-1:
                y = x + 1
            else:
                y = len(header_line)
            start = header_line.index(headers[x])
            stop = header_line.index(headers[y])
            header_list.append({'name':headers[x],'start':start, 'stop':stop})
        for line in diskinfo:
            if len(line):
                deviceid = None
                description = None
                size = None
                freespace = None
                for header in header_list:
                    if re.match('deviceid', header['name'], re.IGNORECASE):
                        deviceid = line[header['start']:header['stop']]
                    if re.match('description', header['name'], re.IGNORECASE):
                        description =  line[header['start']:header['stop']]
                    if re.match('size', header['name'], re.IGNORECASE):
                        size = line[header['start']:header['stop']]
                    if re.match('freespace', header['name'], re.IGNORECASE):
                        freespace = line[header['start']:header['stop']]
                new_disk = WinInstanceDisk(deviceid=deviceid.strip(),
                                           size=size.strip(),
                                           description=description.strip(),
                                           freespace=freespace.strip())
                new_info.append(new_disk)
        self.logical_disks = new_info






















