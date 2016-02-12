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
import os
import sys
import StringIO
from eutester.euservice import EuserviceManager
from boto.ec2.instance import Reservation, Instance
from boto.exception import EC2ResponseError
from eutester.euconfig import EuConfig
from eutester.euproperties import Euproperty_Manager
from eutester.machine import Machine
from eutester.euvolume import EuVolume
from eutester import eulogger
from eutester.sshconnection import CommandExitCodeException
import re
import os
from socket import error as socketerror

class Eucaops(EC2ops,S3ops,IAMops,STSops,CWops, ASops, ELBops, CFNops):
    
    def __init__(self, config_file=None, password=None, keypath=None, credpath=None,
                 aws_access_key_id=None, aws_secret_access_key = None,  account="eucalyptus",
                 user="admin", username=None, APIVersion='2013-10-15',
                 ec2_ip=None, ec2_path=None, iam_ip=None, iam_path=None, s3_ip=None, s3_path=None,
                 as_ip=None, as_path=None, elb_ip=None, elb_path=None, cw_ip=None, cw_path=None,
                 cfn_ip=None, cfn_path=None, sts_ip=None, sts_path=None, force_cert_create=False,
                 port=8773, download_creds=True, boto_debug=0, debug_method=None, region=None,
                 ssh_proxy=None):
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
        self.info = self.logger.log.info
        self.username = username
        self.account_id = None
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.force_cert_create = force_cert_create
        self._property_manager = None
        self.cred_zipfile = None
        self.ssh_proxy = None #SshConnection obj to be used as a default ssh proxy

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
            self.sftp = self.clc.ssh.open_sftp()
            downloaded_creds = False
            if self.download_creds:
                if self.credpath is None:
                    ### TRY TO GET CREDS ON FIRST CLC if it fails try on second listed clc,
                    ### if that fails we've hit a terminal condition
                    try:
                        self.debug("Attempting to get credentials and setup sftp")
                        self.sftp = self.clc.ssh.open_sftp()
                        self.credpath = self.get_credentials(account,user)
                        self.debug("Successfully downloaded and synced credentials")
                    except Exception, e:
                        tb = self.get_traceback()
                        self.debug("Caught an exception when getting credentials "
                                   "from first CLC: " + str(e))
                        ### If i only have one clc this is a critical failure,
                        ### else try on the other clc
                        if len(clc_array) < 2:
                            raise Exception(str(tb) + "\nCould not get credentials from first CLC "
                                                      "and no other to try")
                        self.swap_clc()
                        self.sftp = self.clc.ssh.open_sftp()
                        self.get_credentials(account, user)
                        downloaded_creds = True
                        
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

                self.setup_ec2_connection(endpoint=ec2_ip, path=ec2_path, port=port,
                                          is_secure=False, region=region,
                                          aws_access_key_id=aws_access_key_id,
                                          aws_secret_access_key=aws_secret_access_key,
                                          APIVersion=APIVersion,
                                          boto_debug=boto_debug)
                self.setup_ec2_resource_trackers()

                if self.credpath and not iam_ip:
                    iam_ip = self.get_iam_ip()
                if self.credpath and not iam_path:
                    iam_path = self.get_iam_path()
                self.setup_iam_connection(endpoint=iam_ip,
                                          path=iam_path,
                                          port=port, is_secure=False,
                                          aws_access_key_id=aws_access_key_id,
                                          aws_secret_access_key=aws_secret_access_key,
                                          boto_debug=boto_debug)

                if self.credpath and not sts_ip:
                    sts_ip = self.get_sts_ip()
                if self.credpath and not sts_path:
                    sts_path = self.get_sts_path()
                self.setup_sts_connection(endpoint=sts_ip, path=sts_path, port=port,
                                          is_secure=False, region=region,
                                          aws_access_key_id=aws_access_key_id,
                                          aws_secret_access_key=aws_secret_access_key,
                                          boto_debug=boto_debug)

                if self.credpath and not cw_ip:
                    cw_ip = self.get_cw_ip()
                if self.credpath and not cw_path:
                    cw_path = self.get_cw_path()
                self.setup_cw_connection(endpoint=cw_ip, path=cw_path, port=port,
                                         is_secure=False, region=region,
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
                                         boto_debug=boto_debug)

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
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
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
                                         aws_secret_access_key=aws_secret_access_key,
                                         boto_debug=boto_debug)
            except Exception, e:
                self.debug("Unable to create AS connection because of: " + str(e) )

            try:
                if self.credpath and not elb_ip:
                    elb_ip = self.get_elb_ip()
                if self.credpath and not elb_path:
                    elb_path = self.get_elb_path()
                self.setup_elb_connection(endpoint=elb_ip, path=elb_path, port=port,
                                          is_secure=False, region=region,
                                          aws_access_key_id=aws_access_key_id,
                                          aws_secret_access_key=aws_secret_access_key,
                                          boto_debug=boto_debug)
            except Exception, e:
                self.debug("Unable to create ELB connection because of: " + str(e) )
            try:
                if self.credpath and not cfn_ip:
                    cfn_ip = self.get_cfn_ip()
                if self.credpath and not cfn_path:
                    cfn_path = self.get_cfn_path()
                self.setup_cfn_connection(endpoint=cfn_ip, path=self.get_cfn_path(), port=port,
                                          is_secure=False, region=region,
                                          aws_access_key_id=aws_access_key_id,
                                          aws_secret_access_key=aws_secret_access_key,
                                          boto_debug=boto_debug)
            except Exception, e:
                self.debug("Unable to create CloudFormation connection because of: " + str(e) )

            if self.clc and not (self.ec2_cert and
                                     self.is_ec2_cert_active(certbody=self.ec2_cert)):
                self.logger.log.critical(self.markup('CERTS ARE NOT ACTIVE, '
                                                     'TRYING TO UPDATE NOW...', 1))
                try:
                    self.get_active_cert_for_creds()
                except ValueError, VE:
                    self.critical('Could not get active cert for creds. Err:\n{0}'.format(VE))
                self.get_credentials(force=True)
                if not self.ec2_cert or not self.is_ec2_cert_active():
                    self.logger.log.critical(self.markup('CERTS ARE NOT ACTIVE, COULD NOT UPDATE',
                                                         91))
                else:
                    self.debug(self.markup('UPDATED TEST ENV WITH ACTIVE CERTIFICATE AND '
                                           'PRIVATE KEY',92))

    def critical(self, text):
        return self.logger.log.critical(self.markup(text, 91))

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

    def _update_euzone_list(self):
        zones = self.ec2.get_all_zones()
        verbose_zones = self.ec2.get_all_zones("verbose")




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
        self.debug("Finding available VMs: Partition=" + zone +" Type= " + type + " Number=" +
                   str(int(type_state[0])) )
        return int(type_state[0])

    def modify_property(self, property, value):
        """
        Modify a eucalyptus property through the command line euca-modify-property tool
        property        Property to modify
        value           Value to set it too
        """
        if self.credpath == None or self.eucapath == None or property == None or value == None:
            fail_buf = "Cannot set property: " + (property if property is not None else "unknown")
            fail_buf += "Cannot set property value due to insufficient arguments"
            fail_buf += ("credpath: " + ("None" if self.credpath is None else self.credpath))
            fail_buf += ("eucapath: " + ("None" if self.eucapath is None else self.eucapath))
            fail_buf += ("property: " + ("None" if property is None else property))
            fail_buf += ("value: " + ("None" if value is None else value))
            raise ValueError(fail_buf)
        
        command = ". {0}/eucarc &>/dev/null && " \
                  "{1}/usr/sbin/euca-modify-property -p {2}={3}"\
            .format(self.credpath or '.', self.eucapath, property, value)

        if self.clc.found(command, property):
            self.debug("Properly modified property " + property)
        else:
            raise Exception("Setting property " + property + " failed")

    def cleanup_artifacts(self,instances=True, snapshots=True, volumes=True,
                          load_balancers=True, ip_addresses=True,
                          auto_scaling_groups=True, launch_configurations=True,
                          keypairs=True, images=True):
        """
        Description: Attempts to remove artifacts created during and through this
        eutester's lifespan.
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
            remove_list = []
            instances = []
            # To speed up termination, send terminate to all instances
            # before sending them to the monitor methods
            for res in self.test_resources["reservations"]:
                try:
                    if isinstance(res, Instance):
                        res.terminate()
                    if isinstance(res, Reservation):
                        for ins in res.instances:
                            ins.terminate()
                except:
                    traceback.print_exc()
                    self.debug('ignoring error in instance cleanup '
                               'during termination')
            # Now monitor to terminated state...
            for res in self.test_resources["reservations"]:
                try:
                    self.terminate_instances(res)
                    remove_list.append(res)
                except Exception, e:
                    tb = self.get_traceback()
                    failcount +=1
                    failmsg += str(tb) + "\nError#:"+ str(failcount)+ ":" + str(e)+"\n"
            for res in remove_list:
                self.test_resources["reservations"].remove(res)
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
                        if images:
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
                    failmsg += str(tb) + "\nUnable to delete item: " + str(item) + "\n" + \
                               str(e)+"\n"
        if failmsg:
            failmsg += "\nFound " + str(failcount) + " number of errors while cleaning up. " \
                                                     "See above"
            raise Exception(failmsg)

    def cleanup_load_balancers(self, lbs=None):
        """
        :param lbs: optional list of load balancers, otherwise it will attempt to delete
                    from test_resources[]
        """
        if lbs:
            self.delete_load_balancers(lbs)
        else:
            try:
                self.delete_load_balancers(self.test_resources['load_balancers'])
            except KeyError:
                self.debug("No loadbalancers to delete")

    def cleanup_autoscaling_groups(self, asg_list=None):
        """
        This will attempt to delete auto scaling groups listed in test_resources['auto-scaling-groups']
        """
        ### clear all ASGs
        if asg_list:
            self.delete_autoscaling_groups(asg_list)
        else:
            try:
                self.delete_autoscaling_groups(self.test_resources['auto-scaling-groups'])
            except KeyError:
                self.debug("Auto scaling group list is empty")

    def cleanup_launch_configs(self, lc_list=None):
        """
        This will attempt to delete launch configs listed in test_resources['launch-configurations']
        """
        if lc_list:
            self.delete_launch_configs(lc_list)
        else:
            try:
                self.delete_launch_configs(self.test_resources['launch-configurations'])
            except KeyError:
                self.debug("Launch configuration list is empty")

    def cleanup_addresses(self, ips=None):
        """
        :param ips: optional list of ip addresses, else will attempt to delete from
                    test_resources[]

        """
        addresses = ips or self.test_resources['addresses']
        if not addresses:
            return

        self.debug('Attempting to release to the cloud the following IP addresses:')

        while addresses:
            self.release_address(addresses.pop())

    def cleanup_test_snapshots(self,snaps=None, clean_images=False, add_time_per_snap=10,
                               wait_for_valid_state=120, base_timeout=180):
        """
        :param snaps: optional list of snapshots, else will attempt to delete from test_resources[]
        :param clean_images: Boolean, if set will attempt to delete registered images referencing
                             the snapshots first. Images referencing the snapshot may prevent
                             snapshot deletion to protect the image.
        :param add_time_per_snap:  int number of seconds to append to base_timeout per snapshot
        :param wait_for_valid_state: int seconds to wait for snapshot(s) to enter
                                     a 'deletable' state
        :param base_timeout: base timeout to use before giving up, and failing operation.
        """
        snaps = snaps or self.test_resources['snapshots']
        if not snaps:
            return
        self.debug('Attempting to clean the following snapshots:')
        self.show_snapshots(snaps)
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
        Definition: cleaup helper method intended to clean up volumes created within a test,
                    after the test has ran.

        :param volumes: optional list of volumes to delete from system, otherwise will use
                        test_resources['volumes']
        """
        euvolumes = []
        detaching = []
        not_exist = []
        line = '\n--------------------------------------------------------' \
               '--------------------------------------------\n'

        volumes = volumes or self.test_resources['volumes']
        if not volumes:
            self.debug('clean_up_test_volumes, no volumes passed to delete')
            return
        self.debug('clean_up_test_volumes starting\nVolumes to be deleted:' +
                   ",".join(str(x) for x in volumes))

        for vol in volumes:
            try:
                vol = self.get_volume(volume_id=vol.id)
            except:
                tb = self.get_traceback()
                self.debug("\n" + line + " Ignoring caught Exception:\n" + str(tb) + "\n" +
                           str(vol.id) + ', Could not retrieve volume, may no longer exist?' +
                           line)
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
            self.show_volumes(euvolumes)
        except: pass
        self.debug('Clean_up_volumes: Detaching any attached volumes to be deleted...')
        for vol in euvolumes:
            try:
                vol.update()
                if vol.status == 'in-use':
                    if vol.attach_data and (vol.attach_data.status != 'detaching' or
                                                    vol.attach_data.status != 'detached'):
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
        #If the volume was found to not exist on the system, remove it from further monitoring...
        for vol in not_exist:
            if vol in detaching:
                detaching.remove(vol)
            if vol in euvolumes:
                euvolumes.remove(vol)
        self.test_resources['volumes'] = euvolumes
        timeout = min_timeout + (len(volumes) * timeout_per_vol)
        #If detaching wait for detaching to transition to detached...
        if detaching:
            self.monitor_euvolumes_to_status(detaching, status='available', attached_status=None,
                                             timeout=timeout)
        self.debug('clean_up_volumes: Deleteing volumes now...')
        self.show_volumes(euvolumes)
        if euvolumes:
            self.delete_volumes(euvolumes, timeout=timeout)


    def get_current_resources(self,verbose=False):
        '''
        Return a dictionary with all known resources the system has. Optional pass the verbose=True
        flag to print this info to the logs.
        Included resources are: addresses, images, instances, key_pairs, security_groups,
                                snapshots, volumes, zones
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
                Distro installed on machine - Options are RHEL, CENTOS, UBUNTU additionally
                                              VMWARE can be used for NCs
                Distro version on machine  - RHEL (5.x, 6.x), CentOS (5.x), UBUNTU (LUCID)
                Distro base architecture  - 32 or 64
                System built from packages (REPO) or source (BZR), packages assumes path to
                eucalyptus is /, bzr assumes path to eucalyptus is /opt/eucalyptus
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
        machine_dicts = []
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
                new_machine_dict = {}
                new_machine_dict["hostname"] = machine_details[0]
                new_machine_dict["distro"] = machine_details[1]
                new_machine_dict["distro_ver"] = machine_details[2]
                new_machine_dict["arch"] = machine_details[3]
                new_machine_dict["source"] = machine_details[4]
                new_machine_dict["components"] = map(str.lower, machine_details[5].strip('[]').split())
                machine_dicts.append(new_machine_dict)

        def create_cloud_machine(machine_dict, ssh_proxy=None):
            ### ADD the machine to the array of machine
            try:
                proxy_host = None
                proxy_username = None
                proxy_password = None
                proxy_keypath = None
                self.test_port_status(machine_dict["hostname"], 22, tcp=True)
            except socketerror, se:
                self.debug(self.markup('Could not connect to:"{0}", err:"{1}"'
                           .format(machine_dict["hostname"], se), [1,31]))
                if ssh_proxy:
                    self.debug('Attempting ssh proxy connection now...\n'
                               'Using proxy host:"{0}"'.format(ssh_proxy.hostname))
                    proxy_host = ssh_proxy.hostname
                    proxy_username = ssh_proxy.username
                    proxy_password = ssh_proxy.password
                    proxy_keypath = ssh_proxy.keypath
                else:
                    self.critical('SSH port test to host:"{0}" failed and no proxy defined '
                              'for use'.format(machine_dict["hostname"]))

            cloud_machine = Machine(machine_dict["hostname"],
                                    distro = machine_dict["distro"],
                                    distro_ver = machine_dict["distro_ver"],
                                    arch = machine_dict["arch"],
                                    source = machine_dict["source"],
                                    components = machine_dict["components"],
                                    connect = True,
                                    password = self.password,
                                    keypath = self.keypath,
                                    username = username,
                                    ssh_proxy_host=proxy_host,
                                    ssh_proxy_keypath=proxy_keypath,
                                    ssh_proxy_username=proxy_username,
                                    ssh_proxy_password=proxy_password
                                    )
            if proxy_host:
                self.debug(self.markup('Machine at:"{0}" successfully create using ssh proxy'
                           .format(machine_dict["hostname"]),[1,32]))
            return cloud_machine

        # Create the CLC first in order to use it as an ssh proxy if one was not provided..
        for machine_dict in machine_dicts:
            if 'clc' in machine_dict['components']:
                clc = create_cloud_machine(machine_dict, self.ssh_proxy)
                machine_dicts.remove(machine_dict)
                machines.append(clc)
        # Now create the other machine objects...
        for machine_dict in machine_dicts:
            cloud_machine = create_cloud_machine(machine_dict, self.ssh_proxy or clc)
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
            self.debug("Swapping Walrus from " + all_walruses[0].hostname + " to " +
                       all_walruses[1].hostname)
            self.object_storage = all_walruses[1]
        elif self.object_storage is all_walruses[1]:
            self.debug("Swapping Walrus from " + all_walruses[1].hostname + " to " +
                       all_walruses[0].hostname)
            self.object_storage = all_walruses[0]
            
    def get_network_mode(self):
        return self.config['network']
            
    def get_component_ip(self, component):
        """ Parse the machine list and a bm_machine object for a machine that matches the
         component passed in"""
        #loop through machines looking for this component type
        component.lower()
        machines_with_role = [machine.hostname for machine in self.config['machines']
                              if component in machine.components]
        if len(machines_with_role) == 0:
            raise Exception("Could not find component "  + component + " in list of machines")
        else:
            return machines_with_role[0]
    
    def get_machine_by_ip(self, hostname):
        machines = [machine for machine in self.config['machines'] if re.search(hostname,
                                                                                machine.hostname)]
        
        if machines is None or len(machines) == 0:
            self.fail("Could not find machine at "  + hostname + " in list of machines")
            return None
        else:
            return machines[0]

    def get_component_machines(self, component = None):
        """
        loop through machines looking for this component type
        Parse the machine list and a list of bm_machine objects that match the component passed in
        """
        if component is None:
            return self.config['machines']
        else:
            component.lower()
            machines_with_role = [machine for machine in self.config['machines']
                                  if re.search(component, " ".join(machine.components))]
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
       
    def get_credentials(self, account="eucalyptus", user="admin", force=False):
        """
        Login to the CLC and download credentials programatically for the user and account
        passed in. Defaults to admin@eucalyptus
        """
        self.debug("Starting the process of getting credentials")
        
        ### GET the CLCs from the config file
        clcs = self.get_component_machines("clc")
        if len(clcs) < 1:
            raise Exception("Could not find a CLC in the config file when trying to"
                            " get credentials")
        admin_cred_dir = "eucarc-" + clcs[0].hostname + "-" + account + "-" + user 
        cred_file_name = "creds.zip"
        full_cred_path = admin_cred_dir + "/" + cred_file_name
        
        ### IF I dont already have credentials, download and sync them
        if force or self.credpath is None or not self.is_ec2_cert_active():
            ### SETUP directory remotely
            self.setup_remote_creds_dir(admin_cred_dir)
            
            ### Create credential from Active CLC
            # Store the zipfile info to check for active certs when iam/euare connection is
            # established later...
            self.cred_zipfile = self.create_credentials(admin_cred_dir, account, user,
                                                        zipfile=cred_file_name)
            if hasattr(self, 'euare') and self.euare:
                self.get_active_cert_for_creds(credzippath=self.cred_zipfile, account=account,
                                               user=user)
            self.debug('self.cred_zipfile: ' + str(self.cred_zipfile))
            ### SETUP directory locally
            self.setup_local_creds_dir(admin_cred_dir)
          
            ### DOWNLOAD creds from clc
            self.download_creds_from_clc(admin_cred_dir=os.path.dirname((self.cred_zipfile)),
                                         zipfile=os.path.basename(self.cred_zipfile))

            ### SET CREDPATH ONCE WE HAVE DOWNLOADED IT LOCALLY
            self.credpath = admin_cred_dir
            ### IF there are 2 clcs make sure to sync credentials across them
        ### sync the credentials  to all CLCs
        for clc in clcs:
            self.send_creds_to_machine(admin_cred_dir, clc)

        return admin_cred_dir

    def create_legacy_clc_creds_using_nephoria(self, cred_dir, zipfile='creds.zip',
                                               account='eucalyptus', user='admin'):
        zipfilepath = os.path.join(cred_dir, zipfile)
        output = self.credential_exist_on_remote_machine(os.path.join(zipfilepath))
        if output['status'] == 0:
            self.debug("Found creds file, skipping euca_conf --get-credentials.")
        else:
            from nephoria.testcontroller import TestController
            self.debug(self.markup('Using temporary Nephoria method to create legacy creds',
                                   markups=[35]))
            tc = TestController(self.clc.ssh.host, password=self.clc.ssh.password,
                                log_level=self.logger.logger_level)
            user = tc.get_user_by_name(aws_account_name=account, aws_user_name=user)
            if not getattr(user, 'eucalyptus_cert', None):
                setattr(user, 'eucalyptus_cert', '${EUCA_KEY_DIR}/cloud-cert.pem')
            user.create_local_creds(local_destdir=cred_dir)
            cloud_cert_path = os.path.join(cred_dir, 'cloud-cert.pem')
            if not os.path.exists(cloud_cert_path):
                tc.sysadmin.write_service_cert_to_file(cloud_cert_path)
            self.setup_remote_creds_dir(cred_dir)
            for file in os.listdir(cred_dir):
                fpath = os.path.join(cred_dir, file)
                self.clc.ssh.sftp_put(fpath, fpath)
            self.clc.sys('zip {0} {1}/*'.format(zipfilepath, os.path.normpath(cred_dir)))
        return zipfilepath

    def create_credentials(self, admin_cred_dir, account, user, zipfile='creds.zip',
                           try_alt=False):
        """

        :param admin_cred_dir: The Directory on both the CLC and local machine create the
                                credential artifacts in
        :param account: cloud account to create creds for
        :param user: cloud user to create creds for
        :param zipfile: the name of the zip archive file to create within 'admin_cred_dir'
        :param try_alt: Boolean, to try alternative methods to euca_conf soon to be deprecated
        :return: path to zip archive file
        """
        if try_alt:
            try:
                from nephoria.testcontroller import TestController
                return self.create_legacy_clc_creds_using_nephoria(cred_dir=admin_cred_dir,
                                                                   zipfile=zipfile,
                                                                   account=account,
                                                                   user=user)
            except ImportError as IE:
                self.logger.log.info('Could not import nephoria, using legacy euca_conf to fetch'
                                     'credentials: "{0}"'.format(IE))
        zipfilepath = os.path.join(admin_cred_dir, zipfile)

        output = self.credential_exist_on_remote_machine(zipfilepath)
        if output['status'] == 0:
            self.debug("Found creds file, skipping euca_conf --get-credentials.")
        else:
            cmd_download_creds = str("{0}/usr/sbin/euca_conf --get-credentials {1}/creds.zip "
                                     "--cred-user {2} --cred-account {3}"
                                     .format(self.eucapath, admin_cred_dir, user, account))
            if self.clc.found(cmd_download_creds, "The MySQL server is not responding"):
                raise IOError("Error downloading credentials, looks like CLC was not running")
            if self.clc.found("unzip -o {0}/creds.zip -d {1}"
                                      .format(admin_cred_dir, admin_cred_dir),
                              "cannot find zipfile directory"):
                raise IOError("Empty ZIP file returned by CLC")
        return zipfilepath

    def get_active_cert_for_creds(self, credzippath=None, account=None, user=None, update=True):
            if credzippath is None:
                if hasattr(self, 'cred_zipfile') and self.cred_zipfile:
                    credzippath = self.cred_zipfile
                elif self.credpath:
                    credzippath = self.credpath
                else:
                    raise ValueError('cred zip file not provided or set for eutester object')
            account = account or self.account_name
            user = user or self.aws_username
            admin_cred_dir = os.path.dirname(credzippath)
            clc_eucarc = os.path.join(admin_cred_dir, 'eucarc')
            # backward compatibility
            certpath_in_eucarc = self.clc.sys(". {0} &>/dev/null && "
                                              "echo $EC2_CERT".format(clc_eucarc))
            if certpath_in_eucarc:
                certpath_in_eucarc = certpath_in_eucarc[0]
            self.debug('Current EC2_CERT path for {0}: {1}'.format(clc_eucarc, certpath_in_eucarc))
            if certpath_in_eucarc and self.get_active_id_for_cert(certpath_in_eucarc):
                self.debug("Cert/pk already exist and is active in '" +
                           admin_cred_dir + "/eucarc' file.")
            else:
                # Try to find existing active cert/key on clc first. Check admin_cred_dir then
                # do a recursive search from ssh user's home dir (likely root/)
                self.debug('Attempting to find an active cert for this account on the CLC...')
                certpaths = self.find_active_cert_and_key_in_dir(dir=admin_cred_dir) or \
                            self.find_active_cert_and_key_in_dir()
                self.debug('Found Active cert and key paths')
                if not certpaths:
                    # No existing and active certs found, create new ones...
                    self.debug('Could not find any existing active certs on clc, '
                               'trying to create new ones...')
                    certpaths = self.create_new_user_certs(admin_cred_dir, account, user)
                # Copy cert and key into admin_cred_dir
                certpath = certpaths.get('certpath')
                keypath = certpaths.get('keypath')
                newcertpath = os.path.join(admin_cred_dir, os.path.basename(certpath))
                newkeypath = os.path.join(admin_cred_dir, os.path.basename(keypath))
                self.debug('Using certpath:{0} and keypath:{1} on clc'
                           .format(newcertpath, newkeypath))
                self.clc.sys('cp {0} {1}'.format(certpath, newcertpath))
                self.clc.sys('cp {0} {1}'.format(keypath, newkeypath))
                # Update the existing eucarc with new cert and key path info...
                self.debug("Setting cert/pk in '" + admin_cred_dir + "/eucarc'")
                self.sys("echo 'export EC2_CERT=${EUCA_KEY_DIR}/" + "{0}' >> {1}"
                         .format(os.path.basename(newcertpath), clc_eucarc), code=0)
                self.sys("echo 'export EC2_PRIVATE_KEY=${EUCA_KEY_DIR}/" + "{0}' >> {1}"
                         .format(os.path.basename(newkeypath), clc_eucarc), code=0)
                self.debug('updating zip file with new cert, key and eucarc: {0}'
                           .format(credzippath))
                for updatefile in [os.path.basename(newcertpath), os.path.basename(newkeypath),
                             os.path.basename(clc_eucarc)]:
                    self.clc.sys('cd {0} && zip -g {1} {2}'
                                 .format(os.path.dirname(credzippath),
                                         os.path.basename(credzippath),
                                         updatefile), code=0)
                return credzippath

    def create_new_user_certs(self, admin_cred_dir, account, user,
                              newcertpath=None, newkeypath=None):
        eucarcpath = os.path.join(admin_cred_dir, 'eucarc')
        newcertpath = newcertpath or os.path.join(admin_cred_dir, "euca2-cert.pem")
        newkeypath = newkeypath or os.path.join(admin_cred_dir, "/euca2-pk.pem")
        #admin_certs = self.clc.sys("source {0} && /usr/bin/euare-userlistcerts | grep -v Active"
        #                           .format(eucarcpath))
        admin_certs = []
        for cert in self.get_active_certs():
            admin_certs.append(cert.get('certificate_id'))
        if len(admin_certs) > 1:
            if self.force_cert_create:
                self.debug("Found more than one certs, deleting last cert")
                self.clc.sys(". {0} &>/dev/null && "
                             "/usr/bin/euare-userdelcert -c {1} --user-name {2}"
                             .format(eucarcpath,
                                     admin_certs[admin_certs.pop()],
                                     user),
                             code=0)
            else:
                raise RuntimeWarning('No active certs were found on the clc, and there are 2'
                                     'certs outstanding. Either delete an existing '
                                     'cert or move and active cert into clc root dir.'
                                     'The option "force_cert_create" will "delete" an existing'
                                     'cert automatically and replace it.'
                                     'Warning: deleting existing certs may leave signed'
                                     'objects in cloud unrecoverable.')
        self.debug("Creating a new signing certificate for user '{0}' in account '{1}'."
                   .format(user, account))
        self.debug('New cert name:{0}, keyname:{1}'.format(os.path.basename(newcertpath),
                                                           os.path.basename(newkeypath)))

        self.clc.sys(". {0} &>/dev/null && "
                     "/usr/bin/euare-usercreatecert --user-name {1} --out {2} --keyout {3}"
                     .format(eucarcpath,
                             user,
                             newcertpath,
                             newkeypath),
                    code=0)
        return {"certpath":newcertpath, "keypath":newkeypath}

    def get_active_certs(self):
        '''
        Query system for active certs list
        :returns :list of active cert dicts
        '''
        if not hasattr(self, 'euare') or not self.euare:
            self.critical(self.markup('Cant update certs until euare interface '
                                      'is initialized', 91))
            return []
        certs = []
        resp = self.euare.get_all_signing_certs()
        if resp:
            cresp= resp.get('list_signing_certificates_response')
            if cresp:
                lscr = cresp.get('list_signing_certificates_result')
                if lscr:
                    certs = lscr.get('certificates', [])
        return certs

    def get_active_id_for_cert(self, certpath, machine=None):
        '''
        Attempt to get the cloud's active id for a certificate at 'certpath' on
        the 'machine' filesystem. Also see is_ec2_cert_active() for validating the current
        cert in use or the body (string buffer) of a cert.
        :param certpath: string representing the certificate path on the machines filesystem
        :param machine: Machine obj which certpath exists on
        :returns :str() certificate id (if cert is found to be active) else None
        '''
        if not certpath:
            raise ValueError('No ec2 certpath provided or set for eutester obj')
        machine = machine or self.clc
        self.debug('Verifying cert: "{0}"...'.format(certpath))
        body = str("\n".join(machine.sys('cat {0}'.format(certpath), verbose=False)) ).strip()
        certs = []
        if body:
            certs = self.get_active_certs()
        for cert in certs:
            if str(cert.get('certificate_body')).strip() == body:
                self.debug('verified certificate with id "{0}" is still valid'
                           .format(cert.get('certificate_id')))
                return cert.get('certificate_id')
        self.debug('Cert: "{0}" is NOT active'.format(certpath or body))
        return None

    def find_active_cert_and_key_in_dir(self, dir="", machine=None, recursive=True):
        '''
        Attempts to find an "active" cert and the matching key files in the provided
        directory 'dir' on the provided 'machine' via ssh.
        If recursive is enabled, will attempt a recursive search from the provided directory.
        :param dir: the base dir to search in on the machine provided
        :param machine: a Machine() obj used for ssh search commands
        :param recursive: boolean, if set will attempt to search recursively from the dir provided
        :returns dict w/ values 'certpath' and 'keypath' or {} if not found.
        '''
        machine = machine or self.clc
        ret_dict = {}
        if dir and not dir.endswith("/"):
            dir += "/"
        if recursive:
            rec = "r"
        else:
            rec = ""
        certfiles = machine.sys('grep "{0}" -l{1} {2}*.pem'.format('^-*BEGIN CERTIFICATE', rec, dir))
        for f in certfiles:
            if self.get_active_id_for_cert(f, machine=machine):
                dir = os.path.dirname(f)
                keypath = self.get_key_for_cert(certpath=f, keydir=dir, machine=machine)
                if keypath:
                    self.debug('Found existing active cert and key on clc: {0}, {1}'
                               .format(f, keypath))
                    return {'certpath':f, 'keypath':keypath}
        return ret_dict

    def get_key_for_cert(self, certpath, keydir, machine=None, recursive=True):
        '''
        Attempts to find a matching key for cert at 'certpath' in the provided directory 'dir'
        on the provided 'machine'.
        If recursive is enabled, will attempt a recursive search from the provided directory.
        :param dir: the base dir to search in on the machine provided
        :param machine: a Machine() obj used for ssh search commands
        :param recursive: boolean, if set will attempt to search recursively from the dir provided
        :returns string representing the path to the key found or None if not found.
        '''
        machine = machine or self.clc
        self.debug('Looking for key to go with cert...')
        if keydir and not keydir.endswith("/"):
            keydir += "/"
        if recursive:
            rec = "r"
        else:
            rec = ""
        certmodmd5 = machine.sys('openssl x509 -noout -modulus -in {0}  | md5sum'
                                  .format(certpath))
        if certmodmd5:
            certmodmd5 = str(certmodmd5[0]).strip()
        else:
            return None
        keyfiles = machine.sys('grep "{0}" -lz{1} {2}*.pem'
                               .format("^\-*BEGIN RSA PRIVATE KEY.*\n.*END RSA PRIVATE KEY\-*",
                                       rec, keydir))
        for kf in keyfiles:
            keymodmd5 = machine.sys('openssl rsa -noout -modulus -in {0} | md5sum'.format(kf))
            if keymodmd5:
                keymodmd5 = str(keymodmd5[0]).strip()
            if keymodmd5 == certmodmd5:
                self.debug('Found key {0} for cert {1}'.format(kf, certpath))
                return kf
        return None

    def is_ec2_cert_active(self, certbody=None):
        '''
        Attempts to verify if the current self.ec2_cert @ self.ec2_certpath is still active.
        :param certbody
        :returns the cert id if found active, otherwise returns None
        '''
        certbody = certbody or self.ec2_cert
        if not certbody:
            raise ValueError('No ec2 cert body provided or set for eutester to check for active')
        if isinstance(certbody, dict):
            checkbody = certbody.get('certificate_body')
            if not checkbody:
                raise ValueError('Invalid certbody provided, did not have "certificate body" attr')
        for cert in self.get_active_certs():
            body = str(cert.get('certificate_body')).strip()
            if body and body == str(certbody).strip():
                return cert.get('certificate_id')
        return None

    def credential_exist_on_remote_machine(self, cred_path, machine=None):
        machine = machine or self.clc
        return machine.ssh.cmd("test -e " + cred_path)

    def download_creds_from_clc(self, admin_cred_dir, zipfile="creds.zip"):

        zipfilepath = os.path.join(admin_cred_dir, zipfile)
        self.debug("Downloading credentials from " + self.clc.hostname + ", path:" + zipfilepath +
                   " to local file: " + str(zipfile))
        self.sftp.get(zipfilepath, zipfilepath)
        unzip_cmd = "unzip -o {0} -d {1}".format(zipfilepath, admin_cred_dir)
        self.debug('Trying unzip cmd: ' + str(unzip_cmd))
        self.local(unzip_cmd)
        # backward compatibility
        cert_exists_in_eucarc = self.found("cat " + admin_cred_dir + "/eucarc", "export EC2_CERT")
        if cert_exists_in_eucarc:
            self.debug("Cert/pk already exist in '" + admin_cred_dir + "/eucarc' file.")
        else:
            self.download_certs_from_clc(admin_cred_dir=admin_cred_dir, update_eucarc=True)

    def download_certs_from_clc(self, admin_cred_dir=None, update_eucarc=True):
        admin_cred_dir = admin_cred_dir or self.credpath
        self.debug("Downloading certs from " + self.clc.hostname + ", path:" +
                   admin_cred_dir + "/")
        clc_eucarc = os.path.join(admin_cred_dir, 'eucarc')
        local_eucarc = os.path.join(admin_cred_dir,  'eucarc')
        remotecertpath = self.clc.sys(". {0} &>/dev/null && "
                                      "echo $EC2_CERT".format(clc_eucarc))
        if remotecertpath:
            remotecertpath = remotecertpath[0]
        remotekeypath = self.clc.sys(". {0} &>/dev/null && "
                                     "echo $EC2_PRIVATE_KEY".format(clc_eucarc))
        if remotekeypath:
            remotekeypath = remotekeypath[0]
        if not remotecertpath or not remotekeypath:
            self.critical('CERT and KEY paths not provided in {0}'.format(clc_eucarc))
            return {}
        localcertpath = os.path.join(admin_cred_dir, os.path.basename(remotecertpath))
        localkeypath = os.path.join(admin_cred_dir, os.path.basename(remotekeypath))
        self.sftp.get(remotecertpath,localcertpath )
        self.sftp.get(remotekeypath, localkeypath)
        if update_eucarc:
            self.debug("Setting cert/pk in '{0}".format(local_eucarc))
            self.local("echo 'EUCA_KEY_DIR=$(cd $(dirname ${BASH_SOURCE:-$0}); pwd -P)' >> " +
                       local_eucarc)
            self.local("echo 'export EC2_CERT=${EUCA_KEY_DIR}/" +
                       str(os.path.basename(localcertpath)) + "' >> " + local_eucarc)
            self.local("echo 'export EC2_PRIVATE_KEY=${EUCA_KEY_DIR}/" +
                       str(os.path.basename(localkeypath)) + "' >> " + local_eucarc)
        return {'certpath':localcertpath, 'keypath':localkeypath}

    def send_creds_to_machine(self, admin_cred_dir, machine, filename='creds.zip'):
        filepath = os.path.join(admin_cred_dir, filename)
        self.debug("Sending credentials to " + machine.hostname)
        localmd5 = None
        remotemd5 = None
        try:
            machine.sys('ls ' + filepath, code=0)
            remotemd5 = self.get_md5_for_file(filepath, machine=machine)
            localmd5 = self.get_md5_for_file(filepath)
        except CommandExitCodeException:
            pass
        if not remotemd5 or (remotemd5 != localmd5):
            machine.sys("mkdir " + admin_cred_dir)
            machine.sftp.put( admin_cred_dir + "/creds.zip" , admin_cred_dir + "/creds.zip")
            machine.sys("unzip -o " + admin_cred_dir + "/creds.zip -d " + admin_cred_dir )
            """
            # backward compatibility
            cert_exists_in_eucarc = machine.found("cat " + admin_cred_dir +
                                                  "/eucarc", "export EC2_CERT")
            if cert_exists_in_eucarc:
                self.debug("Cert/pk already exist in '" + admin_cred_dir + "/eucarc' file.")
            else:
                self.debug("Sending cert/pk to " + machine.hostname)
                machine.sftp.put(admin_cred_dir + "/euca2-cert.pem", admin_cred_dir +
                                                                     "/euca2-cert.pem")
                machine.sftp.put(admin_cred_dir + "/euca2-pk.pem", admin_cred_dir +
                                                                   "/euca2-pk.pem")
                self.debug("Setting cert/pk in '" + admin_cred_dir + "/eucarc'")
                machine.sys("echo 'export EC2_CERT=${EUCA_KEY_DIR}/euca2-cert.pem' >> " +
                            admin_cred_dir + "/eucarc")
                machine.sys("echo 'export EC2_PRIVATE_KEY=${EUCA_KEY_DIR}/euca2-pk.pem' >> " +
                            admin_cred_dir + "/eucarc")
            # machine.sys("sed -i 's/" + self.get_ec2_ip() + "/" + machine.hostname  +"/g' " +
            # admin_cred_dir + "/eucarc")
            """
        else:
            self.debug("Machine " + machine.hostname + " already has credentials in place not "
                                                       " sending")

    def setup_local_creds_dir(self, admin_cred_dir):
        if not os.path.exists(admin_cred_dir):
            os.mkdir(admin_cred_dir)
      
    def setup_remote_creds_dir(self, admin_cred_dir):
        self.sys("mkdir " + admin_cred_dir)
    
    def sys(self, cmd, verbose=True, listformat=True, timeout=120, code=None):
        """
        By default will run a command on the CLC machine, the connection used can be changed by
        passing a different hostname into the constructor
        For example:
        instance = Eutester( hostname=instance.ip_address, keypath="my_key.pem")
        instance.sys("mount") # check mount points on instance and return the output as a list
        """
        return self.clc.sys(cmd, verbose=verbose,  listformat=listformat,
                            timeout=timeout, code=code)
    
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
    
