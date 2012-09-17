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
  
from eucaops import Eucaops
import eutester.eutestcase
from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import EutesterTestResult
import eutester.machine 
from imageutils import ImageUtils
from testcases.cloud_user.images.imageutils import ImageUtils
from testcases.cloud_user.ebs.ebstestsuite import TestZone
import windowsproxytests
from eutester.euvolume import EuVolume
import socket
import os
import time
import re

class WindowsTests(EutesterTestCase):
    
    def __init__(self, 
                 #setup eutester and test environment...
                 tester=None, 
                 config_file=None, 
                 cred_path=None,
                 password="foobar", 
                 credpath=None, 
                 eof=True,
                 #Information on where to do image bundle work, and related timeouts
                 destpath='/disk1/storage/',  
                 time_per_gig = 300,
                 inter_bundle_timeout=120, 
                 upload_timeout=0,
                 work_component=None,
                 component_credpath=None,
                 bucketname = None,
                 #Test env resources...
                 group = None,
                 testvolumes = [],
                 testvolcount = 2,
                 keypair=None, 
                 zone = None,
                 url=None,
                 emi=None,
                 emi_location=None,
                 image_path=None, #note this must be available on the work_component
                 instance=None,
                 win_proxy_hostname = None, 
                 win_proxy_username = 'Administrator',
                 win_proxy_password = None, 
                 win_proxy_keypath = None,
                 ):
        if tester is None:
            self.tester = Eucaops( config_file=config_file,password=password,credpath=credpath)
        else:
            self.tester = tester
        self.tester.exit_on_fail = eof
        self.instance = instance
        if self.instance:
            self.instance = self.tester.get_instances(idstring=str(instance))[0]
        self.destpath = str(destpath)
        self.bucketname = bucketname
        self.component = work_component 
        self.component_credpath = component_credpath
        self.time_per_gig = time_per_gig
        self.credpath=credpath or self.tester.credpath
        self.url = url
        self.upload_timeout = upload_timeout
        self.inter_bundle_timeout = inter_bundle_timeout
        self.iu = ImageUtils(tester=self.tester, destpath=self.destpath, time_per_gig=self.time_per_gig, work_component=self.component)
        self.group = group 
        self.keypair = keypair
        self.zonelist = []
        self.emi = self.tester.get_emi(emi)
        self.image_path = image_path
        
        self.emi_location = emi_location
        if zone is not None:
            self.zonelist.append(zone)
        self.testvolcount = testvolcount
        self.testvolumes = testvolumes
        self.instance_password = None
        #setup zone list
        self.setupWindowsZones()
        #setup windows proxy 
        if win_proxy_hostname is not None:
            self.setup_proxy(win_proxy_hostname,
                             proxy_keypath = win_proxy_keypath,
                             proxy_username = win_proxy_username,
                             proxy_password = win_proxy_password,
                             debugmethod = lambda msg: self.debug(msg, traceback=2)
                             )
        self.setup_test_env()
        if self.instance and self.proxy:
                self.update_proxy_instance_data()
    
    def setup_proxy(self, proxy_hostname, proxy_keypath=None, proxy_username=None, proxy_password=None, debugmethod=None):
        debugmethod = debugmethod or (lambda msg: self.debug(msg, traceback=2))
        proxy = windowsproxytests.WindowsProxyTests(proxy_hostname, 
                                                         proxy_keypath = proxy_keypath,
                                                         proxy_username = proxy_username,
                                                         proxy_password = proxy_password,
                                                         debugmethod = debugmethod,
                                                         )
        self.proxy = proxy
        return proxy
    '''       
    def proxydebug(self, msg):
        return self.debug(msg, traceback=2)
    '''
    def setup_test_env(self):
        self.setupWindowsKeypair()
        self.setupWindowsSecurityGroup()
        self.setupWindowsZones()
        
    def get_images_by_location(self, match='windows'):
        retlist=[]
        for image in self.tester.ec2.get_all_images():
            if re.search(match,image.location):
                retlist.append(image)
        return retlist
        
    def update_proxy_instance_data(self, win_instance=None, instance_password=None ):
        if self.proxy is None:
            return
        self.proxy.win_instance = win_instance or self.instance
        try:
            password = instance_password or self.instance_password
            if password is None:
                password = self.test_get_windows_instance_password()
            self.proxy.win_password = password
        except Exception, e:
            self.debug('Warning: update_proxy_instance_data: Could not get instance password')    
        
        
            
    def setupWindowsSecurityGroup(self):
        #Setup our security group for later use...
        if self.group is None:
            group_name='WindowsTestGroup'
            
            try:
                self.group = self.tester.add_group(group_name)
                self.tester.authorize_group_by_name(self.group.name)
                #enable windows RDP port
                self.tester.authorize_group_by_name(self.group.name,protocol="tcp",port=3389) 
                #enable http/https
                self.tester.authorize_group_by_name(self.group.name,protocol="tcp",port=80)
                self.tester.authorize_group_by_name(self.group.name,protocol="tcp",port=443)
                #enable remote powershell
                self.tester.authorize_group_by_name(self.group.name,protocol="tcp",port=5985)
                self.tester.authorize_group_by_name(self.group.name,protocol="tcp",port=5986)
            except Exception, e:    
                raise Exception("Error when setting up group:"+str(group_name)+", Error:"+str(e)) 
         
        
    def setupWindowsKeypair(self):
        #Setup the keypairs for later use
        try:
            if self.keypair is None:
                keys = self.tester.get_all_current_local_keys() 
                if keys != []:
                    self.keypair = keys[0]
                else:
                    self.keypair = keypair = self.tester.add_keypair('windows_test_key-' + str(time.time()))
            else:
                return
        except Exception, ke:
            raise Exception("Failed to find/create a keypair, error:" + str(ke))
        
           
        
    def test_get_windows_instance_password(self, instance=None, privkeypath=None):
        instance =instance or self.instance
        privkeypath = privkeypath or self.tester.verify_local_keypath(self.keypair.name)
        password = self.tester.get_windows_instance_password(instance, private_key_path = privkeypath)
        self.instance_password = password
        return password
        
    def setupWindowsZones(self):
        
        #create some zone objects and append them to the zonelist
        if self.zonelist == []:
            for zone in self.tester.service_manager.partitions.keys():
                partition = self.tester.service_manager.partitions.get(zone)
                tzone = TestZone(partition)
                self.zonelist.append(tzone)
                self.multicluster=True
        else:
            return
                
    def set_windows_test_volumes(self):
        '''
        Description:
            Attempts to confirm that each zone provided has the minimum number of volumes in it. 
            If volumes were provided in __init__ then this method will attempt to sort those into the zone. 
            Volumes will be created if the testzones do not have the amount specified. 
        Failure:
            Failed to create volumes for use in windows test
        '''
        volume = EuVolume()
        zone = TestZone()
        if len(self.zonelist) and len(self.zonelist[0].volumes):
            self.debug('setupWindowsTestVolumes has already been ran')
            return
        #sort any provided volumes into zone
        for volume in self.testvolumes:
            if volume.status == 'available':
                if type(volume) != EuVolume:
                    volume = EuVolume.make_euvol_from_vol(volume)
                for zone in self.zonelist:
                    if volume.zone == zone.name:
                        zone.volumes.append(volume)
        #make sure each zone has the correct amount of volumes to perform the tests
        for zone in self.zonelist:
            while len(zone.volumes) < self.testvolcount:
                volume = EuVolume.make_euvol_from_vol(self.tester.create_volume(zone,timepergig=180))
                zone.volumes.append(volume)
            
        
                
    def create_vols_per_zone(self, zonelist=None, volsperzone=2, size=1, snapshot=None, timepergig=300):
        testmsg =   """
                    Intention of this test is to verify creation of volume(s) per zone given.
                    Upon successful creation the volumes will be appended to a volumes list
                    for the zone it was created in. 
                    These volumes may be later used if in later ebstests suite tests. 
                    """    
        testmsg = testmsg + "variables provided:\nzonelist:"+str(zonelist)+"\nvolsperzone:"+str(volsperzone)+"\nsize:"+str(size)+"\nsnapshot:"+str(snapshot)
        
        self.startmsg(testmsg)
        if zonelist is None:
            zonelist = self.zonelist
        for testzone in zonelist:
            zone = testzone.name
            for x in xrange(0,volsperzone):
                vol = euvolume.EuVolume.make_euvol_from_vol(self.tester.create_volume(zone, size=size, snapshot=snapshot,timepergig=timepergig))
                testzone.volumes.append(vol)
                self.debug('create_vols_per_zone created  vol('+str(x)+') zone:'+str(zone)+' vol:'+str(vol.id))
            
        self.endsuccess() 
    
    def create_windows_emi_from_url(self,
                                      url, 
                                      component = None, 
                                      component_credpath = None,
                                      bucketname = None, 
                                      destpath = None, 
                                      inter_bundle_timeout = None, 
                                      upload_timeout = None,
                                      wget_user = None,
                                      wget_password = None,
                                      time_per_gig = None,
                                      ):
        '''
        Attempts to download (wget), bundle, upload and register a windows image at 'url' 
        Work is done on a given machine and requires euca2ools present on that machine. 
        Returns the emi of the registered image
        '''
        
        return self.iu.create_emi_from_url(url, 
                                           component = (component or self.component), 
                                           bucketname = (bucketname or self.bucketname), 
                                           component_credpath = (component_credpath or self.component_credpath), 
                                           destination = (destpath or self.destpath),
                                           interbundle_timeout = (inter_bundle_timeout or self.inter_bundle_timeout), 
                                           upload_timeout = (upload_timeout or self.upload_timeout),
                                           destpath = (destpath or self.destpath),
                                           wget_user = (wget_user), 
                                           wget_password = (wget_password),   
                                           time_per_gig = (time_per_gig or self.time_per_gig) )
        
    def create_windows_emi_from_file(self,
                                     fpath,
                                     component = None, 
                                     component_credpath = None,
                                     bucketname = None, 
                                     destpath = None, 
                                     inter_bundle_timeout = None, 
                                     upload_timeout = None,
                                     time_per_gig = None,
                                     ):
        '''
        Attempts bundle, upload and register a windows image on component filesystem at fpath.  
        Work is done on a given machine and requires euca2ools present on that machine. 
        Returns the emi of the registered image
        '''
        return self.iu.create_emi_from_url(url, 
                                           component = (component or self.component), 
                                           bucketname = (bucketname or self.bucketname), 
                                           component_credpath = (component_credpath or self.component_credpath), 
                                           destination = (destpath or self.destpath),
                                           interbundle_timeout = (inter_bundle_timeout or self.inter_bundle_timeout), 
                                           upload_timeout = (upload_timeout or self.upload_timeout),
                                           destpath = (destpath or self.destpath),
                                           filepath = fpath,
                                           time_per_gig = (time_per_gig or self.time_per_gig) )
        
    def test_run_windows_emi(self,
                      emi=None, 
                      zone=None,
                      keypair=None,
                      type='m1.xlarge', 
                      group=None, 
                      min=1, 
                      max=1,
                      user_data=None,
                      private_addressing=False,
                      timeout=720):
        '''
        returns a reservation of running emi instances run with the provided parameters.
        '''
        emi = emi or self.emi
        if not emi:
            raise Exception('test_run_windows_emi, no emi provided. ')
        res = self.tester.run_instance(emi, 
                                 keypair = keypair or self.keypair.name, 
                                 group = group or self.group, 
                                 type = type, 
                                 zone=zone, 
                                 min=min, max=max, user_data=user_data, private_addressing=private_addressing, is_reachable=False, timeout=timeout)
        
        
        self.instance = res.instances[0]
        self.debug('test_run_windows_emi, setting test instance to:'+str(self.instance.id))
        self.debug('')
        return res
        
        
    
    
    
    
    def test_rdp_port(self, ip=None, port=3389):
        '''
        Attempts to connect to default windows remote desktop port 
        to verify the instance is accepting RDP connections
        '''
        ip = ip or self.instance.public_dns_name 
        if not ip:
            raise Exception('test_rdp_port, no ip given')
        self.debug('test_rdp_port, ip:'+str(ip)+', port:'+str(port))
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.connect((ip, port)) 
        except socket.error, se:
            self.debug('test_rdp_port failed socket error:'+str(se[0]))
            #handle specific errors here, for now just for debug...
            ecode=se[0]
            if ecode == socket.errno.ECONNREFUSED:
                self.debug("test_rdp_port: Connection Refused")
            if ecode == socket.errno.ENETUNREACH:
                self.debug("test_rdp_port: Network unreachable")
            raise se
        except socket.timeout, st:
            self.debug('test_rdp_port failed socket timeout')
            raise st
        finally:
            s.close()
        self.debug('test_rdp_port, success')
        
    def test_poll_for_rdp(self, ip=None, port=3389, count=10, interval=10, timeout=120):
        start = time.time()
        elapsed = 0 
        for x in xrange(0,count):
            elapsed = int(time.time() -start)
            if elapsed < timeout:
                try:
                    self.test_rdp_port(ip=ip, port=port)
                    return
                except Exception, e:
                    self.debug('Failed to connect to rdp at:'+str(ip)+', attempt:'+str(x)+'/'+str(count)+', elapsed:'+str(elapsed)+', err:'+str(e))
                    time.sleep(interval)
            else:
                self.debug('test_poll_for_rdp timeout after '+str(elapsed)+' seconds')
                break
        raise Exception('Could not connect to rdp at:'+str(ip)+', attempt:'+str(x)+'/'+str(count)+', elapsed:'+str(elapsed)+', err:'+str(e))
            
    
    def test_get_windows_emi(self):
        emi = None
        if self.emi is not None:
            self.debug("get_windows_emi returning provided emi:"+self.emi)
            emi = self.emi
        elif self.emi_location is not None:
            self.debug("get_windows_emi returning emi based on emi location"+str(self.emi_location))
            emi = self.tester.get_emi(location=self.emi_location)
        elif self.image_path is not None:
            self.debug("get_windows_emi attempting to create emi from image at path:"+str(self.image_path))
            emi = self.create_windows_emi_from_file(self.image_path)
        elif self.url is not None:
            self.debug("get_windows_emi attempting to create emi from url:"+str(self.url))
            emi = self.create_windows_emi_from_url(self.url)
        if not emi:
            raise Exception('test_get_windows_emi failed to get emi')
        self.emi = emi
        return emi

    def test_attach_single_volume(self):
        vol = None
        for vol in self.testvolumes:
            if vol.status == 'available':
                break
        if not vol:
            raise Exception('test_attach_single_volume, no available volumes')
        self.tester.attach_volume(self.instance, vol, device_path='/dev/sdc')
        #The guest test may not work on a 32bit host...
        self.proxy.ps_ebs_test(self.instance.public_dns_name, password=self.instance_password)
            
    
    def test_update_proxy_with_instance_info(self):
        self.debug('Updating proxy object with new instance info...')
        if not self.instance or not self.win_password:
            raise Exception('test_update_proxy_with_instance_info, instance and/or win_password None')
        self.proxy.win_instance = self.instance
        self.proxy.win_password = self.instance_password
        
    def is_kvm(self, component=None):
        component = component or self.component
        if (component.distro.name == machine.DistroName.rhel or component.distro.name == machine.DistroName.rhel) and int(component.distro.distro_number) < 6:
            return False
        else:
            return True
        
    def basic_proxy_test_suite(self):
        list = []
        list.append(self.create_testcase_from_method(self.test_get_windows_emi))
        list.append(self.test_get_windows_instance_password)
        list.append(self.test_rdp_port)
        list.append(self.test_update_proxy_with_instance_info)
        list.append(self.proxy.ps_login_test)
        list.append(self.proxy.ps_ephemeral_test)
        list.append(self.proxy.ps_hostname_test)
        list.append(self.set_windows_test_volumes)
        list.append(self.test_attach_single_volume)
        list.append(self.proxy.ps_hostname_test)
        if self.is_kvm(): 
            list.append(self.proxy.ps_virtio_test)
        else:
            list.append(self.proxy.ps_xenpv_test)
            
        self.run_test_case_list(list)
        
            
        
    
        
        
    
        
    
        
        
        
        