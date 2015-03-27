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
from eutester.eutestcase import EutesterTestCase
from eutester import Eutester
from eutester import machine
from testcases.cloud_user.images.imageutils import ImageUtils
from testcases.cloud_user.ebs.ebstestsuite import TestZone
from eutester.euvolume import EuVolume
import socket
import os
import time
import re
from datetime import datetime

class WindowsTests(EutesterTestCase):
    
    def __init__(self,
                 #setup eutester and test environment...
                 tester=None, 
                 config_file=None,
                 password=None, 
                 credpath=None, 
                 eof=True,
                 #Information on where to do image bundle work, and related timeouts
                 destpath=None,  
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
                 user_data=None,
                 emi=None,
                 private_addressing=False,
                 instance_password = None,
                 instance_keypath = None,
                 vmtype='m1.xlarge',
                 emi_location=None,
                 image_path=None, #note this must be available on the work_component
                 instance=None,
                 clean_on_exit=False,
                 authports=['tcp:3389','tcp:80','tcp:443', 'tcp:5985', 'tcp:5986']
                 ):
        """
        Definition:
        This class is intended to hold most of the methods and state(s) needed to run an array of Windows Instance
        related tests. Most TestUnits will use a subset of these methods to define a testcase/operation. See sample
        testcases scripts which reference this class for examples and use cases.

        :param tester: eutester object
        :param config_file: eutester config file
        :param credpath: path to cloud credentials/eucarc
        :param password: password used to access remote components
        :param eof: boolean, end on failure
        :param destpath: path on 'work component' in which to peform work. ie: where to download and bundle an img.
        :param time_per_gig: Time in seconds to be used for image related timeouts
        :param inter_bundle_timeout: Time to wait between bundle operation. Mainly used to detect hung operations
        :param upload_timeout: Time to wait for the upload portion of image operation
        :param work_component: The component or machine in which work is to be executed on, ie download, bundles, etc.
        :param component_credpath: The path on the 'work_component' in which to find creds. ie for tools exectuted remotely
        :param bucketname: Bucketname to be used as a global for operations in this test.
        :param group: Security group to use for this test
        :param testvolumes: List of volumes that are intended to be used in by this obj's test(s)
        :param testvolcount: Number of volumes to be used for ebs related tests defined in this test obj
        :param keypair: keypair ot be used for this test(s)
        :param zone: zone/cluster to be used to executue these tests
        :param url: url to use for fetching remote images to be built into EMI(s) for this test
        :param user_data: Any (instance) user data to be used for in this test
        :param emi: emi to be used for this test
        :param private_addressing: boolean, used to run instances w/o a public ip
        :param instance_password: password used for accessing instance(s) within this test
        :param instance_keypath: keypath used to access instance(s) within this test
        :param vmtype: type of vm to use when running instance(s) in this test, ie m1.xlarge
        :param emi_location: string used to find an existing EMI by the EMI's location-string
        :param image_path: path to an image on the local machine or work component
        :param instance: existing instance to use within this test
        :param win_proxy_hostname: The ip or FQDN of the machine used to proxy powershell and ldap tests against
        :param win_proxy_username: The user name for ssh login on the machine used to  proxy powershell and ldap tests against
        :param win_proxy_password: The password for ssh login on the machine used to  proxy powershell and ldap tests against
        :param win_proxy_keypath: The keypath for ssh login on the machine used to  proxy powershell and ldap tests against
        :param authports: What ports should be authorized within security group for testing
        """
        self.setuptestcase()
        if tester is None:
            self.tester = Eucaops( config_file=config_file,password=password,credpath=credpath)
        else:
            self.tester = tester
        self.tester.exit_on_fail = eof
        self.instance = instance
        if self.instance:
            self.instance = self.tester.get_instances(idstring=str(instance))[0]
        self.instance_keypath = instance_keypath
        self.destpath = destpath or '/tmp'
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
        self.authports=authports
        self.instance_password = instance_password
        self.vmtype= vmtype 
        self.user_data = user_data
        self.private_addressing = private_addressing
        #timeout for run instance command/test
        self.run_timeout=780 
        #setup zone list
        self.setupWindowsZones()
        #setup windows proxy
        self.setup_test_env()

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

    def setupWindowsSecurityGroup(self, portlist=None):
        portlist = portlist or self.authports
        #Setup our security group for later use...
        if self.group is None:
            
            group_name='WindowsTestGroup'
            try:
                self.group = self.tester.add_group(group_name)
                self.setupWindowsGroupAuthorization(portlist=portlist)
                #enable windows RDP port
            except Exception, e:    
                raise Exception("Error when setting up group:"+str(group_name)+", Error:"+str(e)) 
         
    def setupWindowsGroupAuthorization(self,portlist=None):
        '''
        Where format for adding port in list is: 'protocol:port', example: tcp, port 80 = 'tcp:80'
        '''
        authports = portlist or self.authports
        for p in authports:
            protocol,port = str(p).split(':')
            self.tester.authorize_group_by_name(self.group.name,protocol=str(protocol),port=int(port)) 
            
        
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
        privkeypath = privkeypath or self.tester.verify_local_keypath(instance.key_name) 
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
                
    def setup_windows_test_volumes(self):
        '''
        Description:
            Attempts to confirm that each zone provided has the minimum number of volumes in it. 
            If volumes were provided in __init__ then this method will attempt to sort those into the zone. 
            Volumes will be created if the testzones do not have the amount specified. 
        Failure:
            Failed to create volumes for use in windows test
        '''
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
                vol = EuVolume.make_euvol_from_vol(self.tester.create_volume(zone, size=size, snapshot=snapshot,timepergig=timepergig))
                testzone.volumes.append(vol)
                self.debug('create_vols_per_zone created  vol('+str(x)+') zone:'+str(zone)+' vol:'+str(vol.id))
            
        self.endtestunit()
    
    def create_windows_emi_from_url(self,
                                      url=None, 
                                      component = None, 
                                      component_credpath = None,
                                      bucketname = None, 
                                      destpath = None, 
                                      inter_bundle_timeout = None, 
                                      upload_timeout = None,
                                      virtualization_type = None,
                                      wget_user = None,
                                      wget_password = None,
                                      time_per_gig = None,
                                      ):
        '''
        Attempts to download (wget), bundle, upload and register a windows image at 'url' 
        Work is done on a given machine and requires euca2ools present on that machine. 
        Returns the emi of the registered image
        '''
        return self.iu.create_emi(url = (url or self.url),
                                           component = (component or self.component), 
                                           bucketname = (bucketname or self.bucketname), 
                                           component_credpath = (component_credpath or self.component_credpath), 
                                           destination = (destpath or self.destpath),
                                           interbundle_timeout = (inter_bundle_timeout or self.inter_bundle_timeout), 
                                           upload_timeout = (upload_timeout or self.upload_timeout),
                                           destpath = (destpath or self.destpath),
                                           virtualization_type=virtualization_type,
                                           wget_user = (wget_user), 
                                           wget_password = (wget_password),   
                                           time_per_gig = (time_per_gig or self.time_per_gig) )
        
    def create_windows_emi_from_file(self,
                                     image_file_path,
                                     component = None, 
                                     component_credpath = None,
                                     bucketname = None, 
                                     destpath = None, 
                                     inter_bundle_timeout = None, 
                                     upload_timeout = None,
                                     time_per_gig = None,
                                     ):
        '''
        Definition: Attempts bundle, upload and register a windows image on component filesystem at fpath.  
        Work is done on a given machine and requires euca2ools present on that machine. 
        Returns the emi of the registered image
        '''
        return self.iu.create_emi( url = None,
                                   component = (component or self.component),
                                   bucketname = (bucketname or self.bucketname),
                                   component_credpath = (component_credpath or self.component_credpath),
                                   destination = (destpath or self.destpath),
                                   interbundle_timeout = (inter_bundle_timeout or self.inter_bundle_timeout),
                                   upload_timeout = (upload_timeout or self.upload_timeout),
                                   destpath = (destpath or self.destpath),
                                   filepath = image_file_path,
                                   time_per_gig = (time_per_gig or self.time_per_gig) )
        
    def test_run_windows_emi(self,
                              emi=None,
                              zone=None,
                              keypair=None,
                              type=None,
                              group=None,
                              min=1,
                              max=1,
                              user_data=None,
                              private_addressing=None,
                              timeout=None):
        '''
        Description: Attempts to return a reservation of running emi instances run with the provided parameters.
        '''
        emi = emi or self.emi
        zone = zone or self.zonelist[0] if self.zonelist else None
        keypair = keypair or self.keypair
        type = type or self.vmtype or 'm1.xlarge'
        group = group or self.group
        user_data = user_data or self.user_data
        private_addressing = private_addressing if private_addressing is not None else self.private_addressing
        timeout = timeout or self.run_timeout
        if not emi:
            raise Exception('test_run_windows_emi, no emi provided. ')
        res = self.tester.run_instance(emi, 
                                 keypair = keypair or self.keypair.name, 
                                 group = group or self.group, 
                                 type = type, 
                                 zone=zone, 
                                 min=min,
                                 max=max,
                                 user_data=user_data,
                                 private_addressing=private_addressing,
                                 is_reachable=False,
                                 timeout=timeout)
        
        
        self.instance = res.instances[0]
        self.debug('test_run_windows_emi, setting test instance to:'+str(self.instance.id))
        self.debug('')
        return res
        
        
    
    def test_rdp_port(self, ip=None, port=3389, timeout=10):
        '''
        Description: Attempts to test that the host is accepting tcp connections to the RDP port
        '''
        return self.test_port_status(ip=ip, port=port, timeout=timeout)
    
    
    def scan_port_range(self, start,stop,ip=None,timeout=1, tcp=True):
        ip = ip or self.instance.public_dns_name 
        return self.tester.scan_port_range(ip, int(start),int(stop), timeout=int(timeout), tcp=tcp)
    
    def test_port_status(self, port, ip=None, timeout=5, tcp=True, verbose=True):
        ip = ip or self.instance.public_dns_name 
        return self.tester.test_port_status(ip, port, timeout=timeout, tcp=tcp, verbose=verbose)

    def test_poll_for_rdp_port_status(self, instance=None,interval=10,socktimeout=5,timeout=180, waitforboot=120):
        instance = instance or self.instance
        if not instance:
            raise Exception("No instance available to test with, please add to windowstests or provide to method")
        #Make sure some time has passed before we test on the guest side before running guest test...
        attached_seconds = self.tester.get_instance_time_launched(instance)
        sleeptime =  0 if attached_seconds > waitforboot else (waitforboot - attached_seconds)
        self.debug("Instance was launched "+str(attached_seconds)+" seconds ago, waiting:"+str(sleeptime)+" for instance to boot")
        time.sleep(sleeptime)
        ip = instance.public_dns_name
        return self.test_poll_for_port_status(3389, ip=ip, interval=interval, socktimeout=socktimeout, timeout=timeout)
    
    def test_wait_for_instance_boot(self,instance=None,waitforboot=420):
        instance = instance or self.instance
        boot_seconds = self.tester.get_instance_time_launched(instance)
        sleeptime =  0 if boot_seconds > waitforboot else (waitforboot - boot_seconds)
        self.debug("Instance was launched "+str(boot_seconds)+" seconds ago, waiting:"+str(sleeptime)+" for instance to boot")
        start = time.time()
        elapsed = 0
        print "Waiting for Windows to fully boot:",
        while elapsed < sleeptime:
            print "Waiting for Windows to fully boot:"+str(sleeptime-elapsed),
            time.sleep(5)
            elapsed=int(time.time()-start)
        self.debug("test_wait_for_instance_boot: done waiting, instance up for "+str(waitforboot)+" seconds") 
    
    def test_poll_for_port_status(self, port, ip=None, interval=10, socktimeout=5, timeout=180):
        ip = ip or self.instance.public_dns_name
        start = time.time()
        elapsed = 0 
        attempt = 0
        while elapsed < timeout:
            attempt +=1 
            self.debug('test_poll_for_port_status:'+str(attempt))
            if elapsed < timeout:
                try:
                    self.test_rdp_port(ip=ip, port=port, timeout=5)
                    return
                except socket.error, se:
                    self.debug('test_port_status failed socket error:'+str(se[0]))
                    #handle specific errors here, for now just for debug...
                    ecode=se[0]
                    if ecode == socket.errno.ETIMEDOUT or ecode == "timed out":
                        self.debug("test_poll_for_port_status: Connect "+str(ip)+":" +str(port)+ " timed out retrying. Time remaining("+str(timeout-elapsed)+")")
                except Exception, e:
                    self.debug('test_poll_for_port_status:'+str(ip)+':'+str(port)+' FAILED after attempts:'+str(attempt)+', elapsed:'+str(elapsed)+', err:'+str(e) )
                time.sleep(interval)
                elapsed = int(time.time() -start)    
        raise Exception('test_poll_for_port_status:'+str(ip)+':'+str(port)+' FAILED after attempts:'+str(attempt)+', elapsed:'+str(elapsed)+' seconds')
            
    def get_windows_emi(self):
        emi = None
        if self.emi is not None:
            self.debug("get_windows_emi returning provided emi:"+str(self.emi))
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
    
    def find_windows_instance(self,emi=None, location=None):
        self.debug('find_windows_instance attempting to find a pre-existing and running instance...')
        emi = emi or self.emi
        if not emi and location is not None:
            emi = self.get_images_by_location(location)
        if not emi:
            raise Exception("find_windows_instance: No emi provided, and could not find emi to match against instances")
        self.debug("Using emi:"+str(emi)+" to look for running instances...")
        instances = self.tester.get_instances(state='running',image_id=emi.id )
        self.debug("Returning instance list:"+str(instances))
        return instances
    
    def get_windows_instance(self):
        self.debug("get_windows_instance, check to see if we've been provided a running instance...")
        if self.instance:
            self.instance.update()
            if self.instance.state == 'running':
                return
        instances = self.find_windows_instance()
        for instance in instances:
            if instance.state =='running':
                try:
                    keypair = self.get_local_key_for_instance(instance)
                    self.instance = instance
                    self.keypair = keypair
                    return instance
                except: pass
        #We need to create a new instance...
        self.get_windows_emi()
        self.test_run_windows_emi()
        
    def get_local_key_for_instance(self,instance,keypath=None, exten=".pem"):
        self.debug("Looking for local keys for instance:"+str(instance.id))
        keypath = keypath or self.instance_keypath
        keys = self.tester.get_all_current_local_keys(path=keypath, exten=exten)
        for key in keys:
            if key.name == instance.key_name:
                self.debug("Found key:"+str(key.name))
                return key
        raise Exception("No local key found for "+str(instance.id)+":"+str(instance.key_name)+", at path:"+str(keypath)+" exten:"+str(exten))
        
        
    def get_free_ebs_devname(self, instance=None, max=16):
        self.debug('get_free_ebs_dev_name starting...')
        instance = instance or self.instance
        attachedvols = self.tester.get_volumes(attached_instance=instance.id)
        count=0
        for x in xrange(0,(max-1)):
            d = chr(ord('c') + x)
            dev = '/dev/sd'+str(d)
            in_use = False
            for volume in attachedvols:
                if volume.attach_data.device == dev:
                    in_use = True
                    count += 1
                    continue
            if not in_use:
                self.debug("get_free_ebs_devname: Got "+str(dev))
                return dev
        raise Exception('Instance:'+str(instance.id)+", no free devs. Has "+str(count)+" devices in use by ebs already. max:"+str(max))    
        

           
    def test_attach_single_volume(self, instance=None, dev=None):
        instance = instance or self.instance
        if instance is None:
            raise Exception('test_attach_single_volume: instance is None')
        vol = None
        for zone in self.zonelist:
            self.debug('Checking for available volumes in zone:'+str(zone.name))
            if zone.name == instance.placement:
                self.debug('Checking Volume:'+str(zone.name))
                for volume in zone.volumes:
                    if volume.status == 'available':
                        self.debug('Found Available Volume:'+str(volume.id))
                        vol = volume
                        break
        if not vol:
            raise Exception('test_attach_single_volume, no available volumes')
        if dev is None:
            dev = self.get_free_ebs_devname(instance=instance)
        self.tester.attach_volume(self.instance, vol, device_path=dev)
        

        
    def is_kvm(self, component=None):
        component = component or self.component or self.tester.get_component_machines("nc")[0]
        if (component.distro.name == machine.DistroName.rhel or component.distro.name == machine.DistroName.rhel) and int(component.distro.distro_number) < 6:
            return False
        else:
            return True
        
    def setup_active_dir_dns(self,zone=None,ad_dns=None):
        ad_dns = ad_dns or self.win_proxy_hostname 
        if not ad_dns:
            if hasattr(self, 'proxy') and self.proxy:
                ad_dns = self.proxy.proxy_hostname
            else:
                raise Exception('Need hostname/ip of AD DNS to use?')
        if not zone:
            for zone in self.zonelist:
                if zone.name == self.instance.placement:
                    break
        if not zone:
            raise Exception('setup_active_dir_dns zone unknown')
        self.debug("setup_active_dir_dns starting, zone:"+str(zone)+", dns:"+str(ad_dns))
        ccs = zone.partition.ccs
        for cc in ccs:
            #update the CC of this zone to use this DNS server...
            cmd = 'sed -i \'s/VNET_DNS.*$/VNET_DNS="'+str(ad_dns)+'"/g\' '+str(self.tester.eucapath)+'/etc/eucalyptus/eucalyptus.conf'
            self.debug('Attempting to update VNET DNS on:'+str(cc.hostname)+', cmd:'+str(cmd))
            cc.machine.sys(cmd,code=0)
            cc.stop()    
        zone.partition.service_manager.wait_for_service(cc, state='NOTREADY',timeout=120)
        for cc in ccs:
            cc.start()
        zone.partition.service_manager.wait_for_service(cc, state='ENABLED',timeout=120)
        self.debug("setup_active_dir VNET_DNS done")




    
        
    
        
        
        
        
