# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2014, Eucalyptus Systems, Inc.
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
# Author: vic.iglesias@eucalyptus.com
# Author: matt.clark@eucalyptus.com

from boto.ec2.image import Image
from boto.ec2.volume import Volume
from cwops import CWops
from asops import ASops
from eucaops.cfnops import CFNops
from eucaops.elbops import ELBops
from iamops import IAMops
from ec2ops import EC2ops
from s3ops import S3ops
from stsops import STSops
import time
import traceback
import sys
import StringIO
from eutester.euservice import EuserviceManager
from boto.ec2.instance import Reservation
from boto.exception import EC2ResponseError
from eutester.euconfig import EuConfig
from eutester.euproperties import Euproperty_Manager
from eutester.machine import Machine
from eutester.euvolume import EuVolume
from eutester import eulogger
import re
import os

class Eucaops(EC2ops,S3ops,IAMops,STSops,CWops, ASops, ELBops, CFNops):
    
    def __init__(self, config_file=None, password=None, keypath=None, credpath=None, aws_access_key_id=None,
                 aws_secret_access_key = None,  account="eucalyptus", user="admin", username=None, APIVersion='2011-01-01',
                 ec2_ip=None, ec2_path=None, iam_ip=None, iam_path=None, s3_ip=None, s3_path=None,
                 as_ip=None, as_path=None, elb_ip=None, elb_path=None, cw_ip=None, cw_path=None,
                 cfn_ip=None, cfn_path=None, sts_ip=None, sts_path=None,
                 port=8773, download_creds=True, boto_debug=0, debug_method=None, region=None):
        self.config_file = config_file 
        self.APIVersion = APIVersion
        self.eucapath = "/opt/eucalyptus"
        self.ssh = None
        self.sftp = None
        self.clc = None
        self.password = password
        self.keypath = keypath
        self.timeout = 30
        self.delay = 0
        self.exit_on_fail = 0
        self.fail_count = 0
        self.start_time = time.time()
        self.key_dir = "./"
        self.clc_index = 0
        self.credpath = credpath
        self.account_name = account
        self.aws_username = user
        self.download_creds = download_creds
        self.logger = eulogger.Eulogger(identifier="EUCAOPS")
        self.debug = debug_method or self.logger.log.debug
        self.critical = self.logger.log.critical
        self.info = self.logger.log.info
        self.username = username
        self.account_id = None
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self._property_manager = None


        if self.config_file is not None:
            ## read in the config file
            self.debug("Reading config file: " + config_file)
            self.config = self.read_config(config_file)

            ### Set the eucapath
            try:
                if "REPO" in self.config["machines"][0].source:
                    self.eucapath="/"
            except Exception, e:
                raise Exception("Could not get REPO info from input file\n" + str(e))

            ### No credpath but does have password and an ssh connection to the CLC
            ### Private cloud with root access 
            ### Need to get credentials for the user if there arent any passed in
            ### Need to create service manager for user if we have an ssh connection and password
            clc_array = self.get_component_machines("clc")
            self.clc = clc_array[0]
            self.sftp = self.clc.ssh.connection.open_sftp()
            if self.download_creds:
                if self.credpath is None:
                    ### TRY TO GET CREDS ON FIRST CLC if it fails try on second listed clc, if that fails weve hit a terminal condition
                    try:
                        self.debug("Attempting to get credentials and setup sftp")
                        self.sftp = self.clc.ssh.connection.open_sftp()
                        self.credpath = self.get_credentials(account,user)
                        self.debug("Successfully downloaded and synced credentials")
                    except Exception, e:
                        tb = self.get_traceback()
                        self.debug("Caught an exception when getting credentials from first CLC: " + str(e))
                        ### If i only have one clc this is a critical failure, else try on the other clc
                        if len(clc_array) < 2:
                            raise Exception(str(tb) + "\nCould not get credentials from first CLC and no other to try")
                        self.swap_clc()
                        self.sftp = self.clc.ssh.connection.open_sftp()
                        self.get_credentials(account, user)
                        
                self.service_manager = EuserviceManager(self)
                self.clc = self.service_manager.get_enabled_clc().machine

        if self.credpath and not aws_access_key_id:
            aws_access_key_id = self.get_access_key()
        if self.credpath and not aws_secret_access_key:
            aws_secret_access_key = self.get_secret_key()
        self.test_resources = {}
        if self.download_creds:
            try:
                if self.credpath and not ec2_ip:
                    ec2_ip = self.get_ec2_ip()
                if self.credpath and not ec2_path:
                    ec2_path = self.get_ec2_path()

                self.setup_ec2_connection(endpoint=ec2_ip, path=ec2_path, port=port, is_secure=False,
                                          region=region, aws_access_key_id=aws_access_key_id,
                                          aws_secret_access_key=aws_secret_access_key, APIVersion=APIVersion,
                                          boto_debug=boto_debug)
                self.setup_ec2_resource_trackers()

                if self.credpath and not iam_ip:
                    iam_ip = self.get_iam_ip()
                if self.credpath and not iam_path:
                    iam_path = self.get_iam_path()
                self.setup_iam_connection(endpoint=iam_ip, path=iam_path,
                                          port=port, is_secure=False, aws_access_key_id=aws_access_key_id,
                                          aws_secret_access_key=aws_secret_access_key, boto_debug=boto_debug)

                if self.credpath and not sts_ip:
                    sts_ip = self.get_sts_ip()
                if self.credpath and not sts_path:
                    sts_path = self.get_sts_path()
                self.setup_sts_connection(endpoint=sts_ip, path=sts_path, port=port, is_secure=False,
                                          region=region, aws_access_key_id=aws_access_key_id,
                                          aws_secret_access_key=aws_secret_access_key, boto_debug=boto_debug)

                if self.credpath and not cw_ip:
                    cw_ip = self.get_cw_ip()
                if self.credpath and not cw_path:
                    cw_path = self.get_cw_path()
                self.setup_cw_connection(endpoint=cw_ip, path=cw_path, port=port, is_secure=False,
                                         region=region, aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key, boto_debug=boto_debug)

                self.setup_cw_resource_trackers()
            except Exception, e:
                tb = self.get_traceback()
                raise Exception(tb + "\nUnable to create EC2 connection because of: " + str(e) )

            try:
                if self.credpath and not s3_ip:
                    s3_ip = self.get_s3_ip()
                if self.credpath and not s3_path:
                    s3_path = self.get_s3_path()
                self.setup_s3_connection(endpoint=s3_ip, path=s3_path, port=port, is_secure=False,
                                         aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key,
                                         boto_debug=boto_debug)
                self.setup_s3_resource_trackers()
            except Exception, e:
                self.debug("Unable to create S3 connection because of: " + str(e) )

            try:
                if self.credpath and not as_ip:
                    as_ip = self.get_as_ip()
                if self.credpath and not as_path:
                    as_path = self.get_as_path()
                self.setup_as_connection(endpoint=as_ip, path=as_path, port=port, is_secure=False,
                                         region=region, aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key, boto_debug=boto_debug)
            except Exception, e:
                self.debug("Unable to create AS connection because of: " + str(e) )

            try:
                if self.credpath and not elb_ip:
                    elb_ip = self.get_elb_ip()
                if self.credpath and not elb_path:
                    elb_path = self.get_elb_path()
                self.setup_elb_connection(endpoint=elb_ip, path=elb_path, port=port, is_secure=False,
                                          region=region, aws_access_key_id=aws_access_key_id,
                                          aws_secret_access_key=aws_secret_access_key, boto_debug=boto_debug)
            except Exception, e:
                self.debug("Unable to create ELB connection because of: " + str(e) )
            try:
                if self.credpath and not cfn_ip:
                    cfn_ip = self.get_cfn_ip()
                if self.credpath and not cfn_path:
                    cfn_path = self.get_cfn_path()
                self.setup_cfn_connection(endpoint=cfn_ip, path=self.get_cfn_path(), port=port, is_secure=False,
                                          region=region, aws_access_key_id=aws_access_key_id,
                                          aws_secret_access_key=aws_secret_access_key, boto_debug=boto_debug)
            except Exception, e:
                self.debug("Unable to create CloudFormation connection because of: " + str(e) )



    @property
    def property_manager(self):
        if not self._property_manager:
            if self.clc and self.account_name == 'eucalyptus':
                try:
                    self.update_property_manager()
                except:
                    tb = self.get_traceback()
                    self.debug(str(tb) + '\nError creating properties manager')
        return self._property_manager


    @property_manager.setter
    def property_manager(self, new_property_mgr):
        self._property_manager = new_property_mgr

    def get_available_vms(self, type=None, zone=None):
        """
        Get available VMs of a certain type, defaults to m1.small
        type        VM type to get available vms 
        """
        
        zones = self.ec2.get_all_zones("verbose")
        if type is None:
            type = "m1.small"
        ### Look for the right place to start parsing the zones
        zone_index = 0
        if zone is not None:
            while zone_index < len(zones):
                current_zone = zones[zone_index]
                if re.search( zone, current_zone.name):
                    break
                zone_index += 20
            if zone_index > (len(zones) - 1):
                raise Exception("Unable to find Availability Zone")    
        else:
            zone = zones[0].name
            
        ### Inline switch statement
        type_index = {  "t1.micro": 2,
                        "m1.small": 3,
                        "m1.large": 4,
                        "m1.xlarge" : 5,
                        "c1.xlarge" : 6,
                        "m2.xlarge" : 7,
                        "c1.medium" : 8,
                        "m1.medium" : 9,
                        "m3.xlarge" : 10,
                        "m2.2xlarge" : 11,
                        "m3.2xlarge" : 12,
                        "m2.4xlarge" : 13,
                        "cc1.4xlarge" : 14,
                        "hi1.4xlarge" : 15,
                        "cc2.8xlarge" : 16,
                        "cg1.4xlarge" : 17,
                        "cr1.8xlarge" : 18,
                        "hs1.8xlarge" : 19
                      }[type] 
        type_state = zones[ zone_index + type_index ].state.split()
        self.debug("Finding available VMs: Partition=" + zone +" Type= " + type + " Number=" +  str(int(type_state[0])) )
        return int(type_state[0])
        
    
    
            
    def modify_property(self, property, value):
        """
        Modify a eucalyptus property through the command line euca-modify-property tool
        property        Property to modify
        value           Value to set it too
        """
        if self.credpath == None or self.eucapath == None or property == None or value == None:
            self.fail("Cannot set property value due to insufficient arguments")
            self.fail("credpath: " + ("None" if self.credpath is None else self.credpath))
            self.fail("eucapath: " + ("None" if self.eucapath is None else self.eucapath))
            self.fail("property: " + ("None" if property is None else property))
            self.fail("value: " + ("None" if value is None else value))
            raise Exception("Cannot set property: " + (property if property is not None else "unknown"))
        
        command = "source " + self.credpath + "/eucarc && " + self.eucapath + "/usr/sbin/euca-modify-property -p " + property + "=" + value
        if self.clc.found(command, property):
            self.debug("Properly modified property " + property)
        else:
            raise Exception("Setting property " + property + " failed")


    def cleanup_artifacts(self,instances=True, snapshots=True, volumes=True,
                          load_balancers=True, ip_addresses=True,
                          auto_scaling_groups=True, launch_configurations=True,
                          keypairs=True):
        """
        Description: Attempts to remove artifacts created during and through this eutester's lifespan.
        """
        failmsg = ""
        failcount = 0
        self.debug("Starting cleanup of artifacts")
        if auto_scaling_groups:
            try:
                self.cleanup_autoscaling_groups()
            except Exception, e:
                tb = self.get_traceback()
                failcount +=1
                failmsg += str(tb) + "\nError#:"+ str(failcount)+ ":" + str(e)+"\n"
        if instances:
            for res in self.test_resources["reservations"]:
                try:
                    self.terminate_instances(res)
                    if res in self.test_resources["reservations"]:
                        self.test_resources["reservations"].remove(res)
                except Exception, e:
                    tb = self.get_traceback()
                    failcount +=1
                    failmsg += str(tb) + "\nError#:"+ str(failcount)+ ":" + str(e)+"\n"
        if ip_addresses:
            try:
                self.cleanup_addresses()
            except Exception, e:
                tb = self.get_traceback()
                failcount +=1
                failmsg += str(tb) + "\nError#:"+ str(failcount)+ ":" + str(e)+"\n"
        if volumes:
            try:
                self.clean_up_test_volumes(timeout_per_vol=60)
                self.test_resources['volumes']=[]
            except Exception, e:
                tb = self.get_traceback()
                failcount +=1
                failmsg += str(tb) + "\nError#:"+ str(failcount)+ ":" + str(e)+"\n"
        if snapshots:
            try:
                self.cleanup_test_snapshots()
            except Exception, e:
                tb = self.get_traceback()
                failcount +=1
                failmsg += str(tb) + "\nError#:"+ str(failcount)+ ":" + str(e)+"\n"
        if load_balancers:
            try:
                self.cleanup_load_balancers()
            except Exception, e:
                tb = self.get_traceback()
                failcount +=1
                failmsg += str(tb) + "\nError#:"+ str(failcount)+ ":" + str(e)+"\n"

        if launch_configurations:
            try:
                self.cleanup_launch_configs()
            except Exception, e:
                tb = self.get_traceback()
                failcount +=1
                failmsg += str(tb) + "\nError#:"+ str(failcount)+ ":" + str(e)+"\n"

        for key,array in self.test_resources.iteritems():
            for item in array:
                try:
                    ### SWITCH statement for particulars of removing a certain type of resources
                    self.debug("Deleting " + str(item))
                    if isinstance(item, Image):
                        item.deregister()
                    elif isinstance(item,Reservation):
                        continue
                    else:
                        try:
                            item.delete()
                        except EC2ResponseError as ec2re:
                            if ec2re.status == 400:
                                self.debug('Resource not found assuming it is'
                                           ' already deleted, resource:'
                                           + str(item))
                except Exception, e:
                    tb = self.get_traceback()
                    failcount += 1
                    failmsg += str(tb) + "\nUnable to delete item: " + str(item) + "\n" + str(e)+"\n"
        if failmsg:
            failmsg += "\nFound " + str(failcount) + " number of errors while cleaning up. See above"
            raise Exception(failmsg)
        if launch_configurations:
            try:
                self.cleanup_launch_configs()
            except Exception, e:
                tb = self.get_traceback()
                failcount +=1
                failmsg += str(tb) + "\nError#:"+ str(failcount)+ ":" + str(e)+"\n"


    def cleanup_load_balancers(self, lbs=None):
        """
        :param lbs: optional list of load balancers, otherwise it will attempt to delete from test_resources[]
        """
        if lbs:
            self.delete_load_balancers(lbs)
        else:
            try:
                self.delete_load_balancers(self.test_resources['load_balancers'])
            except KeyError:
                self.debug("No loadbalancers to delete")

    def cleanup_addresses(self, ips=None):
        """
        :param ips: optional list of ip addresses, else will attempt to delete from test_resources[]

        """
        addresses = ips or self.test_resources['addresses']
        if not addresses:
            return

        self.debug('Attempting to release to the cloud the following IP addresses:')

        while addresses:
            self.release_address(addresses.pop())


    def cleanup_test_snapshots(self,snaps=None, clean_images=False, add_time_per_snap=10, wait_for_valid_state=120, base_timeout=180):
        """
        :param snaps: optional list of snapshots, else will attempt to delete from test_resources[]
        :param clean_images: Boolean, if set will attempt to delete registered images referencing the snapshots first.
                             Images referencing the snapshot may prevent snapshot deletion to protect the image.
        :param add_time_per_snap:  int number of seconds to append to base_timeout per snapshot
        :param wait_for_valid_state: int seconds to wait for snapshot(s) to enter a 'deletable' state
        :param base_timeout: base timeout to use before giving up, and failing operation.
        """
        snaps = snaps or self.test_resources['snapshots']
        if not snaps:
            return
        self.debug('Attempting to clean the following snapshots:')
        self.print_eusnapshot_list(snaps)
        if clean_images:
            for snap in snaps:
                for image in self.test_resources['images']:
                    for dev in image.block_device_mapping:
                        if image.block_device_mapping[dev].snapshot_id == snap.id:
                            self.delete_image(image)
        if snaps:
            return self.delete_snapshots(snaps,
                                        base_timeout=base_timeout,
                                        add_time_per_snap=add_time_per_snap,
                                        wait_for_valid_state=wait_for_valid_state)




    def clean_up_test_volumes(self, volumes=None, min_timeout=180, timeout_per_vol=30):
        """
        Definition: cleaup helper method intended to clean up volumes created within a test, after the test has ran.

        :param volumes: optional list of volumes to delete from system, otherwise will use test_resources['volumes']
        """
        euvolumes = []
        detaching = []
        not_exist = []
        line = '\n----------------------------------------------------------------------------------------------------\n'

        volumes = volumes or self.test_resources['volumes']
        if not volumes:
            self.debug('clean_up_test_volumes, no volumes passed to delete')
            return
        self.debug('clean_up_test_volumes starting\nVolumes to be deleted:' + ",".join(str(x) for x in volumes))

        for vol in volumes:
            try:
                vol = self.get_volume(volume_id=vol.id)
            except:
                tb = self.get_traceback()
                self.debug("\n" + line + " Ignoring caught Exception:\n" + str(tb) + "\n"+ str(vol.id) +
                           ', Could not retrieve volume, may no longer exist?' + line)
                if vol in self.test_resources['volumes']:
                    self.test_resources['volumes'].remove(vol)
                vol = None
            if vol:
                try:
                    vol.update()
                    if not isinstance(vol, EuVolume):
                        vol = EuVolume.make_euvol_from_vol(vol, self)
                    euvolumes.append(vol)
                except:
                    tb = self.get_traceback()
                    self.debug('Ignoring caught Exception: \n' + str(tb))
        try:
            self.debug('Attempting to clean up the following volumes:')
            self.print_euvolume_list(euvolumes)
        except: pass
        self.debug('Clean_up_volumes: Detaching any attached volumes to be deleted...')
        for vol in euvolumes:
            try:
                vol.update()
                if vol.status == 'in-use':
                    if vol.attach_data and (vol.attach_data.status != 'detaching' or vol.attach_data.status != 'detached'):
                        try:
                            self.debug(str(vol.id) + ', Sending detach. Status:' +str(vol.status) +
                                       ', attach_data.status:' + str(vol.attach_data.status))
                            vol.detach()
                        except EC2ResponseError, be:
                            if 'Volume does not exist' in be.error_message:
                                not_exist.append(vol)
                                self.debug(str(vol.id) + ', volume no longer exists')
                            else:
                                raise be
                    detaching.append(vol)
            except:
                print self.get_traceback()
        #If the volume was found to no longer exist on the system, remove it from further monitoring...
        for vol in not_exist:
            if vol in detaching:
                detaching.remove(vol)
            if vol in euvolumes:
                euvolumes.remove(vol)
        self.test_resources['volumes'] = euvolumes
        timeout = min_timeout + (len(volumes) * timeout_per_vol)
        #If detaching wait for detaching to transition to detached...
        if detaching:
            self.monitor_euvolumes_to_status(detaching, status='available', attached_status=None,timeout=timeout)
        self.debug('clean_up_volumes: Deleteing volumes now...')
        self.print_euvolume_list(euvolumes)
        if euvolumes:
            self.delete_volumes(euvolumes, timeout=timeout)

                    
    def get_current_resources(self,verbose=False):
        '''Return a dictionary with all known resources the system has. Optional pass the verbose=True flag to print this info to the logs
           Included resources are: addresses, images, instances, key_pairs, security_groups, snapshots, volumes, zones
        '''
        current_artifacts = dict()
        current_artifacts["addresses"] = self.ec2.get_all_addresses()
        current_artifacts["images"] = self.ec2.get_all_images()
        current_artifacts["instances"] = self.ec2.get_all_instances()
        current_artifacts["key_pairs"] = self.ec2.get_all_key_pairs()
        current_artifacts["security_groups"] = self.ec2.get_all_security_groups()
        current_artifacts["snapshots"] = self.ec2.get_all_snapshots()
        current_artifacts["volumes"] = self.ec2.get_all_volumes()
        current_artifacts["zones"] = self.ec2.get_all_zones()
        
        if verbose:
            self.debug("Current resources in the system:\n" + str(current_artifacts))
        return current_artifacts
    
    def read_config(self, filepath, username="root"):
        """ Parses the config file at filepath returns a dictionary with the config
            Config file
            ----------
            The configuration file for (2) private cloud mode has the following structure:
            
                clc.mydomain.com CENTOS 5.7 64 REPO [CC00 CLC SC00 WS]    
                nc1.mydomain.com VMWARE ESX-4.0 64 REPO [NC00]
            
            Columns
            ------ 
                IP or hostname of machine   
                Distro installed on machine - Options are RHEL, CENTOS, UBUNTU additionally VMWARE can be used for NCs 
                Distro version on machine  - RHEL (5.x, 6.x), CentOS (5.x), UBUNTU (LUCID)
                Distro base architecture  - 32 or 64
                System built from packages (REPO) or source (BZR), packages assumes path to eucalyptus is /, bzr assumes path to eucalyptus is /opt/eucalyptus
                List of components installed on this machine encapsulated in brackets []
            
            These components can be:
            
                CLC - Cloud Controller   
                WS - Walrus   
                SC00 - Storage controller for cluster 00   
                CC00 - Cluster controller for cluster 00    
                NC00 - A node controller in cluster 00   
        """
        config_hash = {}
        machines = []
        f = None
        try:
            #f = open(filepath, 'r')
            self.testconf = EuConfig(filepath, legacy_qa_config=True)
            f = self.testconf.legacybuf.splitlines()
        except IOError as (errno, strerror):
            self.debug( "ERROR: Could not find config file " + self.config_file)
            raise
            
        for line in f:
            ### LOOK for the line that is defining a machine description
            line = line.strip()
            re_machine_line = re.compile(".*\[.*]")
            if re_machine_line.match(line):
                machine_details = line.split(None, 5)
                machine_dict = {}
                machine_dict["hostname"] = machine_details[0]
                machine_dict["distro"] = machine_details[1]
                machine_dict["distro_ver"] = machine_details[2]
                machine_dict["arch"] = machine_details[3]
                machine_dict["source"] = machine_details[4]
                machine_dict["components"] = map(str.lower, machine_details[5].strip('[]').split())

                ### ADD the machine to the array of machine
                cloud_machine = Machine(   machine_dict["hostname"], 
                                        distro = machine_dict["distro"], 
                                        distro_ver = machine_dict["distro_ver"], 
                                        arch = machine_dict["arch"], 
                                        source = machine_dict["source"], 
                                        components = machine_dict["components"],
                                        connect = True,
                                        password = self.password,
                                        keypath = self.keypath,
                                        username = username
                                        )
                machines.append(cloud_machine)
                
            ### LOOK for network mode in config file if not found then set it unknown
            for param in ["network", "managed_ips", "subnet_ip"]:
                try:
                    if re.search("^" + param + ".*$", line, re.IGNORECASE):
                        config_hash[param] = " ".join(line.split()[1:])
                except:
                    self.debug("Could not find " + param + " type setting to None")
                    config_hash[param] = None
        #f.close()   
        config_hash["machines"] = machines 
        return config_hash


    def update_property_manager(self,machine=None):
        machine = machine or self.clc
        if not machine:
            self._property_manager = None
            return
        self._property_manager = Euproperty_Manager(self, machine=machine, debugmethod=self.debug)

    def swap_clc(self):
        all_clcs = self.get_component_machines("clc")
        if self.clc is all_clcs[0]:
            self.debug("Swapping CLC from " + all_clcs[0].hostname + " to " + all_clcs[1].hostname)
            self.clc = all_clcs[1]
            
        elif self.clc is all_clcs[1]:
            self.debug("Swapping CLC from " + all_clcs[1].hostname + " to " + all_clcs[0].hostname)
            self.clc = all_clcs[0]

    def swap_walrus(self):
        all_walruses = self.get_component_machines("ws")
        if self.object_storage is all_walruses[0]:
            self.debug("Swapping Walrus from " + all_walruses[0].hostname + " to " + all_walruses[1].hostname)
            self.object_storage = all_walruses[1]
        elif self.object_storage is all_walruses[1]:
            self.debug("Swapping Walrus from " + all_walruses[1].hostname + " to " + all_walruses[0].hostname)
            self.object_storage = all_walruses[0]
            
    def get_network_mode(self):
        return self.config['network']
            
    def get_component_ip(self, component):
        """ Parse the machine list and a bm_machine object for a machine that matches the component passed in"""
        #loop through machines looking for this component type
        component.lower()
        machines_with_role = [machine.hostname for machine in self.config['machines'] if component in machine.components]
        if len(machines_with_role) == 0:
            raise Exception("Could not find component "  + component + " in list of machines")
        else:
            return machines_with_role[0]
    
    def get_machine_by_ip(self, hostname):
        machines = [machine for machine in self.config['machines'] if re.search(hostname, machine.hostname)]
        
        if machines is None or len(machines) == 0:
            self.fail("Could not find machine at "  + hostname + " in list of machines")
            return None
        else:
            return machines[0]

    def get_component_machines(self, component = None):
        #loop through machines looking for this component type
        """ Parse the machine list and a list of bm_machine objects that match the component passed in"""
        if component is None:
            return self.config['machines']
        else:
            component.lower()
            machines_with_role = [machine for machine in self.config['machines'] if re.search(component, " ".join(machine.components))]
            if len(machines_with_role) == 0:
                raise IndexError("Could not find component "  + component + " in list of machines")
            else:
                return machines_with_role

    def swap_component_hostname(self, hostname):
        if hostname != None:
            if len(hostname) < 5:
                component_hostname = self.get_component_ip(hostname)
                hostname = component_hostname
        return hostname
       
    def get_credentials(self, account="eucalyptus", user="admin"):
        """Login to the CLC and download credentials programatically for the user and account passed in
           Defaults to admin@eucalyptus 
        """
        self.debug("Starting the process of getting credentials")
        
        ### GET the CLCs from the config file
        clcs = self.get_component_machines("clc")
        if len(clcs) < 1:
            raise Exception("Could not find a CLC in the config file when trying to get credentials")
        
        admin_cred_dir = "eucarc-" + clcs[0].hostname + "-" + account + "-" + user 
        cred_file_name = "creds.zip"
        full_cred_path = admin_cred_dir + "/" + cred_file_name
        
        ### IF I dont already have credentials, download and sync them
        if self.credpath is None:
            ### SETUP directory remotely
            self.setup_remote_creds_dir(admin_cred_dir)
            
            ### Create credential from Active CLC
            self.create_credentials(admin_cred_dir, account, user)
        
            ### SETUP directory locally
            self.setup_local_creds_dir(admin_cred_dir)
          
            ### DOWNLOAD creds from clc
            self.download_creds_from_clc(admin_cred_dir)

            ### SET CREDPATH ONCE WE HAVE DOWNLOADED IT LOCALLY
            self.credpath = admin_cred_dir
            ### IF there are 2 clcs make sure to sync credentials across them
        ### sync the credentials  to all CLCs
        for clc in clcs:
            self.send_creds_to_machine(admin_cred_dir, clc)

        return admin_cred_dir
   
    def create_credentials(self, admin_cred_dir, account, user):
       
        cred_dir =  admin_cred_dir + "/creds.zip"
        self.sys('rm -f '+cred_dir)
        cmd_download_creds = self.eucapath + "/usr/sbin/euca_conf --get-credentials " + admin_cred_dir + "/creds.zip " + "--cred-user "+ user +" --cred-account " + account 
       
        if self.clc.found( cmd_download_creds, "The MySQL server is not responding"):
            raise IOError("Error downloading credentials, looks like CLC was not running")
        if self.clc.found( "unzip -o " + admin_cred_dir + "/creds.zip " + "-d " + admin_cred_dir, "cannot find zipfile directory"):
            raise IOError("Empty ZIP file returned by CLC")
       
        
    
    def download_creds_from_clc(self, admin_cred_dir):
        self.debug("Downloading credentials from " + self.clc.hostname + ", path:" + admin_cred_dir + "/creds.zip")
        self.sftp.get(admin_cred_dir + "/creds.zip" , admin_cred_dir + "/creds.zip")
        self.local("unzip -o " + admin_cred_dir + "/creds.zip -d " + admin_cred_dir )
    
    def send_creds_to_machine(self, admin_cred_dir, machine):
        self.debug("Sending credentials to " + machine.hostname)
        try:
            machine.sftp.listdir(admin_cred_dir + "/creds.zip")
            self.debug("Machine " + machine.hostname + " already has credentials in place")
        except IOError, e:
            machine.sys("mkdir " + admin_cred_dir)
            machine.sftp.put( admin_cred_dir + "/creds.zip" , admin_cred_dir + "/creds.zip")
            machine.sys("unzip -o " + admin_cred_dir + "/creds.zip -d " + admin_cred_dir )
            # machine.sys("sed -i 's/" + self.get_ec2_ip() + "/" + machine.hostname  +"/g' " + admin_cred_dir + "/eucarc")
            
        
    def setup_local_creds_dir(self, admin_cred_dir):
        if not os.path.exists(admin_cred_dir):
            os.mkdir(admin_cred_dir)
      
    def setup_remote_creds_dir(self, admin_cred_dir):
        self.sys("mkdir " + admin_cred_dir)
    
    def sys(self, cmd, verbose=True, listformat=True, timeout=120, code=None):
        """ By default will run a command on the CLC machine, the connection used can be changed by passing a different hostname into the constructor
            For example:
            instance = Eutester( hostname=instance.ip_address, keypath="my_key.pem")
            instance.sys("mount") # check mount points on instance and return the output as a list
        """
        return self.clc.sys(cmd, verbose=verbose,  listformat=listformat, timeout=timeout, code=code)
    
    @classmethod
    def get_traceback(cls):
        '''
        Returns a string buffer with traceback, to be used for debug/info purposes. 
        '''
        try:
            out = StringIO.StringIO()
            traceback.print_exception(*sys.exc_info(),file=out)
            out.seek(0)
            buf = out.read()
        except Exception, e:
                buf = "Could not get traceback"+str(e)
        return str(buf) 
    
