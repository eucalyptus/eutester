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


import time
import re
import os
import copy
import socket
import types
import hmac
import json
import hashlib
import base64
import time
import types
import sys
from datetime import datetime, timedelta
from subprocess import Popen, PIPE


from boto.ec2.image import Image
from boto.ec2.instance import Reservation, Instance
from boto.ec2.keypair import KeyPair
from boto.ec2.blockdevicemapping import BlockDeviceMapping, BlockDeviceType
from boto.ec2.volume import Volume
from boto.ec2.bundleinstance import BundleInstanceTask
from boto.exception import EC2ResponseError
from boto.ec2.regioninfo import RegionInfo
from boto.resultset import ResultSet
import boto

from eutester import Eutester
import eutester
from eutester.euinstance import EuInstance
from eutester.windows_instance import WinInstance
from eutester.euvolume import EuVolume
from eutester.eusnapshot import EuSnapshot
from eutester.euzone import EuZone
from testcases.cloud_user.images.conversiontask import ConversionTask

EC2RegionData = {
    'us-east-1' : 'ec2.us-east-1.amazonaws.com',
    'us-west-1' : 'ec2.us-west-1.amazonaws.com',
    'eu-west-1' : 'ec2.eu-west-1.amazonaws.com',
    'ap-northeast-1' : 'ec2.ap-northeast-1.amazonaws.com',
    'ap-southeast-1' : 'ec2.ap-southeast-1.amazonaws.com'}

class EC2ops(Eutester):

    enable_root_user_data = """#cloud-config
disable_root: false"""

    @Eutester.printinfo
    def __init__(self,
                 host=None,
                 credpath=None,
                 endpoint=None,
                 aws_access_key_id=None,
                 aws_secret_access_key = None,
                 username="root",
                 region=None,
                 is_secure=False,
                 path='/',
                 port=80,
                 boto_debug=0,
                 APIVersion = '2012-07-20'):

        """

        :param host:
        :param credpath:
        :param endpoint:
        :param aws_access_key_id:
        :param aws_secret_access_key:
        :param username:
        :param region:
        :param is_secure:
        :param path:
        :param port:
        :param boto_debug:
        :param APIVersion:
        """
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.user_id = None
        self.account_id = None
        self.poll_count = 48
        self.username = username
        self.test_resources = {}
        self.setup_ec2_resource_trackers()
        self.key_dir = "./"
        self.ec2_source_ip = None  #Source ip on local test machine used to reach instances
        super(EC2ops, self).__init__(credpath=credpath)
        self.setup_ec2_connection(host= host,
                                  region=region,
                                  endpoint=endpoint,
                                  aws_access_key_id=self.aws_access_key_id ,
                                  aws_secret_access_key=self.aws_secret_access_key,
                                  is_secure=is_secure,
                                  path=path,
                                  port=port,
                                  boto_debug=boto_debug,
                                  APIVersion=APIVersion)

    @Eutester.printinfo
    def setup_ec2_connection(self, endpoint=None, aws_access_key_id=None, aws_secret_access_key=None, is_secure=True,host=None ,
                             region=None, path = "/", port = 443,  APIVersion ='2012-07-20', boto_debug=0):
        ec2_region = RegionInfo()
        if region:
            self.debug("Check region: " + str(region))
            try:
                if not endpoint:
                    ec2_region.endpoint = EC2RegionData[region]
                else:
                    ec2_region.endpoint = endpoint
            except KeyError:
                raise Exception( 'Unknown region: %s' % region)
        else:
            ec2_region.name = 'eucalyptus'
            if not host:
                if endpoint:
                    ec2_region.endpoint = endpoint
                else:
                    ec2_region.endpoint = self.get_ec2_ip()
        connection_args = { 'aws_access_key_id' : aws_access_key_id,
                            'aws_secret_access_key': aws_secret_access_key,
                            'is_secure': is_secure,
                            'debug':boto_debug,
                            'port' : port,
                            'path' : path,
                            'host' : host}

        if re.search('2.6', boto.__version__):
            connection_args['validate_certs'] = False

        try:
            ec2_connection_args = copy.copy(connection_args)
            ec2_connection_args['path'] = path
            ec2_connection_args['api_version'] = APIVersion
            ec2_connection_args['region'] = ec2_region
            self.debug("Attempting to create ec2 connection to " + ec2_region.endpoint + ':' + str(port) + path)
            self.ec2 = boto.connect_ec2(**ec2_connection_args)
        except Exception, e:
            self.critical("Was unable to create ec2 connection because of exception: " + str(e))

        #Source ip on local test machine used to reach instances
        self.ec2_source_ip = None

    def setup_ec2_resource_trackers(self):
        """
        Setup keys in the test_resources hash in order to track artifacts created
        """
        self.test_resources["reservations"] = []
        self.test_resources["volumes"] = []
        self.test_resources["snapshots"] = []
        self.test_resources["keypairs"] = []
        self.test_resources["security-groups"] = []
        self.test_resources["images"] = []
        self.test_resources["addresses"]=[]
        self.test_resources["auto-scaling-groups"]=[]
        self.test_resources["launch-configurations"]=[]
        self.test_resources["conversion-tasks"]=[]

    def get_ec2_ip(self):
        """Parse the eucarc for the EC2_URL"""
        ec2_url = self.parse_eucarc("EC2_URL")
        return ec2_url.split("/")[2].split(":")[0]

    def get_ec2_path(self):
        """Parse the eucarc for the EC2_URL"""
        ec2_url = self.parse_eucarc("EC2_URL")
        ec2_path = "/".join(ec2_url.split("/")[3:])
        return ec2_path

    def create_tags(self, resource_ids, tags):
        """
        Add tags to the given resource

        :param resource_ids:      List of resources IDs to tag
        :param tags:              Dict of key value pairs to add, for just a name include a key with a '' value
        """
        self.debug("Adding the following tags:" + str(tags))
        self.debug("To Resources: " + str(resource_ids))
        self.ec2.create_tags(resource_ids=resource_ids, tags=tags)

    def delete_tags(self, resource_ids, tags):
        """
        Add tags to the given resource

        :param resource_ids:      List of resources IDs to tag
        :param tags:              Dict of key value pairs to add, for just a name include a key with a '' value
        """
        self.debug("Deleting the following tags:" + str(tags))
        self.debug("From Resources: " + str(resource_ids))
        self.ec2.delete_tags(resource_ids=resource_ids, tags=tags)

    def add_keypair(self, key_name=None):
        """
        Add a keypair with name key_name unless it already exists

        :param key_name:      The name of the keypair to add and download.
        """
        if key_name is None:
            key_name = "keypair-" + str(int(time.time())) 
        self.debug("Looking up keypair " + key_name)
        key = []
        try:
            key = self.ec2.get_all_key_pairs(keynames=[key_name])    
        except EC2ResponseError:
            pass
        
        if not key:
            self.debug( 'Creating keypair: %s' % key_name)
            # Create an SSH key to use when logging into instances.
            key = self.ec2.create_key_pair(key_name)
            # AWS will store the public key but the private key is
            # generated and returned and needs to be stored locally.
            # The save method will also chmod the file to protect
            # your private key.
            key.save(self.key_dir)
            #Add the fingerprint header to file
            keyfile = open(self.key_dir+key.name+'.pem','r')
            data = keyfile.read()
            keyfile.close()
            keyfile = open(self.key_dir+key.name+'.pem','w')
            keyfile.write('KEYPAIR '+str(key.name)+' '+str(key.fingerprint)+"\n")
            keyfile.write(data)
            keyfile.close()
            
            self.test_resources["keypairs"].append(key)
            return key
        else:
            self.debug(  "Key " + key_name + " already exists")
            
            
            
    def verify_local_keypath(self,keyname, path=None, exten=".pem"):
        """
        Convenience function to verify if a given ssh key 'keyname' exists on the local server at 'path'

        :returns: the keypath if the key is found.
        >>> instance= self.get_instances(state='running')[0]
        >>> keypath = self.get_local_keypath(instance.key_name)
        """
        if path is None:
            path = os.getcwd()
        keypath = path + "/" + keyname + exten
        try:
            os.stat(keypath)
            self.debug("Found key at path:"+str(keypath))
        except:
            raise Exception("key not found at the provided path:"+str(keypath))
        return keypath
    
    
    @Eutester.printinfo
    def get_all_current_local_keys(self,path=None, exten=".pem"):
        """
        Convenience function to provide a list of all keys in the local dir at 'path' that exist on the server to help
        avoid producing additional keys in test dev.

        :param path: Filesystem path to search in
        :param exten: extension of private key file
        :return: list of key names
        """
        keylist = []
        keys = self.ec2.get_all_key_pairs()
        keyfile = None
        for k in keys:
            self.debug('Checking local path:'+str(path)+" for keyfile: "+str(k.name)+str(exten))
            try:
                #will raise exception if keypath is not found
                keypath = self.verify_local_keypath(k.name, path, exten)
                if not keypath:
                    continue
                keyfile = open(keypath,'r')
                for line in keyfile.readlines():
                    if re.search('KEYPAIR',line):
                        fingerprint = line.split()[2]
                        break
                keyfile.close()
                if fingerprint == k.fingerprint:
                    self.debug('Found file with matching finger print for key:'+k.name)
                    keylist.append(k)
            except: 
                self.debug('Did not find local match for key:'+str(k.name))
            finally:
                if keyfile and not keyfile.closed:
                    keyfile.close()
        return keylist

    def delete_keypair(self,keypair):

        """
        Delete the keypair object passed in and check that it no longer shows up

        :param keypair: Keypair object to delete and check
        :return: boolean of whether the operation succeeded
        """
        name = keypair.name
        self.debug(  "Sending delete for keypair: " + name)
        keypair.delete()
        try:
            keypair = self.ec2.get_all_key_pairs(keynames=[name])
        except EC2ResponseError:
            keypair = []
            
        if len(keypair) > 0:
            self.fail("Keypair found after attempt to delete it")
            return False
        return True
    
    
    @Eutester.printinfo
    def get_windows_instance_password(self,
                                      instance,
                                      private_key_path=None,
                                      key=None,
                                      dir=None,
                                      exten=".pem",
                                      encoded=True):
        """
        Get password for a windows instance.

        :param instance: euinstance object
        :param private_key_path: private key file used to decrypt password
        :param key: name of private key
        :param dir: Path to private key
        :param exten: extension of private key
        :param encoded: boolean of whether string returned from server is Base64 encoded
        :return: decrypted password
        :raise: Exception when private key cannot be found on filesystem
        """
        self.debug("get_windows_instance_password, instance:"+str(instance.id)+", keypath:"+str(private_key_path)+
                   ", dir:"+str(dir)+", exten:"+str(exten)+", encoded:"+str(encoded))
        key = key or self.get_keypair(instance.key_name)
        if private_key_path is None and key is not None:
            private_key_path = str(self.verify_local_keypath( key.name , dir, exten))
        if not private_key_path:
            raise Exception('get_windows_instance_password, keypath not found?')
        encrypted_string = self.ec2.get_password_data(instance.id)
        if encoded:
            string_to_decrypt = base64.b64decode(encrypted_string)
        else:
            string_to_decrypt = encrypted_string
        popen = Popen(['openssl', 'rsautl', '-decrypt', '-inkey',
                       private_key_path, '-pkcs'], stdin=PIPE, stdout=PIPE)
        (stdout, _) = popen.communicate(string_to_decrypt)
        return stdout

    @Eutester.printinfo
    def add_group(self, group_name=None, description=None, fail_if_exists=False ):
        """
        Add a security group to the system with name group_name, if it exists dont create it

        :param group_name: Name of the security group to create
        :param fail_if_exists: IF set, will fail if group already exists, otherwise will return the existing group
        :return: boto group object upon success or None for failure
        """
        if group_name is None:
            group_name = "group-" + str(int(time.time()))
        if self.check_group(group_name):
            if fail_if_exists:
                self.fail(  "Group " + group_name + " already exists")
            else:
                self.debug(  "Group " + group_name + " already exists")
                group = self.ec2.get_all_security_groups(group_name)[0]
            return self.get_security_group(name=group_name)
        else:
            self.debug( 'Creating Security Group: %s' % group_name)
            # Create a security group to control access to instance via SSH.
            if not description:
                description = group_name
            group = self.ec2.create_security_group(group_name, description)
            self.test_resources["security-groups"].append(group)
        return self.get_security_group(name=group_name)

    def delete_group(self, group):
        """
        Delete the security group object passed in and check that it no longer shows up

        :param group: Group object to delete and check
        :return: bool whether operation succeeded
        """
        name = group.name
        self.debug( "Sending delete for security group: " + name )
        group.delete()
        if self.check_group(name):
            self.fail("Group still found after attempt to delete it")
            return False
        return True

    def check_group(self, group_name):
        """
        Check if a group with group_name exists in the system

        :param group_name: Group name to check for existence
        :return: bool whether operation succeeded
        """
        self.debug( "Looking up group " + group_name )
        try:
            group = self.ec2.get_all_security_groups(groupnames=[group_name])
        except EC2ResponseError:
            return False
        
        if not group:
            return False
        else:
            return True

    @Eutester.printinfo
    def authorize_group_by_name(self,
                                group_name="default",
                                port=22,
                                protocol="tcp",
                                cidr_ip="0.0.0.0/0",
                                src_security_group=None,
                                src_security_group_name=None,
                                src_security_group_owner_id=None,
                                force_args=False):
        """
        Authorize the group with group_name

        :param group_name: Name of the group to authorize, default="default"
        :param port: Port to open, default=22
        :param protocol: Protocol to authorize, default=tcp
        :param cidr_ip: CIDR subnet to authorize, default="0.0.0.0/0" everything
        :param src_security_group_name: Grant access to 'group' from src_security_group_name, default=None
        :return:

        """
        if not force_args:
            if src_security_group or src_security_group_name:
                cidr_ip=None
                port=None
                protocol=None
            if src_security_group:
                src_security_group_owner_id= src_security_group_owner_id or src_security_group.owner_id
                src_security_group_name = src_security_group_name or src_security_group.name

            if src_security_group_name and not src_security_group_owner_id:
                    group = self.get_security_group(name=src_security_group_name)
                    src_security_group_owner_id = group.owner_id

        old_api_version = self.ec2.APIVersion
        try:
            #self.ec2.APIVersion = "2009-10-31"
            if src_security_group_name:
                self.debug( "Attempting authorization of " + group_name + " from " + str(src_security_group_name) +
                            " on port " + str(port) + " " + str(protocol) )
            else:
                self.debug( "Attempting authorization of " + group_name + " on port " + str(port) + " " + str(protocol) )
            self.ec2.authorize_security_group_deprecated(group_name,
                                                         ip_protocol=protocol,
                                                         from_port=port,
                                                         to_port=port,
                                                         cidr_ip=cidr_ip,
                                                         src_security_group_name=src_security_group_name,
                                                         src_security_group_owner_id=src_security_group_owner_id,
                                                         )
            return True
        except self.ec2.ResponseError, e:
            if e.code == 'InvalidPermission.Duplicate':
                self.debug( 'Security Group: %s already authorized' % group_name )
            else:
                raise
        finally:
            self.ec2.APIVersion = old_api_version


    def authorize_group(self,
                        group,
                        port=22,
                        protocol="tcp",
                        cidr_ip="0.0.0.0/0",
                        src_security_group=None,
                        src_security_group_name=None,
                        src_security_group_owner_id=None,
                        force_args=False):
        """
        Authorize the boto.group object

        :param group: boto.group object
        :param port: Port to open, default=22
        :param protocol: Protocol to authorize, default=tcp
        :param cidr_ip: CIDR subnet to authorize, default="0.0.0.0/0" everything
        :param src_security_group_name: Grant access to 'group' from src_security_group_name, default=None
        :param force_args: boolean to send arguments w/o the test method sanitizing them
        :return: True on success
        :raise: Exception if operation fails
        """
        return self.authorize_group_by_name(group.name,
                                            port=port,
                                            protocol=protocol,
                                            cidr_ip=cidr_ip,
                                            src_security_group=src_security_group,
                                            src_security_group_name=src_security_group_name,
                                            src_security_group_owner_id=src_security_group_owner_id,
                                            force_args=force_args)
    
    def terminate_single_instance(self, instance, timeout=300 ):
        """
        Terminate an instance

        :param instance: boto.instance object to terminate
        :param timeout: Time in seconds to wait for terminated state
        :return: True on success
        """
        instance.terminate()
        return self.wait_for_instance(instance, state='terminated', timeout=timeout)

    def wait_for_instance(self,instance, state="running", poll_count = None, timeout=480):
        """
        Wait for the instance to enter the state

        :param instance: Boto instance object to check the state on
        :param state: state that we are looking for
        :param poll_count: Number of 10 second poll intervals to wait before failure (for legacy test script support)
        :param timeout: Time in seconds to wait before failure
        :return: True on success
        :raise: Exception when instance does not enter proper state
        """
        if poll_count is not None:
            timeout = poll_count*10 
        self.debug( "Beginning poll loop for instance " + str(instance) + " to go to " + str(state) )
        instance.update()
        instance_original_state = instance.state
        start = time.time()
        elapsed = 0
        ### If the instance changes state or goes to the desired state before my poll count is complete
        while( elapsed <  timeout ) and (instance.state != state) and (instance.state != 'terminated'):
            #poll_count -= 1
            self.debug( "Instance("+instance.id+") State("+instance.state+"), elapsed:"+str(elapsed)+"/"+str(timeout))
            time.sleep(10)
            instance.update()
            elapsed = int(time.time()- start)
            if instance.state != instance_original_state:
                break
        self.debug("Instance("+instance.id+") State("+instance.state+") time elapsed (" +str(elapsed).split('.')[0]+")")
        #self.debug( "Waited a total o" + str( (self.poll_count - poll_count) * 10 ) + " seconds" )
        if instance.state != state:
            raise Exception( str(instance) + " did not enter "+str(state)+" state after elapsed:"+str(elapsed))

        self.debug( str(instance) + ' is now in ' + instance.state )
        return True

    def wait_for_reservation(self,reservation, state="running",timeout=480):
        """
        Wait for an entire reservation to enter the state

        :param reservation: Boto reservation object to check the state on
        :param state: state that we are looking for
        :param timeout: How long in seconds to wait for state
        :return: True on success
        """
        aggregate_result = True
        instance_list = reservation
        if isinstance(reservation, Reservation):
            instance_list = reservation.instances
        self.debug( "Beginning poll loop for the " + str(len(instance_list))   + " instance found in " + str(instance_list) )
        for instance in instance_list:
            if not self.wait_for_instance(instance, state, timeout=timeout):
                aggregate_result = False
        return aggregate_result
    
    
    @Eutester.printinfo
    def create_volume(self, zone, size=1, eof=True, snapshot=None, timeout=0, poll_interval=10,timepergig=120):
        """
        Create a new EBS volume then wait for it to go to available state, size or snapshot is mandatory

        :param zone: Availability zone to create the volume in
        :param size: Size of the volume to be created
        :param count: Number of volumes to be created
        :param eof: Boolean, indicates whether to end on first instance of failure
        :param snapshot: Snapshot to create the volume from
        :param timeout: Time to wait before failing. timeout of 0 results in size of volume * timepergig seconds
        :param poll_interval: How often in seconds to poll volume state
        :param timepergig: Time to wait per gigabyte size of volume, used when timeout is set to 0
        :return:
        """
        return self.create_volumes(zone, size=size, count=1, mincount=1, eof=eof, snapshot=snapshot, timeout=timeout, poll_interval=poll_interval,timepergig=timepergig)[0]



    @Eutester.printinfo
    def create_volumes(self, 
                       zone,
                       size = 1, 
                       count = 1, 
                       mincount = None, 
                       eof = True, 
                       monitor_to_state = 'available',
                       delay = 0, 
                       snapshot = None, 
                       timeout=0, 
                       poll_interval = 10,
                       timepergig = 120 ):
        """
        Definition:
                    Create a multiple new EBS volumes then wait for them to go to available state, 
                    size or snapshot is mandatory

        :param zone: Availability zone to create the volume in
        :param size: Size of the volume to be created
        :param count: Number of volumes to be created
        :param mincount: Minimum number of volumes to be created to be considered a success.Default = 'count'
        :param eof: Boolean, indicates whether to end on first instance of failure
        :param monitor_to_state: String, if not 'None' will monitor created volumes to the provided state
        :param snapshot: Snapshot to create the volume from
        :param timeout: Time to wait before failing. timeout of 0 results in size of volume * timepergig seconds
        :param poll_interval: How often in seconds to poll volume state
        :param timepergig: Time to wait per gigabyte size of volume, used when timeout is set to 0
        :return: list of volumes
        """
        start = time.time()
        elapsed = 0
        volumes = []
        
        mincount = mincount or count
        if mincount > count:
            raise Exception('Mincount can not be greater than count')
        #if timeout is set to 0, use size to create a reasonable timeout for this volume creation
        if timeout == 0:
            if snapshot is not None:
                timeout = timepergig * int(snapshot.volume_size)
            else:
                timeout = timepergig * size
        
        if snapshot and not hasattr(snapshot,'eutest_volumes'):
                snapshot = self.get_snapshot(snapshot.id)
        self.debug( "Sending create volume request, count:"+str(count) )
        for x in xrange(0,count):
            vol = None
            try:
                cmdstart = time.time()
                vol = self.ec2.create_volume(size, zone, snapshot)
                cmdtime =  time.time() - cmdstart 
                if vol:
                    vol = EuVolume.make_euvol_from_vol(vol, tester=self, cmdstart=cmdstart)
                    vol.eutest_cmdstart = cmdstart
                    vol.eutest_createorder = x
                    vol.eutest_cmdtime = "{0:.2f}".format(cmdtime)
                    vol.size = size
                    volumes.append(vol)
            except Exception, e:
                if eof:
                    #Clean up any volumes from this operation and raise exception
                    for vol in volumes:
                        vol.delete()
                    raise e
                else:
                    self.debug("Caught exception creating volume,eof is False, continuing. Error:"+str(e))
            if delay:
                time.sleep(delay)
        if len(volumes) < mincount:
             #Clean up any volumes from this operation and raise exception
            for vol in volumes:
                vol.delete()
            raise Exception("Created "+str(len(volumes))+"/"+str(count)+
                            ' volumes. Less than minimum specified:'+str(mincount))
        self.debug( str(len(volumes))+"/"+str(count)+" requests for volume creation succeeded." )
        
        if volumes:
            self.print_euvolume_list(volumes)
        
        if not monitor_to_state:
            self.test_resources["volumes"].extend(volumes)
            if snapshot:
                snapshot.eutest_volumes.extend(volumes)
            return volumes
        #If we begain the creation of the min volumes, monitor till completion, otherwise cleanup and fail out
        retlist = self.monitor_created_euvolumes_to_state(volumes,
                                                          eof=eof,
                                                          mincount=mincount,
                                                          state=monitor_to_state,
                                                          poll_interval=poll_interval,
                                                          timepergig=timepergig)
        self.test_resources["volumes"].extend(retlist)
        if snapshot:
            snapshot.eutest_volumes.extend(retlist)
        return retlist
    
    
    @Eutester.printinfo
    def monitor_created_euvolumes_to_state(self,
                                           volumes,
                                           eof=True,
                                           mincount=None,
                                           state='available',
                                           poll_interval=10,
                                           deletefailed=True,
                                           size=1,
                                           timepergig=120):
        """


        Description:
                    Monitors a list of created volumes until 'state' or failure. Allows for a variety of volumes, using
                    different types and creation methods to be monitored by a central method.
        :param volumes: list of created volumes
        :param eof: boolean, if True will end on first failure
        :param mincount: minimum number of successful volumes, else fail
        :param state: string indicating the expected state to monitor to
        :param deletefailed: delete all failed volumes, in eof case deletes 'volumes' list.
               In non-eof, if mincount is met, will delete any failed volumes.
        :param timepergig: integer, time allowed per gig before failing.
        :param poll_interval: int seconds to wait between polling for status
        :param size: int size in gigs to request for volume creation
        """
        
        retlist = []
        failed = []
        elapsed = 0
        
        if not volumes:
            raise Exception("Volumes list empty in monitor_created_volumes_to_state")
        count = len(volumes)
        mincount = mincount or count 
        self.debug("Monitoring "+str(count)+" volumes for at least "+str(mincount)+" to reach state:"+str(state))
        origlist = copy.copy(volumes)
        self.debug("Monitoring "+str(count)+" volumes for at least "+str(mincount)+" to reach state:"+str(state))
        for volume in volumes:
            if not isinstance(volume, EuVolume):
                raise Exception("object not of type EuVolume. Found type:"+str(type(volume)))
        #volume = EuVolume()
        # Wait for the volume to be created.
        self.debug( "Polling "+str(len(volumes))+" volumes for status:\""+str(state)+"\"...")
        start = time.time()
        while volumes:
            for volume in volumes:
                volume.update()
                voltimeout = timepergig * (volume.size or size)
                elapsed = time.time()-start
                self.debug("Volume #"+str(volume.eutest_createorder)+" ("+volume.id+") State("+volume.status+
                           "), seconds elapsed: " + str(int(elapsed))+'/'+str(voltimeout))
                if volume.status == state:
                    #add to return list and remove from volumes list
                    retlist.append(volumes.pop(volumes.index(volume)))
                else:
                    if elapsed > voltimeout:
                        volume.status = 'timed-out'
                    if volume.status == 'failed' or volume.status == 'timed-out':
                        if eof:
                            #Clean up any volumes from this operation and raise exception
                            self.debug(str(volume.id) + " - Failed current status:" + str(volume.status))
                            if deletefailed:
                                self.debug('Failure caught in monitor volumes, attempting to delete all volumes...')
                                for vol in origlist:
                                    try:
                                        self.delete_volume(vol)
                                    except Exception, e:
                                        self.debug('Could not delete volume:'+str(vol.id)+", err:"+str(e))
                            raise Exception(str(volume) + ", failed to reach state:"+str(state)+", vol status:"+
                                            str(volume.eutest_laststatus)+", test status:"+str(vol.status))
                        else:
                            #End on failure is not set, so record this failure and move on
                            msg = str(volume) + " went to: " + volume.status
                            self.debug(msg)
                            volume.eutest_failmsg = msg
                            failed.append(volumes.pop(volumes.index(volume)))
                    #Fail fast if we know we've exceeded our mincount already
                    if (count - len(failed)) < mincount:
                        if deletefailed:
                            buf = ""
                            for failedvol in failed:
                                retlist.remove(failedvol)
                                buf += str(failedvol.id)+"-state:"+str(failedvol.status) + ","
                            self.debug(buf)
                            for vol in origlist:
                                self.debug('Failure caught in monitor volumes, attempting to delete all volumes...')
                                try:
                                    self.delete_volume(vol)
                                except Exception, e:
                                    self.debug('Could not delete volume:'+str(vol.id)+", err:"+str(e))
                        raise Exception("Mincount of volumes did not enter state:"+str(state)+" due to faults")
            self.debug("----Time Elapsed:"+str(int(elapsed))+", Waiting on "+str(len(volumes))+
                       " volumes to enter state:"+str(state)+"-----")
            if volumes:
                time.sleep(poll_interval)
            else:
                break
        #We have at least mincount of volumes, delete any failed volumes
        if failed and deletefailed:
            self.debug( "Deleting volumes that never became available...")
            for volume in failed:
                self.debug('Failure caught in monitor volumes, attempting to delete all volumes...')
                try:
                    self.delete_volume(volume)
                except Exception, e:
                    self.debug('Could not delete volume:'+str(volume.id)+", err:"+str(e))
            buf = str(len(failed))+'/'+str(count)+ " Failed volumes after " +str(elapsed)+" seconds:"
            for failedvol in failed:
                retlist.remove(failedvol)
                buf += str(failedvol.id)+"-state:"+str(failedvol.status)+","
                self.debug(buf)
        self.print_euvolume_list(origlist)
        return retlist

    @Eutester.printinfo
    def monitor_euvolumes_to_status(self,
                                   euvolumes,
                                   status = None,
                                   attached_status = None,
                                   poll_interval=10,
                                   timeout=180,
                                   eof=True,
                                   validate_args=True):
        """
        (See: monitor_created_euvolumes_to_state() if monitoring newly created volumes, otherwise this method is
              intended for monitoring attached and in-use states of volume(s). )
        Definition: monitors a list of euvolumes to a given state.
        Some example valid states:
            status = available, attached_status = None
            status = in-use, attached_status = attached, attaching, detaching

        :param euvolumes:  list of euvolumes to monitor
        :param status: state of volume expected: ie 'in-use', 'available', 'deleted'
        :param attached_status: state of volume's attached data. ie 'attached', 'attaching', 'detaching', 'none'
        :param poll_interval: integer seconds between polling for status updates
        :param timeout: time to wait before failing
        :param eof: exit on first failure encountered, otherwise wait until other volumes pass/fail. Default=True
        :param validate_args: boolean, Will check args for a valid status/available_status pair.
                                If False will monitor to a non-valid state for testing purposes
        """
        good = []
        failed = []
        monitor = []
        failmsg = ""
        self.debug('Monitor_euvolumes_to_state:'+str(status)+"/"+str(attached_status))
        if attached_status and not status:
            status = 'in-use'
        #check for valid states in given arguments...
        if validate_args:
            if (status != 'available') and (status != 'in-use') and (status != 'deleted') and (status != 'failed'):
                raise Exception('Invalid volume states in monitor request:'+str(status)+" != in-use or available")
            if attached_status is None:
                if status != 'available':
                    raise Exception('Invalid volume states in monitor request:'+str(status)+"/"+str(attached_status))
            else:
                if (attached_status == 'attached') or (attached_status == 'attaching') or \
                        (attached_status == 'detaching') or (attached_status == 'detaching'):
                    if status != 'in-use':
                        raise Exception('Invalid volume states in monitor request:'+str(status)+"/"+str(attached_status))
                else:
                    raise Exception('Invalid volume states in monitor request:'+str(status)+"/"+str(attached_status)+
                                    " != attached, attaching, detaching")

        start = time.time()
        elapsed = 0
        self.debug('Updating volume list before monitoring...')
        for vol in euvolumes:
            try:
                vol = self.get_volume(vol.id)
                if not isinstance(vol, EuVolume):
                    vol = EuVolume.make_euvol_from_vol(vol,self)
                monitor.append(vol)
            except:
                self.debug(self.get_traceback())

        self.print_euvolume_list(monitor)
        while monitor and (elapsed < timeout):
            elapsed = int(time.time()-start)
            for vol in monitor:
                last_attached_status = vol.eutest_attached_status
                vol.update()
                if vol.eutest_attached_instance_id:
                    instance_debug_str = ', (att_instance'+str(vol.eutest_attached_instance_id)+")"
                else:
                    instance_debug_str = ""
                self.debug("Monitoring volume:"+str(vol.id)+". Currently state/attached_state:'"+str(vol.status)
                            +"/"+str(vol.eutest_attached_status)+"', needed: '"+str(status)+"/"+str(attached_status)+
                           "'"+instance_debug_str)
                #fail fast for improper state transitions when attaching:
                if attached_status and last_attached_status and not vol.eutest_attached_status:
                    failmsg += str(vol.id)+" - state:"+str(vol.status)+", reverted from attached state:'"\
                              +str(last_attached_status)+"' to '"+str(vol.eutest_attached_status)+"', elapsed:" \
                              +str(elapsed)+"/"+str(timeout)+"\n"
                    if eof:
                        raise VolumeStateException(failmsg)
                    else:
                        failed.append(monitor.pop(monitor.index(vol)))
                        continue
                if (vol.status == 'deleted' and status != 'deleted') or (vol.status == 'failed' and status != 'failed'):
                    failmsg += str(vol.id)+" - detected error in state:'"+str(vol.status)+\
                               "/"+str(vol.eutest_attached_status)+"'"+str(elapsed)+"/"+str(timeout)+"\n"
                    if eof:
                        raise Exception(failmsg)
                    else:
                        failed.append(monitor.pop(monitor.index(vol)))
                        continue
                if vol.status == status:
                        if vol.eutest_attached_status == attached_status:
                            good.append(monitor.pop(monitor.index(vol)))
            self.debug('Waiting for '+str(len(monitor))+ " remaining Volumes. Sleeping for poll_interval: "
                       +str(poll_interval)+" seconds ...")
            self.print_euvolume_list(euvolumes)
            time.sleep(poll_interval)
        self.debug('Done with monitor volumes after '+str(elapsed)+"/"+str(timeout)+"...")
        self.print_euvolume_list(euvolumes)
        if monitor:
            for vol in monitor:
                failmsg +=  str(vol.id)+" -TIMED OUT current state/attached_state:'" \
                        +str(vol.status) + "/" + str(vol.eutest_attached_status) + "' ! = '" \
                        + str(status)+"/" + str(attached_status)+ "', elapsed:" \
                        +str(elapsed)+"/"+str(timeout)+"\n"
            failed.extend(monitor)
        #finally raise an exception if any failures were detected al    long the way...
        if failmsg:
            self.print_euvolume_list(failed)
            raise Exception(failmsg)
        return good


                
    def print_euvolume_list(self,euvolumelist=None):
        """

        :param euvolumelist: list of euvolume
        """
        buf=""
        euvolumes = []
        if not euvolumelist:
            euvolumelist = self.get_volumes()
        if not euvolumelist:
            self.debug('No volumes to print')
            return
        for volume in euvolumelist:
            if not isinstance(volume, EuVolume):
                self.debug("object not of type EuVolume. Found type:"+str(type(volume)))
                volume = EuVolume.make_euvol_from_vol(volume=volume, tester=self)
            euvolumes.append(volume)
        if not euvolumes:
            return
        volume = euvolumes.pop()
        buf = volume.printself()
        for volume in euvolumes:
            buf += volume.printself(title=False)
        self.debug("\n"+str(buf)+"\n")
        
    def print_eusnapshot_list(self,eusnapshots=None):
        """

        :param eusnapshots: list of eusnapshots
        """
        buf=""
        print_list = []
        if not eusnapshots:
            eusnapshots = self.get_snapshots()
        if not eusnapshots:
            self.debug('No snapshots to print')
            return
        for snapshot in eusnapshots:
            if not isinstance(snapshot, EuSnapshot):
                self.debug("object not of type EuSnapshot. Found type:"+str(type(snapshot)))
                snapshot = EuSnapshot.make_eusnap_from_snap(snapshot=snapshot, tester=self)
            print_list.append(snapshot)
        snapshot = print_list.pop()
        buf = snapshot.printself()
        for snapshot in print_list:
            buf += snapshot.printself(title=False)
        self.debug("\n"+str(buf)+"\n")

    def wait_for_volume(self, volume, status="available"):
        def get_volume_state():
            volume.update()
            return volume.status
        self.wait_for_result(get_volume_state, status)

    def delete_volume(self, volume, poll_interval=10, timeout=180):
        """
        Delete the EBS volume then check that it no longer exists

        :param poll_interval: int seconds to wait between polls to server for status
        :param timeout: int in seconds used for time to wait before failure
        :param volume: Volume object to delete
        :return: bool, success of the operation
        """
        try:
            self.ec2.delete_volume(volume.id)
        except Exception, e:
            self.debug('Caught err while sending delete for volume:'+ str(volume.id) + " err:" + str(e))
            self.debug('Monitoring to deleted state after catching error...')
        self.debug( "Sent delete for volume: " +  str(volume.id) + ", monitor to deleted state or failure"  )
        start = time.time()
        elapsed = 0
        volume_id = volume.id
        volume.update()
        while elapsed < timeout:
            try:
                chk_volume = self.get_volume(volume_id=volume_id)
                if not chk_volume:
                    self.debug(str(volume_id) + ', Volume no longer exists on system, deleted')
                    break
                chk_volume.update()
                self.debug( str(chk_volume) + " in " + chk_volume.status + " sleeping:"+str(poll_interval)+", elapsed:"+str(elapsed))
                if chk_volume.status == "deleted":
                    break
                time.sleep(poll_interval)
                elapsed = int(time.time()-start)
            except EC2ResponseError as e:
                if e.status == 400:
                    self.debug(str(volume_id) + "no longer exists in system")
                    if volume in self.test_resources['volumes']:
                        self.test_resources['volumes'].remove(volume)
                    return True
                else:
                    raise e
            if volume in self.test_resources['volumes']:
                self.test_resources['volumes'].remove(volume)
            return True


        if volume.status != 'deleted':
            self.fail(str(volume) + " left in " +  volume.status + ',elapsed:'+str(elapsed))
            return False
        return True
    
    def delete_volumes(self, volume_list, poll_interval=10, force_send=False, timeout=180):
        """
        Deletes a list of EBS volumes then checks for proper state transition

        :param volume_list: List of volume objects to be deleted
        :param poll_interval: integer, seconds between polls on volumes' state
        :param timeout: integer time allowed before this method fails
        """
        errmsg = ''
        errlist = []
        if volume_list:
            vollist = copy.copy(volume_list)
        else:
            raise Exception("delete_volumes: volume_list was empty")
        for volume in vollist:
            try:
                self.debug( "Sending delete for volume: " +  str(volume.id))
                if volume in self.test_resources['volumes']:
                    self.test_resources['volumes'].remove(volume)
                volumes = self.ec2.get_all_volumes([volume.id])
                if len(volumes) == 1:
                    volume = volumes[0]
                    #previous_status = volume.status
                    #self.ec2.delete_volume(volume.id)
                elif len(volumes) == 0:
                    vollist.remove(volume)
                    continue
                previous_status = volume.status
                self.ec2.delete_volume(volume.id)
            except EC2ResponseError, be:
                err = "ERROR: " + str(volume.id) + ", " + str(be.status)+ ", " + str(be.reason) + \
                          ", " +str(be.error_message) + "\n"
                if previous_status == 'deleting':
                    self.debug(str(volume.id)+ ":" + str(previous_status) + ', err:' + str(err))
                else:
                    errmsg += err
                    errlist.append(volume)
                    self.debug(err)
        for volume in errlist:
            if volume in vollist:
                vollist.remove(volume)
        start = time.time()
        elapsed = 0
        while vollist and elapsed < timeout:
            for volume in vollist:
                volumes = self.ec2.get_all_volumes([volume.id])
                if len(volumes) == 1:
                    volume = volumes[0]
                elif len(volumes) == 0:
                    vollist.remove(volume)
                    self.debug("Volume no longer found")
                    continue
                self.debug(str(volume) + " in " + volume.status)
                if volume and volume.status == "deleted"and volume in vollist:
                    vollist.remove(volume)
                    if volume in self.test_resources['volumes']:
                        self.test_resources['volumes'].remove(volume)
                elapsed = int(time.time()-start)
            time.sleep(poll_interval)
            self.debug("---Waiting for:"+str(len(vollist))+" volumes to delete. Sleeping:"+
                       str(poll_interval)+", elapsed:"+str(elapsed)+"/"+str(timeout)+"---")
        if vollist or errmsg:
                for volume in vollist:

                  errmsg += "ERROR:"+str(volume) + " left in " +  volume.status + ',elapsed:'+str(elapsed) + "\n"
                raise Exception(errmsg)


    def delete_all_volumes(self):
        """
        Deletes all volumes on the cloud
        """
        volumes = self.ec2.get_all_volumes()
        self.delete_volumes(volumes)

        
    @Eutester.printinfo    
    def attach_volume(self, instance, volume, device_path, pause=10, timeout=120):
        """
        Attach a volume to an instance

        :param instance: instance object to attach volume to
        :param volume: volume object to attach
        :param device_path: device name to request on guest
        :param pause: Time in seconds to wait before checking volume state
        :param timeout: Total time in seconds to wait for volume to reach the attached state
        :return:
        :raise: Exception of failure to reach proper state or enter previous state
        """
        self.debug("Sending attach for " + str(volume) + " to be attached to " + str(instance) +
                   " at requested device  " + device_path)
        volume.attach(instance.id,device_path )
        start = time.time()
        elapsed = 0  
        volume.update()
        status = ""
        failmsg = ""
        laststatus=None
        while elapsed < timeout:
            volume.update()
            attach_status=None
            if volume.attach_data is not None:
                if re.search("attached",str(volume.attach_data.status)):
                    self.debug(str(volume) + ", Attached: " +  volume.status+ " - " +
                               str(volume.attach_data.status) + ", elapsed:"+str(elapsed))
                    return True
                else:
                    attach_status = volume.attach_data.status
                    if attach_status:
                        laststatus = attach_status
                    elif laststatus and not attach_status:
                        failmsg += str(volume.id)+" - state:"+str(volume.status)+", reverted from attached state:'" \
                                   +str(laststatus)+"' to '"+str(attach_status)+"', elapsed:" \
                                   +str(elapsed)+"/"+str(timeout)+"\n"
                        raise VolumeStateException(failmsg)
            self.debug( str(volume) + ", state:" + volume.status+', attached status:'+str(attach_status) +
                        ", elapsed:"+str(elapsed)+'/'+str(timeout))
            self.sleep(pause)
            elapsed = int(time.time()-start)

    def detach_volume(self, volume, pause = 10, timeout=60):
        """
        Detach a volume

        :param volume: volume to detach
        :param pause: Time in seconds to wait before checking volume state
        :param timeout: Total time in seconds to wait for volume to reach the attached state
        :return: True on success
        """
        attach_data_status = None
        instance_id = None
        if volume is None:
            raise Exception(str(volume) + " does not exist")
        volume.detach()
        self.debug( "Sent detach for volume: " + volume.id + " which is currently in state: " + volume.status)
        start = time.time()
        elapsed = 0  
        while elapsed < timeout:
            volume.update()
            if volume.status != "in-use":
                self.debug(str(volume) + " left in " +  volume.status)
                return True
            if volume.attach_data is not None:
                attach_data_status = volume.attach_data.status
                if not instance_id:
                    instance_id = volume.attach_data.instance_id
            else:
                attach_data_status = None
            self.debug( str(volume) + " state:" + volume.status + ", attached_data:"+
                        str(attach_data_status)+", pause:"+str(pause)+", instance:"+str(instance_id)+", elapsed:"+str(elapsed))
            self.sleep(pause)
            elapsed = int(time.time() - start)
        raise Exception(str(volume.id)+':DETACH FAILED - Volume status remained at:'+
                        str(volume.status)+', attach_data_status:'+str(attach_data_status)+", instance: "+str(instance_id))
    
    def get_volume_time_attached(self,volume):
        """
        Get the seconds elapsed since the volume was attached.

        :type volume: boto volume object
        :param volume: The volume used to calculate the elapsed time since attached.

        :rtype: integer
        :returns: The number of seconds elapsed since this volume was attached.
        """
        self.debug("Getting time elapsed since volume attached...")
        volume.update()
        if volume.attach_data is None:
            raise Exception('get_time_since_vol_attached: Volume '+str(volume.id)+" not attached")
        #get timestamp from attach_data
        attached_time = self.get_datetime_from_resource_string(volume.attach_data.attach_time)
        #return the elapsed time in seconds
        return time.mktime(datetime.utcnow().utctimetuple()) - time.mktime(attached_time.utctimetuple())
    
    @classmethod
    def get_volume_time_created(cls,volume):
        """
        Get the seconds elapsed since the volume was created.

        :type volume: boto volume object
        :param volume: The volume used to calculate the elapsed time since created.

        :rtype: integer
        :returns: The number of seconds elapsed since this volume was created.
        """
        volume.update()
        #get timestamp from attach_data
        create_time = cls.get_datetime_from_resource_string(volume.create_time)
        #return the elapsed time in seconds
        return time.mktime(datetime.utcnow().utctimetuple()) - time.mktime(create_time.utctimetuple())
    
    @classmethod
    def get_snapshot_time_started(cls,snapshot):
        """
        Get the seconds elapsed since the snapshot was started.

        :type snapshot: boto snapshot object
        :param snapshot: The volume used to calculate the elapsed time since started.

        :rtype: integer
        :returns: The number of seconds elapsed since this snapshot was started.
        """
        snapshot.update()
        #get timestamp from attach_data
        start_time = cls.get_datetime_from_resource_string(snapshot.start_time)
        #return the elapsed time in seconds
        return time.mktime(datetime.utcnow().utctimetuple()) - time.mktime(start_time.utctimetuple())
    
    @classmethod
    def get_instance_time_launched(cls,instance):
        """
        Get the seconds elapsed since the volume was attached.

        :type volume: boto volume object
        :param volume: The volume used to calculate the elapsed time since attached.

        :rtype: integer
        :returns: The number of seconds elapsed since this volume was attached.
        """
        #instance.update()
        #get timestamp from launch data
        if not instance.launch_time:
            return None
        launch_time = cls.get_datetime_from_resource_string(instance.launch_time)
        #return the elapsed time in seconds
        return time.mktime(datetime.utcnow().utctimetuple()) - time.mktime(launch_time.utctimetuple())
    
    @classmethod
    def get_datetime_from_resource_string(cls,
                                          timestamp,
                                          time_format="%Y %m %d %H %M %S"):
        """
        Convert a typical resource timestamp to datetime time_struct.

        :type timestamp: string
        :param timestamp: Timestamp held within specific boto resource objects.
                          Example timestamp format: 2012-09-19T21:24:03.864Z

        :rtype: time_struct
        :returns: The time_struct representation of the timestamp provided.
        """
        t = re.findall('\w+',str(timestamp).replace('T',' '))
        #remove milliseconds from list...
        t.pop()
        #create a time_struct out of our list
        return datetime.strptime(" ".join(t), time_format)
    
    
    @Eutester.printinfo
    def create_snapshot_from_volume(self, volume, wait_on_progress=40, poll_interval=10, timeout=0, description=""):
        """
        Create a new EBS snapshot from an existing volume then wait for it to go to the created state.
        By default will poll for poll_count.  If wait_on_progress is specified than will wait on "wait_on_progress"
        overrides # of poll_interval periods, using wait_on_progress # of periods of poll_interval length in seconds
        w/o progress before failing. If volume.id is passed, euvolume data will not be transfered to snapshot created. 

        :param volume_id: (mandatory string) Volume id of the volume to create snapshot from
        :param wait_on_progress:(optional integer) # of poll intervals to wait while 0 progress is made before exiting,
         overrides "poll_count" when used
        :param poll_interval: (optional integer) time to sleep between polling snapshot status
        :param timeout: (optional integer) over all time to wait before exiting as failure
        :param description:  (optional string) string used to describe the snapshot
        :return: EuSnapshot
        """
        return self.create_snapshots(volume, count=1, mincount=1, eof=True, wait_on_progress=wait_on_progress,
                                     poll_interval=poll_interval, timeout=timeout, description=description)[0]
        
        
    @Eutester.printinfo
    def create_snapshot(self, volume_id, wait_on_progress=40, poll_interval=10, timeout=0, description=""):
        """
        Create a new single EBS snapshot from an existing volume id then wait for it to go to the created state.
        By default will poll for poll_count.  If wait_on_progress is specified than will wait on "wait_on_progress"
        overrides # of poll_interval periods, using wait_on_progress # of periods of poll_interval length in seconds
        w/o progress before failing. If volume.id is passed, euvolume data will not be transfered to snapshot created. 

        :param volume_id: (mandatory string) Volume id of the volume to create snapshot from
        :param wait_on_progress:(optional integer) # of poll intervals to wait while 0 progress is made before exiting,
         overrides "poll_count" when used
        :param poll_interval: (optional integer) time to sleep between polling snapshot status
        :param timeout: (optional integer) over all time to wait before exiting as failure
        :param description:  (optional string) string used to describe the snapshot
        :return: EuSnapshot
        """
        snapshots = self.create_snapshots_from_vol_id(volume_id, count=1, mincount=1, eof=True,
                                                      wait_on_progress=wait_on_progress, poll_interval=poll_interval,
                                                      timeout=timeout, description=description)
        if len(snapshots) == 1:
            return snapshots[0]
        else:
            raise Exception("create_snapshot: Expected 1 snapshot, got '"+str(len(snapshots))+"' snapshots")
    
    
    @Eutester.printinfo
    def create_snapshots_from_vol_id(self,
                                     volume_id,
                                     count=1,
                                     mincount=None,
                                     eof=True,
                                     delay=0,
                                     wait_on_progress=40,
                                     poll_interval=10,
                                     timeout=0,
                                     description=""):
        """
        Create a new EBS snapshot from an existing volume' string then wait for it to go to the created state.
        By default will poll for poll_count.  If wait_on_progress is specified than will wait on "wait_on_progress"
        overrides # of poll_interval periods, using wait_on_progress # of periods of poll_interval length in seconds
        w/o progress before failing

        :param volume_id: (mandatory string) Volume id of the volume to create snapshot from
        :parram count: (optional Integer) Specify how many snapshots to attempt to create
        :param mincount: (optional Integer) Specify the min success count, defaults to 'count'
        :param eof: (optional boolean) End on failure.If true will end on first failure, otherwise will continue to try
         and fufill mincount
        :param wait_on_progress:(optional integer) # of poll intervals to wait while 0 progress is made before exiting,
         overrides "poll_count" when used
        :param poll_interval: (optional integer) time to sleep between polling snapshot status
        :param timeout: (optional integer) over all time to wait before exiting as failure
        :param description:  (optional string) string used to describe the snapshot
        :return: EuSnapshot list
        """
        if isinstance(volume_id, Volume):
            raise Exception('Expected volume.id got Volume, try create_snapshots or create_snapshot_from_volume methods instead')
        volume = EuVolume.make_euvol_from_vol(self.get_volume(volume_id), tester=self)
        return self.create_snapshots(volume,
                                     count=count, mincount=mincount, eof=eof, delay=delay,
                                     wait_on_progress=wait_on_progress, poll_interval=poll_interval,
                                     timeout=timeout, description=description)



    @Eutester.printinfo
    def create_snapshots(self, 
                         volume, 
                         count=1, 
                         mincount=None, 
                         eof=True, 
                         delay=0, 
                         wait_on_progress=40,
                         poll_interval=10, 
                         timeout=0, 
                         monitor_to_completed=True,
                         delete_failed = True, 
                         description="Created by eutester"):
        """
        Create a new EBS snapshot from an existing volume then wait for it to go to the created state.
        By default will poll for poll_count.  If wait_on_progress is specified than will wait on "wait_on_progress"
        overrides # of poll_interval periods, using wait_on_progress # of periods of poll_interval length in seconds
        w/o progress before failing

        :param volume: (mandatory Volume object) Volume to create snapshot from
        :parram count: (optional Integer) Specify how many snapshots to attempt to create
        :param mincount: (optional Integer) Specify the min success count, defaults to 'count'
        :param eof: (optional boolean) End on failure.
                    If true will end on first failure, otherwise will continue to try and fufill mincount
        :param wait_on_progress: (optional integer) # of poll intervals to wait while 0 progress is made before exiting,
                                 overrides "poll_count" when used
        :param poll_interval: (optional integer) time to sleep between polling snapshot status
        :param monitor_to_completed: (optional boolean) If true will monitor created snapshots to the completed state,
                                     else return a list of created snaps
        :param timeout: (optional integer) over all time to wait before exiting as failure
        :param delete_failed: (optional boolean) automatically delete failed volumes
        :param description: (optional string) string used to describe the snapshot
        :return: EuSnapshot list
        """
        #Fix EuSnapshot for isinstance() use later...
        if not hasattr(volume, 'md5'):
            volume = EuVolume.make_euvol_from_vol(volume,tester= self)
        volume_id = volume.id
        snapshots = []
        retlist = []
        failed = []
        mincount = mincount or count
        if mincount > count:
            raise Exception('Mincount can not be greater than count')
        if wait_on_progress > 0:
            poll_count = wait_on_progress
        else:
            poll_count = self.poll_count
        last_progress = 0
        elapsed = 0
        polls = 0
        self.debug('Create_snapshots count:'+str(count)+", mincount:"+str(mincount)+', wait_on_progress:'+
                    str(wait_on_progress)+",eof:"+str(eof))
        for x in xrange(0,count):
            try:
                start = time.time()
                snapshot = self.ec2.create_snapshot( volume_id, description=str(description))
                cmdtime = time.time()-start
                if snapshot:
                    self.debug("Attempting to create snapshot #"+str(x)+ ", id:"+str(snapshot.id))
                    snapshot = EuSnapshot().make_eusnap_from_snap(snapshot, tester=self ,cmdstart=start)
                    #Append some attributes for tracking snapshot through creation and test lifecycle.
                    snapshot.eutest_polls = 0
                    snapshot.eutest_poll_count = poll_count
                    snapshot.eutest_last_progress = 0
                    snapshot.eutest_failmsg = "FAILED"
                    snapshot.eutest_laststatus = None
                    snapshot.eutest_timeintest = 0
                    snapshot.eutest_createorder = x
                    snapshot.eutest_cmdtime = "{0:.2f}".format(cmdtime)
                    snapshot.eutest_volume_md5 = volume.md5
                    snapshot.eutest_volume_md5len = volume.md5len
                    snapshot.eutest_volume_zone = volume.zone
                    
                    snapshot.update()
                    if description and (not re.match(str(snapshot.description), str(description)) ):
                        raise Exception('Snapshot Description does not match request: Snap.description:"'+
                                        str(snapshot.description)+'" -vs- "'+str(description)+'"')

                    if snapshot:
                        snapshots.append(snapshot)
            except Exception, e:
                self.debug("Caught exception creating snapshot,eof is False, continuing. Error:"+str(e))
                if eof:
                    if delete_failed:
                        try:
                            self.delete_snapshots(snapshots)
                        except: pass
                    raise e
                else:
                    failed.append(snapshot)
                    #Check to see if our min count of snapshots succeeded, we allow this for specific tests. 
                    #If not clean up all snapshots from this system created from this operation
                    if (count - len(failed)) > mincount:
                        if delete_failed: 
                            snapshots.extend(failed)
                            try:
                                self.delete_snapshots(snapshots)
                            except:pass
                            raise Exception('Failed to created mincount('+str(mincount)+
                                            ') number of snapshots from volume:'+str(volume_id))
            #If a delay was given, wait before next snapshot gets created
            if delay:
                time.sleep(delay)
        #If we have failed snapshots,
        # but still met our minimum clean up the failed and continue (this might be better as a thread?)...
        if failed and delete_failed:
                try:
                    self.delete_snapshots(failed)
                except: pass
        #Pass the list of created snapshots to monitor method if state was not None,
        # otherwise just return the list of newly created
        #snapshots. 
        if monitor_to_completed:
            snapshots = self.monitor_eusnaps_to_completed(snapshots, 
                                                        mincount=mincount, 
                                                        eof=eof, 
                                                        wait_on_progress=wait_on_progress, 
                                                        poll_interval=poll_interval, 
                                                        timeout=timeout, 
                                                        delete_failed=delete_failed
                                                        )
        return snapshots
        
        
    @Eutester.printinfo
    def monitor_eusnaps_to_completed(self,
                                     snaps,
                                     mincount=None, 
                                     eof=True,
                                     wait_on_progress=40,
                                     poll_interval=10, 
                                     timeout=0,
                                     monitor_to_progress = None,
                                     delete_failed=True ):
        """
        Monitor an EBS snapshot list for snapshots to enter the to the completed state.
        By default will poll for poll_count.  If wait_on_progress is specified than will wait on "wait_on_progress"
        overrides # of poll_interval periods, using wait_on_progress # of periods of poll_interval length in seconds
        w/o progress before failing

        :param snaps: list of eusnapshots to monitor
        :param mincount: (optional Integer) Specify the min success count, defaults to length of list provided
        :param eof: (optional boolean) End on failure.If true will end on first failure,
                    otherwise will continue to try and fufill mincount
        :param wait_on_progress: (optional integer) # of poll intervals to wait while 0 progress is made before exiting,
                                 overrides "poll_count" when used
        :param poll_interval: (optional integer) time to sleep between polling snapshot status
        :param timeout: (optional integer) over all time to wait before exiting as failure
        :param monitor_to_progress (optional integer): will consider the monitor successful and exit when the snapshot's
                                                        progress is >= this value
        :param delete_failed: (optional boolean) automatically delete failed volumes
        :return: EuSnapshot list
        """
              
        failed = []
        retlist = []
        elapsed = 0
        self.debug("Monitor_snapshot_to_completed starting...")
        mincount = mincount or len(snaps)
        if mincount > len(snaps):
            raise Exception('Mincount can not be greater than count')
        if wait_on_progress > 0:
            poll_count = wait_on_progress
        else:
            poll_count = self.poll_count
        last_progress = 0
        monitor_start = time.time()
        for snap in snaps:
            if not isinstance(snap, EuSnapshot):
                raise Exception("object not of type EuSnapshot. Found type:"+str(type(snap)))
        snapshots = copy.copy(snaps)      
        for snap in snapshots:
            if not snap.eutest_polls:
                snap.eutest_poll_count = poll_count
        
        self.debug('Waiting for '+str(len(snapshots))+" snapshots to go to completed state...")
        
        while (timeout == 0 or elapsed <= timeout) and snapshots:
            self.debug("Waiting for "+str(len(snapshots))+" snapshots to complete creation")
            for snapshot in snapshots:
                try:
                    snapshot.eutest_polls += 1
                    snapshot.update()
                    snapshot.eutest_laststatus = snapshot.status
                    if snapshot.status == 'failed':
                        raise Exception(str(snapshot) + " failed after Polling("+str(snapshot.eutest_polls)+
                                        ") ,Waited("+str(elapsed)+" sec), last reported (status:" + snapshot.status+
                                        " progress:"+snapshot.progress+")")
                    curr_progress = int(snapshot.progress.replace('%',''))
                    #if progress was made, then reset timer 
                    if (wait_on_progress > 0) and (curr_progress > snapshot.eutest_last_progress):
                        snapshot.eutest_poll_count = wait_on_progress
                    else: 
                        snapshot.eutest_poll_count -= 1
                    snapshot.eutest_last_progress = curr_progress
                    elapsed = int(time.time()-monitor_start)
                    if snapshot.eutest_poll_count <= 0:
                        raise Exception("Snapshot did not make progress for "+str(wait_on_progress)+" polls, after "+
                                        str(elapsed)+" seconds")
                    self.debug(str(snapshot.id)+", Status:"+snapshot.status+", Progress:"+snapshot.progress+
                               ", Polls w/o progress:"+str(wait_on_progress-snapshot.eutest_poll_count)+"/"+
                               str(wait_on_progress)+", Time Elapsed:"+str(elapsed)+"/"+str(timeout))
                    if snapshot.status == 'completed':
                        self.debug(str(snapshot.id)+" created after " + str(elapsed) + " seconds. Status:"+
                                   snapshot.status+", Progress:"+snapshot.progress)
                        self.test_resources["snapshots"].append(snapshot)
                        snapshot.eutest_timeintest = elapsed
                        snapshot.eutest_failmsg ='SUCCESS'
                        retlist.append(snapshot)
                        snapshots.remove(snapshot)
                    if monitor_to_progress and (curr_progress >=  monitor_to_progress):
                        self.debug(str(snapshot.id)+" reached designated monitor state after " + str(elapsed) + " seconds. Status:"+
                                   snapshot.status+", Progress:"+snapshot.progress)
                        self.test_resources["snapshots"].append(snapshot)
                        snapshot.eutest_timeintest = elapsed
                        retlist.append(snapshot)
                        snapshots.remove(snapshot)
                except Exception, e:
                    tb = self.get_traceback()
                    errbuf = '\n' + str(tb) + '\n' + str(e)
                    self.debug("Exception caught in snapshot creation, snapshot:"+str(snapshot.id)+".Err:"+str(errbuf))
                    if eof:
                        #If exit on fail, delete all snaps and raise exception
                        self.delete_snapshots(snapshots)
                        raise e
                    else:
                        snapshot.eutest_failmsg = str(e)
                        snapshot.eutest_timeintest = elapsed
                        failed.append(snapshot)
                        snapshots.remove(snapshot)
            elapsed = int(time.time()-monitor_start)
            if snapshots:
                time.sleep(poll_interval)
        for snap in snapshots:
            snapshot.eutest_failmsg = "Snapshot timed out in creation after "+str(elapsed)+" seconds"
            snapshot.eutest_timeintest = elapsed
            failed.append(snapshot)
            snapshots.remove(snapshot)
        #If delete_failed flag is set, delete the snapshots believed to have failed...
        if delete_failed:
                try:
                   self.delete_snapshots(failed)
                except: pass
        #join the lists again for printing debug purposes, retlist should only contain snaps believed to be good
        snapshots = copy.copy(retlist)
        snapshots.extend(failed)
        #Print the results in a formated table
        self.print_eusnapshot_list(snapshots)
        #Check for failure and failure criteria and return 
        self.test_resources['snapshots'].extend(snapshots)
        if failed and eof:
            raise(str(len(failed))+' snapshots failed in create, see debug output for more info')
        if len(retlist) < mincount:
            raise('Created '+str(len(retlist))+'/'+str(mincount)+
                  ' snapshots is less than provided mincount, see debug output for more info')
        return retlist
    
    
    def get_snapshot(self,snapid=None):
        snaps = self.get_snapshots(snapid=snapid, maxcount=1)
        if snaps:
            return snaps[0]
        else:
            return None
    
    
    
    @Eutester.printinfo   
    def get_snapshots(self,
                      snapid=None,
                      volume_id=None,
                      volume_size=None,
                      volume_md5=None,
                      filters=None,
                      maxcount=None,
                      owner_id=None):
        """

        :param snapid: string, snapshot id to use as filter
        :param volume_id: string, volume id to use as filter
        :param volume_size: int size of volume snap'd to use as filter
        :param volume_md5: string md5 checksum of vol snap'd to use as filter
        :param maxcount: int max number of snaps to match before returning list
        :param owner_id: string owner id to use as filter
        :return: list of snapshots found
        """
        retlist = []
        #Start by comparing resources the current test obj is tracking to see if they are still in sync with the system
        snapshots = copy.copy(self.test_resources['snapshots'])
        snapshot_list = []
        if snapid:
            snapshot_list.append(snapid)
        ec2_snaps =  self.ec2.get_all_snapshots(snapshot_ids=snapshot_list, filters=filters, owner=owner_id)
        for snap in ec2_snaps:
            if snap not in snapshots:
                snapshots.append(snap)
        for snap in snapshots:
            if not snap in ec2_snaps:
                self.debug('Snapshot:'+str(snap.id)+' no longer found on system')
            if not hasattr(snap,'eutest_volume_md5'):
                snap = EuSnapshot.make_eusnap_from_snap(snap, tester=self)
            self.debug("Checking snap:"+str(snap.id)+" for match...")
            if volume_id and snap.volume_id != volume_id:
                continue
            if volume_size and snap.volume_size != volume_size:
                continue
            if volume_md5 and snap.eutest_volume_md5 != volume_md5:
                continue
            retlist.append(snap)
            if maxcount and (len(retlist) >= maxcount):
                return retlist
        self.debug("Found "+str(len(retlist))+" snapshots matching criteria")
        return retlist
    
    
    @Eutester.printinfo
    def delete_snapshots(self,
                         snapshots, 
                         valid_states='completed,failed', 
                         base_timeout=60, 
                         add_time_per_snap=10, 
                         wait_for_valid_state=120,
                         poll_interval=10, 
                         eof=False):
        """
        Delete a list of snapshots.

        :param snapshots: List of snapshot IDs
        :param valid_states: Valid status for snapshot to
                             enter (Default: 'completed,failed')
        :param base_timeout: Timeout for waiting for poll interval
        :param add_time_per_snap: Amount of time to add to base_timeout
                                  per snapshot in the list
        :param wait_for_valid_state: How long to wait for a valid state to
                                     be reached before attempting delete, as
                                     some states will reject a delete request.
        :param poll_interval: Time to wait between checking the snapshot states
        :param eof: Whether or not to call an Exception() when first
                    failure is reached
        :raise:
        """
        snaps = copy.copy(snapshots)
        delete_me = []
        start = time.time()
        elapsed = 0
        valid_delete_states = str(valid_states).split(',')
        if not valid_delete_states:
            raise Exception("delete_snapshots, error in valid_states "
                            "provided:" + str(valid_states))

        #Wait for snapshot to enter a state that will accept the deletion action, before attempting to delete it...
        while snaps and (elapsed < wait_for_valid_state):
            elapsed = int(time.time()-start)
            check_state_list = copy.copy(snaps)
            for snap in check_state_list:
                try:
                    snap_id = self.get_snapshot(snap.id)
                    if not snap_id:
                        self.debug("Get Snapshot not found, assuming it's "
                                   "already deleted:" + str(snap.id))
                        delete_me.append(snap)
                        break
                except EC2ResponseError as ec2e:
                    if ec2e.status == 400:
                        self.debug("Get Snapshot not found, assuming it's "
                                   "already deleted:" + str(snap.id) +
                                   ", err:" + str(ec2e))
                        delete_me.append(snap)
                else:
                    snap.update()
                    self.debug("Checking snapshot:" + str(snap.id) +
                               " status:"+str(snap.status))
                    for v_state in valid_delete_states:
                        v_state = str(v_state).rstrip().lstrip()
                        if snap.status == v_state:
                            delete_me.append(snap)
                            try:
                                snap.delete()
                            except EC2ResponseError as ec2e:
                                self.debug("Snapshot not found, assuming "
                                           "it's already deleted:" +
                                           str(snap.id))
                                delete_me.append(snap)
                            break
            for snap in delete_me:
                if snap in snaps:
                    snaps.remove(snap)
            if snaps:
                buf = "\n-------| WAITING ON " + str(len(snaps)) + \
                      " SNAPSHOTS TO ENTER A DELETE-ABLE STATE:(" + \
                      str(valid_states) + "), elapsed:" + str(elapsed) + \
                      '/' + str(wait_for_valid_state) + "|-----"
                for snap in snaps:
                    buf = buf + "\nSnapshot:"+str(snap.id) + ",status:" + \
                          str(snap.status)+", progress:"+str(snap.progress)
                self.debug(buf)
                self.debug('waiting poll_interval to recheck snapshots:' +
                           str(poll_interval) +' seconds')
                time.sleep(poll_interval)
        #Now poll all the snapshots which a delete() request was made for
        if snaps:
            buf = ""
            for snap in snaps:
                buf = buf+','+str(snap.id)
            msg = "Following snapshots did not enter a valid state(" + \
                  str(valid_states) + ") for deletion:" + str(buf)
            if eof:
                raise Exception(msg)
            else:
                self.debug(msg)
        start = time.time()
        elapsed = 0
        timeout= base_timeout + (add_time_per_snap*len(delete_me))
        # Wait for all snapshots in delete_me list to be deleted or timeout...
        while delete_me and (elapsed < timeout):
            self.debug('Waiting for remaining ' + str(int(len(delete_me))) +
                       ' snaps to delete...' )
            waiting_list = copy.copy(delete_me)
            for snapshot in waiting_list:
                try:
                    snapshot.update()
                    get_snapshot = self.ec2.get_all_snapshots(
                        snapshot_ids=[snapshot.id])
                except EC2ResponseError as ec2re:
                    self.debug("Snapshot not found, assuming "
                                           "it's already deleted:" +
                                           str(snapshot.id))
                if not get_snapshot or snapshot.status == 'deleted':
                    self.debug('Snapshot:'+str(snapshot.id)+" is deleted")
                    delete_me.remove(snapshot)
                    #snapshot is deleted remove it from test resources list
                    for testsnap in self.test_resources['snapshots']:
                        if snapshot.id == testsnap.id:
                            self.test_resources['snapshots'].remove(testsnap)
            if delete_me and (elapsed < timeout):
                time.sleep(poll_interval)
            elapsed = int(time.time()-start)
        # Record any snapshots not yet deleted as errors...
        if delete_me:
            buf = ""
            for snap in snaps:
                buf += "\nSnapshot:" + str(snap.id)+",status:" + \
                       str(snap.status) + ", progress:"+str(snap.progress) +\
                       ", elapsed:" + str(elapsed) + '/' + str(timeout)
            raise Exception("Snapshots did not delete within timeout:" +
                            str(timeout) + "\n" + str(buf))
                
             
        
    
    def delete_snapshot(self,snapshot,timeout=60):
        """
        Delete the snapshot object

        :param snapshot: boto.ec2.snapshot object to delete
        :param timeout: Time in seconds to wait for deletion
        """
        snapshot.delete()
        self.debug( "Sent snapshot delete request for snapshot: " + snapshot.id)
        return self.delete_snapshots([snapshot], base_timeout=60)
    
    @Eutester.printinfo
    def register_snapshot(self,
                          snapshot,
                          root_device_name="/dev/sda",
                          description="bfebs",
                          windows=False,
                          bdmdev=None,
                          name=None,
                          ramdisk=None,
                          kernel=None,
                          dot=True,
                          block_device_map=None):
        """Convience function for passing a snapshot instead of its id. See register_snapshot_by_id
        :param snapshot: Snapshot object to use as an image
        :param root_device_name: root device name to use when registering
        :param description: Description of image that will be registered
        :param windows: Is the image a Windows image
        :param bdmdev: Block device mapping
        :param name: Name to register the image as
        :param ramdisk: Ramdisk ID to use
        :param kernel: Kernel ID to use
        :param dot: Delete on terminate flag
        :param block_device_map: existing block device map to append snapshot block dev to
        """
        return self.register_snapshot_by_id( snap_id=snapshot.id,
                                             root_device_name=root_device_name,
                                             description=description,
                                             windows=windows,
                                             bdmdev=bdmdev,
                                             name=name,
                                             ramdisk=ramdisk,
                                             kernel=kernel,
                                             dot=dot,
                                             block_device_map=block_device_map)
    
    @Eutester.printinfo
    def register_snapshot_by_id( self,
                                 snap_id,
                                 root_device_name="/dev/sda1",
                                 description="bfebs",
                                 windows=False,
                                 bdmdev=None,
                                 name=None,
                                 ramdisk=None,
                                 kernel=None,
                                 size=None,
                                 dot=True,
                                 block_device_map=None,
                                 custom_params=None):
        """
        Register an image snapshot

        :param snap_id: snapshot id
        :param root_device_name: root-device-name for image
        :param description: description of image to be registered
        :param windows: Is windows image boolean
        :param bdmdev: block-device-mapping device for image
        :param name: name of image to be registered
        :param ramdisk: ramdisk id
        :param kernel: kernel id (note for windows this name should be "windows")
        :param dot: Delete On Terminate boolean
        :param block_device_map: existing block device map to add the snapshot block dev type to
        :return: emi id of registered image
        """
        custom_params = custom_params or {}
        if bdmdev is None:
            bdmdev=root_device_name
        if name is None:
            name="bfebs_"+ snap_id
        if windows:
            custom_params['Platform'] = "windows"
            
        bdmap = block_device_map or BlockDeviceMapping()
        block_dev_type = BlockDeviceType()
        block_dev_type.snapshot_id = snap_id
        block_dev_type.delete_on_termination = dot
        block_dev_type.size = size
        bdmap[bdmdev] = block_dev_type
            
        self.debug("Register image with: snap_id:"+str(snap_id)+", root_device_name:"+str(root_device_name)+", desc:"+str(description)+
                   ", windows:"+str(windows)+", bdname:"+str(bdmdev)+", name:"+str(name)+", ramdisk:"+
                   str(ramdisk)+", kernel:"+str(kernel))
        image_id = self._register_image_custom_params(name=name, description=description, kernel_id=kernel, ramdisk_id=ramdisk,
                                           block_device_map=bdmap, root_device_name=root_device_name, **custom_params)
        self.debug("Image now registered as " + image_id)
        return image_id


    @Eutester.printinfo
    def register_image( self,
                        image_location,
                        root_device_name=None,
                        description=None,
                        architecture=None,
                        virtualization_type=None,
                        platform=None,
                        bdmdev=None,
                        name=None,
                        ramdisk=None,
                        kernel=None,
                        custom_params=None):
        """
        Register an image based on the s3 stored manifest location

        :param image_location:
        :param root_device_name: root-device-name for image
        :param description: description of image to be registered
        :param bdmdev: block-device-mapping object for image
        :param name: name of image to be registered
        :param ramdisk: ramdisk id
        :param kernel: kernel id (note for windows this name should be "windows")
        :return: image id string
        """
        custom_params = custom_params or {}
        if platform:
             custom_params['Platform']= platform
        #Check to see if boto is recent enough to have this param...
        image_id = self._register_image_custom_params(name=name,
                                                      description=description,
                                                      kernel_id=kernel,
                                                      image_location=image_location,
                                                      ramdisk_id=ramdisk,
                                                      architecture=architecture,
                                                      virtualization_type=virtualization_type,
                                                      block_device_map=bdmdev,
                                                      root_device_name=root_device_name,
                                                      **custom_params)
        self.test_resources["images"].append(self.ec2.get_all_images([image_id])[0])
        return image_id

    def delete_image(self, image, timeout=60):
        """
        Delete image by multiple deregistrations.

        :param timeout: int seconds to wait before failing operation
        :param image: boto image object to deregister
        :param delete: boolean, if True will attempt to deregister until removed/deleted, default:False
        """
        return self.deregister_image( image )

    def deregister_image(self, image):
        """
        Deregister an image.

        :param image: boto image object to deregister
        """
        gotimage = image
        self.debug("Deregistering image: " + str(image))
        try:
            gotimage = self.ec2.get_all_images(image_ids=[image.id])[0]
        except IndexError, ie:
            raise Exception("deregister_image:" + str(image.id) + ", No image found in get_all_images.Error: ")
        except Exception, e:
            #should return [] if not found, exception indicates an error with the command maybe?
            tb = self.get_traceback()
            raise Exception(
                'deregister_image: Error attempting to get image:' + str(image.id) + ", err:" + str(tb) + '\n' + str(e))
        self.ec2.deregister_image(image.id)
        try:
            # make sure the image was removed (should throw an exception),if not make sure it is in the deregistered state
            # if it is still associated with a running instance'
            gotimage = self.ec2.get_all_images(image_ids=[image.id])[0]
            # this will not be executed if image was removed
            if( gotimage.state != 'deregistered') :
                raise Exception('deregister_image: Error attempting to deregister image:' + str(image.id)  + '\n')
        except IndexError, ie:
            pass


    @Eutester.printinfo
    def get_images(self,
                   emi=None,
                   name=None,
                   root_device_type=None,
                   root_device_name=None,
                   virtualization_type=None,
                   location=None,
                   state="available",
                   arch=None,
                   owner_id=None,
                   filters=None,
                   basic_image=None,
                   platform=None,
                   not_platform=None,
                   tagkey=None,
                   tagvalue=None,
                   max_count=None,
                   _args_dict=None):
        """
        Get a list of images which match the provided criteria.

        :param emi: Partial ID of the emi to return, defaults to the 'emi-" prefix to grab any
        :param root_device_type: example: 'instance-store' or 'ebs'
        :param root_device_name: example: '/dev/sdb'
        :param virtualization_type: example: 'hvm' or 'paravirtualized'
        :param location: partial on location match example: 'centos'
        :param state: example: 'available'
        :param arch: example: 'x86_64'
        :param owner_id: owners numeric id
        :param filters: standard filters
        :param basic_image: boolean, avoids returning windows, load balancer and service images
        :param not_platform: skip if platform string matches this string. Example: not_platform='windows'
        :param max_count: return after finding 'max_count' number of matching images
        :param _args_dict: dict which can be populated by annotation to give
                            insight into the args/kwargs this was called with
        :return: image id
        :raise: Exception if image is not found
        """

        ret_list = []
        if not filters:
            filters = {}
            if emi:
                filters['image-id'] = emi
            if name:
                filters['name'] = name
            if root_device_type:
                filters['root-device-type'] = root_device_type
            if root_device_name:
                filters['root-device-name'] = root_device_name
            if state:
                filters['state'] = state
            if virtualization_type:
                filters['virtualization-type'] = virtualization_type
            if arch:
                filters['architecture'] = arch
            if owner_id:
                filters['owner-id'] = owner_id
            if platform:
                filters['platform'] = platform
            if tagkey:
                filters['tag-key'] = tagkey
            if tagvalue:
                filters['tag-value'] = tagvalue

        # if emi is None and not platform:
        if basic_image is None and not _args_dict:
            # If a specific EMI was not provided, set some sane defaults for
            # fetching a test image to work with...
            basic_image = True
        if name is None:
             emi = "mi-"

        images = self.ec2.get_all_images(filters=filters)
        self.debug("Got " + str(len(images)) + " total images " + str(emi) + ", now filtering..." )
        for image in images:
            if (re.search(emi, image.id) is None) and (re.search(emi, image.name) is None):
                continue
            if (root_device_type is not None) and (image.root_device_type != root_device_type):
                continue
            if (virtualization_type is not None):
                if hasattr(image, 'virtualization_type'):
                    if image.virtualization_type != virtualization_type:
                        continue
                else:
                    self.debug('Filter by virtualization type requested but not supported in this boto version?')
            if (root_device_name is not None) and (image.root_device_name != root_device_name):
                continue       
            if (state is not None) and (image.state != state):
                continue            
            if (location is not None) and (not re.search( location, image.location)):
                continue
            if (name is not None) and (image.name != name):
                continue
            if (arch is not None) and (image.architecture != arch):
                continue
            if (owner_id is not None) and (image.owner_id != owner_id):
                continue
            if basic_image:
                not_location = ["windows", "imaging-worker", "loadbalancer"]
                skip = False
                for loc in not_location:
                    if (re.search( str(loc), image.location)):
                        skip = True
                        break
                if skip:
                    continue
            if (not_platform is not None) and (image.platform == not_platform):
                continue
            self.debug("Returning image:"+str(image.id))
            ret_list.append(image)
            if max_count and len(ret_list) >= max_count:
                return ret_list
        if not ret_list:
            raise ResourceNotFoundException("Unable to find an EMI")
        return ret_list


    @Eutester.printinfo
    def get_emi(self,
                   emi=None,
                   name=None,
                   root_device_type=None,
                   root_device_name=None,
                   location=None,
                   state="available",
                   arch=None,
                   owner_id=None,
                   filters=None,
                   basic_image=None,
                   platform=None,
                   not_platform=None,
                   tagkey=None,
                   tagvalue=None,
                   _args_dict=None,
                   ):
        """
        Get an emi with name emi, or just grab any emi in the system. Additional 'optional' match criteria can be defined.

        :param emi: Partial ID of the emi to return, defaults to the 'emi-" prefix to grab any
        :param root_device_type: example: 'instance-store' or 'ebs'
        :param root_device_name: example: '/dev/sdb'
        :param location: partial on location match example: 'centos'
        :param state: example: 'available'
        :param arch: example: 'x86_64'
        :param owner_id: owners numeric id
        :param filters: standard filters, dict.
        :param basic_image: boolean, avoids returning windows, load balancer and service images
        :param not_platform: skip if platform string matches this string. Example: not_platform='windows'
        :param _args_dict: dict which can be populated by annotation to give
                            insight into the args/kwargs this was called with
        :return: image id
        :raise: Exception if image is not found
        """
        # If no criteria was provided for filter an image, use 'basic_image'
        # flag to provide some sane defaults
        if basic_image is None and not _args_dict:
            basic_image = True
        else:
            basic_image = False
        if filters is None and emi is None and \
                        name is None and location is None:
            # Attempt to get a eutester created image if it happens to meet
            # the other criteria provided. Otherwise remove filter and
            # return the image found without the imposed filters.
            filters={'tag-key':'eutester-created'}
            try:
                return self.get_images(emi=emi,
                                   name=name,
                                   root_device_type=root_device_type,
                                   root_device_name=root_device_name,
                                   location=location,
                                   state=state,
                                   arch=arch,
                                   owner_id=owner_id,
                                   filters=filters,
                                   basic_image=basic_image,
                                   platform=platform,
                                   not_platform=not_platform,
                                   tagkey=tagkey,
                                   tagvalue=tagvalue,
                                   max_count=1)[0]
            except:
                filters = None
        return self.get_images(emi=emi,
                               name=name,
                               root_device_type=root_device_type,
                               root_device_name=root_device_name,
                               location=location,
                               state=state,
                               arch=arch,
                               owner_id=owner_id,
                               filters=filters,
                               basic_image=basic_image,
                               platform=platform,
                               not_platform=not_platform,
                               tagkey=tagkey,
                               tagvalue=tagvalue,
                               max_count=1)[0]


    
    def get_all_allocated_addresses(self,account_id=None):
        """
        Return all allocated addresses for a given account_id as boto.ec2.address objects

        :param account_id: account number to filter on
        :return: list of boto.ec2.address objects
        """
        self.debug("get_all_allocated_addresses...")
        account_id = account_id or self.get_account_id()
        ret = []
        if account_id:
            account_id = str(account_id)
            addrs = self.ec2.get_all_addresses()
            for addr in addrs:
                if addr.instance_id and re.search(account_id, str(addr.instance_id)):
                    ret.append(addr)
        return ret
    
    def get_available_addresses(self):
        """
        Get all available addresses

        :return: a list of all available boto.ec2.address
        """
        self.debug("get_available_addresses...")
        ret = []
        addrs = self.ec2.get_all_addresses()
        for addr in addrs:
            if addr.instance_id and re.search(r"(available|nobody)", addr.instance_id):
                ret.append(addr)
        return ret


    def show_all_addresses_verbose(self, display=True):
        """
        Print table to debug output showing all addresses available to cloud admin using verbose filter
        """
        address_width = 20
        info_width = 64
        account_width = 24
        buf = ""
        line = ""
        header = "| " + str("PUBLIC IP").ljust(address_width) + " | " + str("ADDRESS INFO").ljust(info_width) + \
                 " | " + str("ACCOUNT NAME").ljust(account_width) + " | " + str("REGION") + "\n"
        longest = len(header)
        try:
            ad_list = self.ec2.get_all_addresses(addresses='verbose')
            for ad in ad_list:
                account_name = ""
                adline = ""
                match = re.findall('\(arn:*.*\)', ad.instance_id)
                if match:
                    try:
                        match = match[0]
                        account_id = match.split(':')[4]
                        account_name = self.get_all_accounts(account_id=account_id)[0]['account_name']
                    except:pass
                if ad.region:
                    region = ad.region.name
                adline = "| " + str(ad.public_ip ).ljust(address_width) + " | " + str(ad.instance_id).ljust(info_width) + \
                       " | " + str(account_name).ljust(account_width)  + " | " + str(region) + "\n"
                buf += adline
                if len(adline) > longest:
                    longest = len(adline)
        except Exception, e:
            tb = self.get_traceback()
            buf = str(tb) + "\n ERROR in show_all_addresses_verbose:" + str(e)
        for x in xrange(0,longest):
            line += "-"
        line += "\n"
        buf = "\n" + line + header + line + buf + line
        if not display:
            return buf
        self.debug(buf)


    def allocate_address(self):
        """
        Allocate an address for the current user

        :return: boto.ec2.address object allocated
        """
        try:
            self.debug("Allocating an address")
            address = self.ec2.allocate_address()
        except Exception, e:
            tb = self.get_traceback()
            err_msg = 'Unable to allocate address'
            self.critical(str(err_msg))
            raise Exception(str(tb) + "\n" + str(err_msg))
        self.debug("Allocated " + str(address))
        return address

    def associate_address(self,instance, address, refresh_ssh=True, timeout=75):
        """
        Associate an address object with an instance

        :param instance: instance object to associate ip with
        :param address: address to associate to instance
        :param timeout: Time in seconds to wait for operation to complete
        :raise: Exception in case of association failure
        """
        ip =  str(address.public_ip)
        old_ip = str(instance.ip_address)
        self.debug("Attemtping to associate " + str(ip) + " with " + str(instance.id))
        try:
            address.associate(instance.id)
        except Exception, e:
            self.critical("Unable to associate address "+str(ip)+" with instance:"+str(instance.id)+"\n")
            raise e
        
        start = time.time()
        elapsed = 0
        address = self.ec2.get_all_addresses(addresses=[ip])[0] 
        ### Ensure address object holds correct instance value
        while not address.instance_id:
            if elapsed > timeout:
                raise Exception('Address ' + str(ip) + ' never associated with instance')
            self.debug('Address {0} not attached to {1} but rather {2}'.format(str(address), instance.id, address.instance_id))
            self.sleep(5)
            address = self.ec2.get_all_addresses(addresses=[ip])[0]
            elapsed = int(time.time()-start)

        poll_count = 15
        ### Ensure instance gets correct address
        while instance.ip_address not in address.public_ip:
            if elapsed > timeout:
                raise Exception('Address ' + str(address) + ' did not associate with instance after:'+str(elapsed)+" seconds")
            self.debug('Instance {0} has IP {1} attached instead of {2}'.format(instance.id, instance.ip_address, address.public_ip) )
            self.sleep(5)
            instance.update()
            elapsed = int(time.time()-start)
            self.debug("Associated IP successfully old_ip:"+str(old_ip)+' new_ip:'+str(instance.ip_address))
        if refresh_ssh:
            if isinstance(instance, EuInstance) or isinstance(instance, WinInstance):
                self.sleep(5)
                instance.update()
                self.debug('Refreshing EuInstance:'+str(instance.id)+' ssh connection to associated addr:'+str(instance.ip_address))
                instance.reset_ssh_connection()
            else:
                self.debug('WARNING: associate_address called with refresh_ssh set to true, but instance is not EuInstance type:'+str(instance.id))

    def disassociate_address_from_instance(self, instance, timeout=75):
        """
        Disassociate address from instance and ensure that it no longer holds the IP

        :param instance: An instance that has an IP allocated
        :param timeout: Time in seconds to wait for address to disassociate
        :raise:
        """
        self.debug("disassociate_address_from_instance: instance.ip_address:" +
                   str(instance.ip_address) + " instance:" + str(instance))
        ip=str(instance.ip_address)
        address = self.ec2.get_all_addresses(addresses=[instance.ip_address])[0]
        
        
        start = time.time()
        elapsed = 0
      
        address = self.ec2.get_all_addresses(addresses=[address.public_ip])[0]
        ### Ensure address object hold correct instance value
        while address.instance_id and not re.match(instance.id, str(address.instance_id)):
            self.debug('Address {0} not attached to Instance "{1}" but rather Instance "{2}" after {3} seconds'.format(str(address), instance.id, address.instance_id, str(elapsed)) )
            if elapsed > timeout:
                raise Exception('Address ' + str(address) + ' never associated with instance after '+str(elapsed)+' seconds')
            address = self.ec2.get_all_addresses(addresses=[address.public_ip])[0]
            self.sleep(5)
            elapsed = int(time.time()-start)
            
        
        self.debug("Attemtping to disassociate " + str(address) + " from " + str(instance.id))
        address.disassociate()
        
        start = time.time()
        ### Ensure instance gets correct address
        ### When private addressing is enabled the pub address should be equal to the priv address
        ### Otherwise we want to the pub address to be anything but its current and not the priv address
        while (not instance.private_addressing and instance.ip_address != address.public_ip and instance.ip_address != address.private_ip_address) or \
                (instance.private_addressing and instance.ip_address == instance.private_ip_address):
            self.debug('Instance {0} has IP "{1}" still using address "{2}" after {3} seconds'.format(instance.id, instance.ip_address, address.public_ip, str(elapsed)) )
            if elapsed > timeout:
                raise Exception('Address ' + str(address) + ' never disassociated with instance after '+str(elapsed)+' seconds')
            instance.update()
            self.sleep(5)
            elapsed = int(time.time()-start)
            address = self.ec2.get_all_addresses(addresses=[address.public_ip])[0]
        self.debug("Disassociated IP successfully")

    def release_address(self, address):
        """
        Release all addresses or a particular IP

        :param address: Address object to release
        :raise: Exception when the address does not release
        """
        try:
            self.debug("Releasing address: " + str(address))
            address.release()
        except Exception, e:
            raise Exception("Failed to release the address: " + str(address) + ": " +  str(e))


    def check_device(self, device_path):
        """
        Used with instance connections. Checks if a device at a certain path exists

        :param device_path: Path to check
        :return: bool, if device was found
        """
        return self.found("ls -1 " + device_path, device_path)

    @Eutester.printinfo
    def get_volumes(self, 
                    volume_id="vol-", 
                    status=None, 
                    attached_instance=None, 
                    attached_dev=None, 
                    snapid=None, 
                    zone=None,
                    filters=None,
                    minsize=1, 
                    maxsize=None,
                    md5=None, 
                    eof=False):
        """
        Return list of volumes that matches the criteria. Criteria options to be matched:

        :param volume_id: string present within volume id
        :param status: examples: 'in-use', 'creating', 'available'
        :param attached_instance: instance id example 'i-1234abcd'
        :param attached_dev: example '/dev/sdf'
        :param snapid: snapshot volume was created from example 'snap-1234abcd'
        :param zone: zone of volume example 'PARTI00'
        :param minsize: minimum size of volume to be matched
        :param maxsize: maximum size of volume to be matched
        :param eof: exception on failure to find volume, else returns empty list
        :return: List of volumes matching the filters provided
        :raise:
        """
        retlist = []
        if (attached_instance is not None) or (attached_dev is not None):
            status='in-use'
        volumes = self.ec2.get_all_volumes(filters=filters)
        for volume in volumes:
            if not hasattr(volume,'md5'):
                volume = EuVolume.make_euvol_from_vol(volume, tester=self)
            if not re.match(volume_id, volume.id):
                continue
            if (snapid is not None) and (volume.snapshot_id != snapid):
                continue
            if (zone is not None) and (volume.zone != zone):
                continue
            if (status is not None) and (volume.status != status):
                continue
            if (md5 is not None) and hasattr(volume,'md5') and (volume.md5 != md5):
                continue
            if volume.attach_data is not None:
                if (attached_instance is not None) and ( volume.attach_data.instance_id != attached_instance):
                    continue
                if (attached_dev is not None) and (volume.attach_data.device != attached_dev):
                    continue
            if volume.size <  minsize:
                continue
            if maxsize is not None and volume.size > maxsize:
                continue
            if not hasattr(volume,'md5'):
                volume = EuVolume.make_euvol_from_vol(volume)
            retlist.append(volume)
        if eof and retlist == []:
            raise ResourceNotFoundException("Unable to find matching volume")
        else:
            return retlist

  
    def get_volume(self,
                   volume_id="vol-",
                   status=None,
                   attached_instance=None,
                   attached_dev=None,
                   snapid=None,
                   zone=None,
                   minsize=1,
                   maxsize=None,
                   eof=True):
        """
        Return first volume that matches the criteria.

        :param volume_id: string present within volume id
        :param status: examples: 'in-use', 'creating', 'available'
        :param attached_instance: instance id example 'i-1234abcd'
        :param attached_dev: example '/dev/sdf'
        :param snapid: snapshot volume was created from example 'snap-1234abcd'
        :param zone: zone of volume example 'PARTI00'
        :param minsize: minimum size of volume to be matched
        :param maxsize: maximum size of volume to be matched
        :param eof: exception on failure to find volume, else returns None
        :return: List of volumes matching the filters provided
        :raise:
        """
        vol = None
        try:
            vol = self.get_volumes(volume_id=volume_id, status=status, attached_instance=attached_instance,
                                   attached_dev=attached_dev, snapid=snapid, zone=zone, minsize=minsize,
                                   maxsize=maxsize, eof=eof)[0]

        except Exception, e:
            if eof:
                raise e
        return vol

    @Eutester.printinfo
    def run_instance(self,
                     image=None,
                     keypair=None,
                     group="default",
                     name=None,
                     type=None,
                     zone=None,
                     min=1,
                     max=1,
                     user_data=None,
                     private_addressing=False,
                     username="root",
                     password=None,
                     is_reachable=True,
                     monitoring_enabled=False,
                     timeout=600):
        """
        Run instance/s and wait for them to go to the running state

        :param image: Image object to use, default is pick the first emi found in the system
        :param keypair: Keypair name to use for the instances, defaults to none
        :param group: Security group name to apply to this set of instnaces, defaults to none
        :param type: VM type to use for these instances, defaults to m1.small
        :param zone: Availability zone to run these instances
        :param min: Minimum instnaces to launch, default 1
        :param max: Maxiumum instances to launch, default 1
        :param user_data: User-data string to pass to instance
        :param private_addressing: Runs an instance with only private IP address
        :param username: username to use when connecting via ssh
        :param password: password to use when connecting via ssh
        :param is_reachable: Instance can be reached on its public IP (Default=True)
        :param timeout: Time in seconds for instance to enter running state
        :return: Reservation object
        :raise:
        """
        if image is None:
            image = self.get_emi()
        if not isinstance(image, Image):
            image = self.get_emi(emi=str(image))
        if image is None:
            raise Exception("emi is None. run_instance could not auto find an emi?")
        if not user_data:
            user_data = self.enable_root_user_data
        if private_addressing is True:
            addressing_type = "private"
            is_reachable= False
        else:
            addressing_type = None
        #In the case a keypair object was passed instead of the keypair name
        if keypair:
            if isinstance(keypair, KeyPair):
                keypair = keypair.name

        if monitoring_enabled :
            enabled=True
        else:
            enabled=False
        start = time.time()
        
        self.debug( "Attempting to run "+ str(image.root_device_type)  +" image " + str(image) + " in group " + str(group))
        reservation = image.run(key_name=keypair,security_groups=[group],instance_type=type, placement=zone,
                                min_count=min, max_count=max, user_data=user_data, addressing_type=addressing_type,
                                monitoring_enabled=enabled)
        self.test_resources["reservations"].append(reservation)
        
        if (len(reservation.instances) < min) or (len(reservation.instances) > max):
            fail = "Reservation:"+str(reservation.id)+" returned "+str(len(reservation.instances))+\
                   " instances, not within min("+str(min)+") and max("+str(max)+")"
        
        try:
            self.wait_for_reservation(reservation,timeout=timeout)
        except Exception, e:
            self.debug(self.get_traceback())
            self.critical("An instance did not enter proper running state in " + str(reservation) )
            self.critical("Terminatng instances in " + str(reservation))
            self.terminate_instances(reservation)
            raise Exception("Instances in " + str(reservation) + " did not enter proper state")
        
        for instance in reservation.instances:
            if instance.state != "running":
                self.critical("Instance " + instance.id + " now in " + instance.state  + " state  in zone: "  + instance.placement )
            else:
                self.debug( "Instance " + instance.id + " now in " + instance.state  + " state  in zone: "  + instance.placement )
            #    
            # check to see if public and private DNS names and IP addresses are the same
            #
            if (instance.ip_address == instance.private_ip_address) or \
                    (instance.ip_address == instance.private_ip_address) and \
                    ( private_addressing is False ):
                self.debug(str(instance) + " got Public IP: " + str(instance.ip_address)  + " Private IP: " +
                           str(instance.private_ip_address) + " Public DNS Name: " + str(instance.public_dns_name) +
                           " Private DNS Name: " + str(instance.private_dns_name))
                self.critical("Instance " + instance.id + " has he same public and private IPs of " + str(instance.ip_address))
            else:
                self.debug(str(instance) + " got Public IP: " + str(instance.ip_address)  + " Private IP: " +
                           str(instance.private_ip_address) + " Public DNS Name: " + str(instance.public_dns_name) +
                           " Private DNS Name: " + str(instance.private_dns_name))

            if not private_addressing:
                try:
                    self.wait_for_valid_ip(instance)
                except Exception, e:
                    tb = self.get_traceback()
                    ip_err = str(tb)  + "\nWARNING in wait_for_valid_ip: "+str(e)
                    self.debug(ip_err)
                    self.terminate_instances(reservation)
                    raise Exception("Reservation " +  str(reservation) + " has been terminated because instance " +
                                    str(instance) + " did not receive a valid IP")

            if is_reachable:
                self.ping(instance.ip_address, 20)

        ## Add name tag
        if name:
            self.create_tags([reservation.instances], {"Name:": name})
                
        #calculate remaining time to wait for establishing an ssh session/euinstance     
        timeout -= int(time.time() - start)
        #if we can establish an SSH session convert the instances to the test class euinstance for access to instance specific test methods
        if is_reachable:
            self.debug("Converting " + str(reservation) + " into euinstances")
            return self.convert_reservation_to_euinstance(reservation, username=username, password=password, private_addressing=private_addressing,
                                                          keyname=keypair, timeout=timeout)
        else:
            return reservation
        
    @Eutester.printinfo
    def run_image(self, 
                  image=None, 
                  keypair=None, 
                  group="default", 
                  type=None, 
                  zone=None, 
                  min=1, 
                  max=1,
                  block_device_map=None,
                  user_data=None,
                  private_addressing=False, 
                  username="root", 
                  password=None,
                  auto_connect=True,
                  clean_on_fail=True,
                  monitor_to_running = True,
                  timeout=480):
        """

        :param image: image object or string image_id to create instances with
        :param keypair: keypair to create instances with
        :param group: security group to run instances in
        :param type: vmtype to run instances as
        :param zone: availability zone (aka cluster, aka parition) to run instances in
        :param min: minimum amount of instances to try to run
        :param max: max amount of instances to try to run
        :param user_data: user_data to run instances with
        :param private_addressing: boolean to run instances without public ips
        :param username: username for connecting ssh to instances
        :param password: password for connnecting ssh to instances
        :param auto_connect: boolean flag whether or not ssh connections should be automatically attempted
        :param clean_on_fail: boolean flag whether or not to attempt to delete/remove failed instances-(not implemented)
        :param monitor_to_running: boolean flag whether or not to monitor instances to a running state
        :pararm block_device_map: block device map obj
        :param timeout: time allowed before failing this operation
        :return: list of euinstances
        """
        reservation = None
        try:
            instances = []
            if image is None:
                images = self.ec2.get_all_images()
                for emi in images:
                    if re.match("emi",emi.id):
                        image = emi      
            if not isinstance(image, Image):
                image = self.get_emi(emi=str(image))
            if image is None:
                raise Exception("emi is None. run_instance could not auto find an emi?")
            if not user_data:
                user_data = self.enable_root_user_data
            if private_addressing is True:
                addressing_type = "private"
                connect = False
            else:
                addressing_type = None
            #In the case a keypair object was passed instead of the keypair name
            if keypair:
                if isinstance(keypair, KeyPair):
                    keypair = keypair.name
            self.debug('Euinstance list prior to running image...')
            try:
                self.print_euinstance_list()
            except Exception, e:
                self.debug('Failed to print euinstance list before running image, err:' +str(e))
            #self.debug( "Attempting to run "+ str(image.root_device_type)  +" image " + str(image) + " in group " + str(group))
            cmdstart=time.time()
            reservation = image.run(key_name=keypair,security_groups=[group],instance_type=type, placement=zone,
                                    min_count=min, max_count=max, user_data=user_data, addressing_type=addressing_type,
                                    block_device_map=block_device_map)
            self.test_resources["reservations"].append(reservation)
            
            if (len(reservation.instances) < min) or (len(reservation.instances) > max):
                fail = "Reservation:"+str(reservation.id)+" returned "+str(len(reservation.instances))+\
                       " instances, not within min("+str(min)+") and max("+str(max)+")"
            
            if image.root_device_type == 'ebs':
                self.wait_for_instances_block_dev_mapping(reservation.instances, timeout=timeout)
            for instance in reservation.instances:
                try:
                    self.debug(str(instance.id)+':Converting instance to euinstance type.')
                    #convert to euinstances, connect ssh later...
                    if image.platform == 'windows':
                        eu_instance = WinInstance.make_euinstance_from_instance( instance,
                                                                                 self,
                                                                                 keypair=keypair,
                                                                                 username='Administrator',
                                                                                 password=password,
                                                                                 reservation=reservation,
                                                                                 private_addressing=private_addressing,
                                                                                 timeout=timeout,
                                                                                 cmdstart=cmdstart,
                                                                                 auto_connect=False
                                                                                 )

                    else:
                        eu_instance =  EuInstance.make_euinstance_from_instance( instance,
                                                                                 self,
                                                                                 keypair=keypair,
                                                                                 username = username,
                                                                                 password=password,
                                                                                 reservation = reservation,
                                                                                 private_addressing=private_addressing,
                                                                                 timeout=timeout,
                                                                                 cmdstart=cmdstart,
                                                                                 auto_connect=False )
                    #set the connect flag in the euinstance object for future use
                    eu_instance.auto_connect = auto_connect
                    instances.append(eu_instance)
                except Exception, e:
                    self.debug(self.get_traceback())
                    raise Exception("Unable to create Euinstance from " + str(instance)+", err:\n"+str(e))
            if monitor_to_running:
                return self.monitor_euinstances_to_running(instances, timeout=timeout)
            else:
                return instances
        except Exception, e:
            trace = self.get_traceback()
            self.debug('!!! Run_instance failed, terminating reservation. Error:'+str(e)+"\n"+trace)
            if reservation and clean_on_fail:
                self.terminate_instances(reservation=reservation)
            raise e 
    
    
    def wait_for_instances_block_dev_mapping(self, instances, poll_interval=1, timeout=60):
        waiting = copy.copy(instances)
        elapsed = 0
        good = []
        failed = []
        start = time.time()
        self.debug('wait_for_instance_block_dev_mapping started...')
        while waiting and (elapsed < timeout):
            elapsed = time.time() - start
            for instance in waiting:
                instance.update()
                for failed_state in ['terminated', 'stopped','stopping']:
                    if instance.state == failed_state:
                        failed.append(instance)
                        if instance in waiting:
                            waiting.remove(instance)
                if instance.root_device_type == 'ebs':
                    if instance.block_device_mapping and instance.block_device_mapping.current_value:
                        self.debug('Instance block device mapping is populated:'+str(instance.id))
                        self.update_resources_with_volumes_from_instance_block_device_mapping(instance)
                        good.append(instance)
                else:
                    good.append(instance)
                    self.print_block_device_map(instance.block_device_mapping)
            for instance in good:
                if instance in waiting:
                    waiting.remove(instance)
            if waiting:
                if not int(elapsed)%10:
                    for instance in waiting:
                        self.debug('Waiting for instance block device mapping to be populated:'+str(instance.id))
                time.sleep(poll_interval)
        failed.extend(waiting)
        if failed:
            err_buf = 'Instances failed to populate block dev mapping after '+str(elapsed)+'/'+str(timeout)+' seconds: '
            for instance in failed:
                err_buf += str(instance.id)+', current state:'+str(instance.state)+', '
            raise Exception(err_buf)
        self.debug('wait_for_instance_block_dev_mapping done. elapsed:'+str(elapsed))


    def update_resources_with_volumes_from_instance_block_device_mapping(self, instance):
        for device_name in instance.block_device_mapping:
            device = instance.block_device_mapping.get(device_name)
            if device.volume_id:
                try:
                    volume = self.get_volume(volume_id=device.volume_id)
                    if not volume in self.test_resources['volumes']:
                        self.test_resources['volumes'].append(volume)
                except Exception, e:
                    tb = self.get_traceback()
                    self.debug("\n" + str(tb) + "\nError trying to retrieve volume:" + str(device.volume_id) +
                               ' from instance:' + str(instance.id) + " block dev map, err:" + str(e))


    @Eutester.printinfo 
    def monitor_euinstances_to_running(self,instances, poll_interval=10, timeout=480):
        if not isinstance(instances, types.ListType):
            instances = [instances]
        self.debug("("+str(len(instances))+") Monitor_instances_to_running starting...")
        ip_err = ""
        #Wait for instances to go to running state...
        self.monitor_euinstances_to_state(instances, failstates=['terminated','shutting-down'],timeout=timeout)
        #Wait for instances in list to get valid ips, check for duplicates, etc...
        try:
            self.wait_for_valid_ip(instances, timeout=timeout)
        except Exception, e:
            tb = self.get_traceback()
            ip_err = str(tb)  + "\nWARNING in wait_for_valid_ip: "+str(e)
            self.debug(ip_err)
        #Now attempt to connect to instances if connect flag is set in the instance...
        waiting = copy.copy(instances)
        good = []
        elapsed = 0
        start = time.time()
        self.debug("Instances in running state and wait_for_valid_ip complete, attempting connections...")
        while waiting and (elapsed < timeout):
            self.debug("Checking "+str(len(waiting))+" instance ssh connections...")
            elapsed = int(time.time()-start)
            for instance in waiting:
                self.debug('Checking instance:'+str(instance.id)+" ...")
                if instance.auto_connect:
                    try:
                        if isinstance(instance, WinInstance):
                            #First try checking the RDP and WINRM ports for access...
                            self.debug('Do Security group rules allow winrm from this test machine:'+
                                       str(self.does_instance_sec_group_allow(instance, protocol='tcp', port=instance.winrm_port)))
                            self.debug('Do Security group rules allow winrm from this test machine:'+
                                       str(self.does_instance_sec_group_allow(instance, protocol='tcp', port=instance.rdp_port)))
                            instance.poll_for_ports_status(timeout=1)
                            instance.connect_to_instance(timeout=15)
                            self.debug("Connected to instance:"+str(instance.id))
                            good.append(instance)
                        else:
                            #First try ping
                            self.debug('Do Security group rules allow ping from this test machine:'+
                                       str(self.does_instance_sec_group_allow(instance, protocol='icmp', port=0)))
                            self.ping(instance.ip_address, 2)
                            #now try to connect ssh or winrm
                            allow = "None"
                            try:
                                allow=str(self.does_instance_sec_group_allow(instance, protocol='tcp', port=22))
                            except:
                                pass
                            self.debug('Do Security group rules allow ssh from this test machine:'+str(allow))
                            instance.connect_to_instance(timeout=15)
                            self.debug("Connected to instance:"+str(instance.id))
                            good.append(instance)
                    except :
                        self.debug(self.get_traceback())
                        pass
                else:
                    good.append(instance)
            for instance in good:
                if instance in waiting:
                    waiting.remove(instance)
            if waiting:
                time.sleep(poll_interval)
                
        if waiting:
            buf = "Following Errors occurred while waiting for instances:\n"
            buf += 'Errors while waiting for valid ip:'+ ip_err + "\n"
            buf += "Timed out waiting:" + str(elapsed) + " to connect to the following instances:\n"
            for instance in waiting:
                buf += str(instance.id)+":"+str(instance.ip_address)+","
            raise Exception(buf)
        self.print_euinstance_list(good)
        return good
    
    
    @Eutester.printinfo
    def does_instance_sec_group_allow(self, instance, src_addr=None, protocol='tcp',port=22):
        s = None
        #self.debug("does_instance_sec_group_allow:"+str(instance.id)+" src_addr:"+str(src_addr))
        try:
            if not src_addr:
                #Use the local test machine's addr
                if not self.ec2_source_ip:
                    #Try to get the outgoing addr used to connect to this instance
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                    s.connect((instance.ip_address,1))
                    #set the tester's global source_ip, assuming it can re-used (at least until another method sets it to None again)
                    self.ec2_source_ip = s.getsockname()[0]
                if self.ec2_source_ip == "0.0.0.0":
                    raise Exception('Test machine source ip detected:'+str(self.ec2_source_ip)+', tester may need ec2_source_ip set manually')
                src_addr = self.ec2_source_ip
            
            self.debug('Using src_addr:'+str(src_addr))
            groups = self.get_instance_security_groups(instance)
            for group in groups:
                if self.does_sec_group_allow(group, src_addr, protocol=protocol, port=port):
                    self.debug("Sec allows from test source addr: " +
                               str(src_addr + ", protocol:" + str(protocol) +
                               ", port:" + str(port)))
                    #Security group allows from the src/proto/port
                    return True
            #Security group does not allow from the src/proto/port
            return False
        except Exception, e:
            self.debug(self.get_traceback())
            raise e
        finally:
            if s:
                s.close()

    def get_security_group(self, id=None, name=None):
        #Adding this as both a convienence to the user to separate euare groups from security groups
        #Not sure if botos filter on group names and ids is reliable?
        if not id and not name:
            raise Exception('get_security_group needs either a name or an id')
        groups = self.ec2.get_all_security_groups(groupnames=[name], group_ids=id)
        for group in groups:
            if not id or (id and group.id == id):
                if not name or (name and group.name == name):
                    self.debug('Found matching security group for name:'+str(name)+' and id:'+str(id))
                    return group
        self.debug('No matching security group found for name:'+str(name)+' and id:'+str(id))
        return None
        
    @Eutester.printinfo                    
    def does_sec_group_allow(self, group, src, protocol='tcp', port=22):
        """
        Test whether a security group will allow traffic from a specific 'src' ip address to
        a specific 'port' using a specific 'protocol'
        :param group: Security group obj to use in lookup
        :param src: Source address to lookup against sec group rule(s)
        :param protocol: Protocol to lookup sec group rule against
        :param port: Network port to lookup sec group rule against
        """
        port = int(port)
        protocol = str(protocol).strip().lower()
        self.debug('Security group:' + str(group.name) + ", src ip:" +
                   str(src) + ", proto:" + str(protocol) + ", port:" +
                   str(port))
        group = self.get_security_group(id=group.id, name=group.name)
        for rule in group.rules:
            g_buf =""
            if str(rule.ip_protocol).strip().lower() == protocol:
                for grant in rule.grants:
                    g_buf += str(grant)+","
                self.debug("rule#" + str(group.rules.index(rule)) +
                           ": port:" + str(rule.to_port) +
                           ", grants:"+str(g_buf))
                to_port= int(rule.to_port)
                if (to_port == 0 ) or (to_port == -1) or (to_port == port):
                    for grant in rule.grants:
                        if self.is_address_in_network(src, str(grant)):
                            self.debug('sec_group DOES allow: group:"{0}"'
                                       ', src:"{1}", proto:"{2}", port:"{3}"'
                                       .format(group.name, src, protocol, port))
                            return True
        self.debug('sec_group DOES NOT allow: group:"{0}", src:"{1}", proto:'
                   '"{2}", port:"{3}"'.format(group.name, src, protocol, port))
        return False
                    
    @classmethod
    @Eutester.printinfo
    def is_address_in_network(cls,ip_addr, network):
        """

        :param ip_addr: Ip address ie: 192.168.1.5
        :param network: Ip network in cidr notation ie: 192.168.1.0/24
        :return: boolean true if ip is found to be in network/mask, else false
        """
        ip_addr = str(ip_addr)
        network = str(network)
        # Check for 0.0.0.0/0 network first...
        rem_zero = network.replace('0','')
        if not re.search('\d', rem_zero):
            return True
        ipaddr = int(''.join([ '%02x' % int(x) for x in ip_addr.split('.') ]), 16)
        netstr, bits = network.split('/')
        netaddr = int(''.join([ '%02x' % int(x) for x in netstr.split('.') ]), 16)
        mask = (0xffffffff << (32 - int(bits))) & 0xffffffff
        return (ipaddr & mask) == (netaddr & mask)
    
    def get_instance_security_groups(self,instance):
        """
        Definition: Look up and return all security groups this instance is referencing.

        :param instance: instance or euinstance object to
        :return:
        """
        secgroups = []
        if hasattr(instance, 'security_groups') and instance.security_groups:
            return instance.security_groups
        if hasattr(instance, 'reservation') and instance.reservation:
            res = instance.reservation
        else:
            res = self.get_reservation_for_instance(instance)
        for group in res.groups:
         secgroups.extend(self.ec2.get_all_security_groups(groupnames=str(group.id)))
        return secgroups
    
    def get_reservation_for_instance(self, instance):
        """
        Definition: Lookup and return reservation obj for this instance

        :param instance: boto instance or euinstance obj to use for lookup
        :return: :raise:
        """
        if hasattr(self.ec2, 'get_all_reservations'):
            res = self.ec2.get_all_reservations(instance_ids=instance.id)
            if res and isinstance(res, types.ListType):
                return res[0]
        for res in self.ec2.get_all_instances():
            for inst in res.instances:
                if inst.id == instance.id:
                    if hasattr(instance,'reservation'):
                        instance.reservation = res
                    return res
        raise Exception('No reservation found for instance:'+str(instance.id))
    
    @Eutester.printinfo    
    def monitor_euinstances_to_state(self,
                                     instance_list,
                                     state='running',
                                     min=None,
                                     poll_interval=10,
                                     failstates=[],
                                     timeout=120,
                                     eof=True):
        """

        :param instance_list: list of instances to monitor
        :param state: state to monitor to, expected state
        :param min: int min count of instances that need to succeed otherwise except out
        :param poll_interval: int number of seconds between polls for instance status
        :param timeout: time to wait before this method is considered to have failed
        :param eof: boolean to indicate whether or not to exit on first failure
        :return list of instances
        """
        self.debug('(' + str(len(instance_list)) + ") monitor_instances_to_state: '" + str(state) + "' starting....")
        monitor = copy.copy(instance_list)
        for instance in monitor:
            if not isinstance(instance, EuInstance) and not isinstance(instance, WinInstance):
                instance = EuInstance.make_euinstance_from_instance( instance, self, auto_connect=False)

        good = []
        failed = []
        elapsed = 0
        start = time.time()
        failmsg = None
        pollinterval = 10
        failmsg = ""
        #If no min allowed successful instance count is given, set it to the length of the list provdied. 
        if min is None:
            min = len(instance_list)
        while monitor and elapsed < timeout:
            elapsed = int(time.time() - start)
            self.debug("\n------>Waiting for remaining "+str(len(monitor))+"/"+str(len(instance_list))+
                       " instances to go to state:"+str(state)+', elapsed:('+str(elapsed)+'/'+str(timeout)+")...")
            for instance in monitor:
                try:
                    instance.update()
                    bdm_root_vol_status = None
                    bdm_root_vol_id = None
                    if instance.root_device_type == 'ebs':
                        if not instance.bdm_root_vol:
                            try:
                                instance.bdm_root_vol = self.get_volume(volume_id = instance.block_device_mapping.get(instance.root_device_name).volume_id)
                                bdm_root_vol_id = instance.bdm_root_vol.id
                                bdm_root_vol_status = instance.bdm_root_vol.status
                            except: pass
                        else:
                            instance.bdm_root_vol.update()
                            bdm_root_vol_id = instance.bdm_root_vol.id
                            bdm_root_vol_status = instance.bdm_root_vol.status
                        if instance.laststate:
                            #fail fast on ebs backed instances that go into stopped stated unintentionally
                            if state != "stopped" and ( instance.laststate == 'pending' and instance.state == "stopped"):
                                raise Exception("Instance:"+str(instance.id)+" illegal state transition from "
                                                +str(instance.laststate)+" to "+str(instance.state))
                    dbgmsg = ("Intended state:" + str(state)+": "+str(instance.id)+' Current state:'+str(instance.state)+', type:'+
                              str(instance.root_device_type) + ', backing volume:'+str(bdm_root_vol_id)+' status:'+
                              str(bdm_root_vol_status)+", elapsed:"+ str(elapsed)+"/"+str(timeout))
                    if instance.state == state:
                        self.debug("SUCCESS "+ dbgmsg)
                        #This instance is in the correct state, remove from monitor list
                        good.append(instance)
                    else:
                        for failed_state in failstates:
                            if instance.state == failed_state:
                                raise Exception('FAILED STATE:'+ dbgmsg )

                    self.debug("WAITING for "+dbgmsg)
                except Exception, e:
                    failed.append(instance)
                    tb = self.get_traceback()
                    self.debug('FAILED: Instance:'+str(instance.id)+",err:"+str(e)+"\n"+str(tb))
                    if eof:
                        self.debug("EOF set to True, monitor_euinstances_to_state ending...")
                        raise e
                    if len(instance_list) - len(failed) > min:
                        self.debug('Failed instances has exceeded allowed minimum('+str(min)+") monitor_euinstances_to_state ending...")
                        raise e
                    else:
                        failmsg += str(e)+"\n"
                        
            #remove good instances from list to monitor
            for instance in monitor:
                if (instance in good) or (instance in failed):
                    monitor.remove(instance)
                    
            if monitor:
                time.sleep(poll_interval)
                
        self.print_euinstance_list(instance_list)
        if monitor:
            failmsg = "Some instances did not go to state:"+str(state)+' within timeout:'+str(timeout)+"\nFailed:"
            for instance in monitor:
                failed.append(instance)
                failmsg += str(instance.id)+","
            if eof:
                raise Exception(failmsg)
            if len(instance_list) - len(failed) > min:
                self.debug('Failed instances has exceeded allowed minimum('+str(min)+") monitor_euinstances_to_state ending...")
                raise Exception(failmsg)
            else:
                self.debug(failmsg)

    def print_euinstance_list(self,
                              euinstance_list=None,
                              state=None,
                              instance_id=None,
                              reservation=None,
                              root_device_type=None,
                              zone=None,
                              key=None,
                              public_ip=None,
                              private_ip=None,
                              ramdisk=None,
                              kernel=None,
                              image_id=None
                              ):
        """

        :param euinstance_list: list of euinstance objs
        :raise:
        """
        plist = []
        if not euinstance_list:
            euinstance_list = []
            instances = self.get_instances(state=state,
                                           idstring=instance_id,
                                           reservation=reservation,
                                           rootdevtype=root_device_type,
                                           zone=zone,
                                           key=key,
                                           pubip=public_ip,
                                           privip=private_ip,
                                           ramdisk=ramdisk,
                                           kernel=kernel,
                                           image_id=image_id)
            for instance in instances:
                instance_res = getattr(instance, 'reservation', None)
                euinstance_list.append(self.convert_instance_to_euisntance(
                    instance, reservation=instance_res, auto_connect=False))
        if not euinstance_list:
            self.debug('No instances to print')
            return
        for instance in euinstance_list:
            if not isinstance(instance,EuInstance) and not isinstance(instance, WinInstance):
                self.debug("print instance list passed non-EuInstnace type")
                instance = self.convert_instance_to_euisntance(instance, auto_connect=False)
            plist.append(instance)
        first = plist.pop(0)
        buf = first.printself(title=True, footer=True)
        for instance in plist:
            buf += instance.printself(title=False, footer=True)
        self.debug("\n"+str(buf)+"\n")

    @Eutester.printinfo
    def wait_for_valid_ip(self, instances, regex="0.0.0.0", poll_interval=10, timeout = 60):
        """
        Wait for instance public DNS name to clear from regex

        :param instances:
        :param private_addressing: boolean for whether instance has private addressing enabled
        :param poll_interval:
        :param instance: instance object to check
        :param timeout: Time in seconds to wait for IP to change
        :return: True on success
        :raise: Exception if IP stays at 0.0.0.0
        """
        #self.debug("wait_for_valid_ip: Monitoring instances for valid ips...")
        if not isinstance(instances, types.ListType):
            monitoring = [instances]
        else:
            monitoring = copy.copy(instances)
        elapsed = 0
        good = []
        start = time.time()
        zeros = re.compile(regex)
        while monitoring and (elapsed <= timeout):
            elapsed = int(time.time()- start)
            for instance in monitoring:
                instance.update()
                if hasattr(instance, 'ip_address') and instance.ip_address and \
                        (zeros.search(str(instance.ip_address)) or zeros.search(str(instance.private_ip_address))):
                    self.debug(str(instance.id)+": WAITING for public ip. Current:"+str(instance.ip_address)+
                               ", elapsed:"+str(elapsed)+"/"+str(timeout))
                else:
                    self.debug(str(instance.id)+": FOUND public ip. Current:"+str(instance.ip_address)+
                               ", elapsed:"+str(elapsed)+"/"+str(timeout))
                    good.append(instance)
            #clean up list outside of loop
            for instance in good:
                if instance in monitoring:
                    monitoring.remove(instance)
            if monitoring:
                time.sleep(poll_interval)
        if monitoring:
            buf = "Instances timed out waiting for a valid IP, elapsed:"+str(elapsed)+"/"+str(timeout)+"\n"
            for instance in instances:
                buf += "Instance: "+str(instance.id)+", public ip: "+str(instance.ip_address)+", private ip: "+str(instance.private_ip_address)+"\n"
            raise Exception(buf)
        self.check_system_for_dup_ip(instances=good)
        self.debug('Wait_for_valid_ip done')
                
    def check_system_for_dup_ip(self, instances=None):
        """
        Check system for instances with conflicting duplicate IPs.
        Will raise exception at end of iterating through all running, pending, or starting instances with info
        as to which instances and IPs conflict.
        If a list of instances is provided, all other conflicting IPS will be ignored and will only raise an exception
        for conflicts with the provided instance 'inst'

        :param instances: optional list, or subset of instances to use in duplicate search.
        """
        errbuf = ""
        publist = {}
        privlist = {}
        self.debug('Check_system_for_dup_ip starting...')
        reslist = self.ec2.get_all_instances()
        for res in reslist:
            self.debug("Checking reservation: "+str(res.id))
            for instance in res.instances:
                self.debug('Checking instance '+str(instance.id).ljust(20)+', state:'+str(instance.state).ljust(20)+
                           ' pubip:'+str(instance.ip_address).ljust(20)+
                           ' privip:'+str(instance.private_ip_address).ljust(20))
                if instance.state == 'running' or instance.state == 'pending' or instance.state == 'starting':
                    if instance.ip_address != '0.0.0.0':
                        if instance.ip_address in publist:
                            errbuf += "PUBLIC:"+str(instance.id)+"/"+str(instance.state)+"="+\
                                      str(instance.ip_address)+" vs: "+\
                                      str(publist[instance.ip_address])+"\n"
                            if instances and (instance in instances):
                                raise Exception("PUBLIC:"+str(instance.id)+"/"+str(instance.state)+"="+
                                                str(instance.ip_address)+" vs: "+
                                                str(publist[instance.ip_address]))
                        else:
                            publist[instance.ip_address] = str(instance.id+"/"+instance.state)
                    if instance.private_ip_address != '0.0.0.0':
                        if instance.private_ip_address in privlist:
                            errbuf += "PRIVATE:"+str(instance.id)+"/"+str(instance.state)+"="+\
                                      str(instance.private_ip_address)+" vs: "+\
                                      str(privlist[instance.private_ip_address])+"\n"
                            if instances and (instance in instances):
                                raise Exception("PRIVATE:"+str(instance.id)+"/"+str(instance.state)+"="+
                                                str(instance.private_ip_address)+" vs: "+
                                                str(privlist[instance.private_ip_address]))
                        else:
                            privlist[instance.private_ip_address] = str(instance.id+"/"+instance.state)
        if not instances and errbuf:
            raise Exception("DUPLICATE IPs FOUND:"+errbuf)
        self.debug("Done with check_system_for_dup_ip")
        

    def convert_reservation_to_euinstance(self, reservation, username="root", password=None, keyname=None, private_addressing=False, timeout=60):
        """
        Convert all instances in an entire reservation into eutester.euinstance.Euinstance objects.

        :param reservation: reservation object to use in conversion
        :param username: SSH user name of instance
        :param password: SSH password
        :param keyname: Private key file to use when connecting to the instance
        :param timeout: Time in seconds to wait for successful SSH connection
        :return:
        """
        euinstance_list = []
        keypair = None
        if keyname is not None:
                keypair = self.get_keypair(keyname)
        for instance in reservation.instances:
            if keypair is not None or (password is not None and username is not None):
                try:
                    euinstance_list.append( EuInstance.make_euinstance_from_instance(instance, 
                                                                                     self, 
                                                                                     keypair=keypair, 
                                                                                     username = username, 
                                                                                     password=password, 
                                                                                     timeout=timeout,
                                                                                     private_addressing=private_addressing))
                except Exception, e:
                    self.debug(self.get_traceback())
                    euinstance_list.append(instance)
                    self.get_console_output(instance)
                    self.fail("Unable to create Euinstance from " + str(instance)+": "+str(e))
            else:
                euinstance_list.append(instance)
        reservation.instances = euinstance_list
        return reservation

    def convert_instance_to_euisntance(self, instance, keypair=None,
                                       username="root", password=None,
                                       reservation=None,auto_connect=True,
                                       timeout=120):
        if instance.platform == 'windows':
            return WinInstance.make_euinstance_from_instance(
                instance,
                self,
                keypair=keypair,
                username = username,
                password=password,
                reservation=reservation,
                auto_connect=auto_connect,
                timeout=timeout)
        else:
            return EuInstance.make_euinstance_from_instance(
                instance,
                self,
                keypair=keypair,
                username = username,
                password=password,
                reservation=reservation,
                auto_connect=auto_connect,
                timeout=timeout)

    def get_console_output(self, instance):
        """
        Retrieve console output from an instance

        :param instance:  Instance ID or Instance object
        :return: string
        :raise: Exception on failure to get console output
        """
        self.debug("Attempting to get console output from: " + str(instance))
        if isinstance(instance, Instance):
            instance = instance.id
        output = self.ec2.get_console_output(instance_id=instance)
        self.debug(output.output)
        return output


    def get_keypair(self, name):
        """
        Retrieve a boto.ec2.keypair object by its name

        :param name:  Name of keypair on the cloud
        :return: boto.ec2.keypair object
        :raise: Exception on failure to find keypair
        """
        try:
            return self.ec2.get_all_key_pairs([name])[0]
        except IndexError, e:
            raise Exception("Keypair: " + name + " not found")
        
    def get_zones(self):
        """
        Return a list of availability zone names.

        :return: list of zone names
        """
        zone_objects = self.ec2.get_all_zones()
        zone_names = []
        for zone in zone_objects:
            zone_names.append(zone.name)
        return zone_names
 
    @Eutester.printinfo
    def get_instances(self,
                      state=None,
                      idstring=None,
                      reservation=None,
                      rootdevtype=None,
                      zone=None,
                      key=None,
                      pubip=None,
                      privip=None,
                      ramdisk=None,
                      kernel=None,
                      image_id=None,
                      filters=None):
        """
        Return a list of instances matching the filters provided.

        :param state: str of desired state
        :param idstring: instance-id string
        :param reservation:  reservation-id
        :param rootdevtype: 'instance-store' or 'ebs'
        :param zone: Availablity zone
        :param key: Keypair the instance was launched with
        :param pubip: Instance public IP
        :param privip: Instance private IP
        :param ramdisk: Ramdisk ID string
        :param kernel: Kernel ID string
        :param image_id: Image ID string
        :param filters: dict filters
        :return: list of instances
        """
        ilist = []
        if isinstance(idstring, list):
            instance_ids = idstring
        elif idstring:
            instance_ids = str(idstring)
        else:
            instance_ids = idstring
        
        reservations = self.ec2.get_all_instances(instance_ids=instance_ids, filters=filters)
        for res in reservations:
            if ( reservation is None ) or (re.search(str(reservation), str(res.id))):
                for i in res.instances:
                    #if (idstring is not None) and (not re.search(idstring, i.id)) :
                    #   continue
                    if (state is not None) and (i.state != state):
                        continue
                    if (rootdevtype is not None) and (i.root_device_type != rootdevtype):
                        continue
                    if (zone is not None) and (i.placement != zone ):
                        continue
                    if (key is not None) and (i.key_name != key):
                        continue
                    if (pubip is not None) and (i.ip_address != pubip):
                        continue
                    if (privip is not None) and (i.private_ip_address != privip):
                        continue
                    if (ramdisk is not None) and (i.ramdisk != ramdisk):
                        continue
                    if (kernel is not None) and (i.kernel != kernel):
                        continue
                    if (image_id is not None) and (i.image_id != image_id):
                        continue
                    i.reservation = res
                    ilist.append(i)
        return ilist

        
    
    def get_connectable_euinstances(self,path=None,username='root', password=None, connect=True):
        """
        Convenience method, returns a list of all running instances, for the current creduser
        for which there are local keys at 'path'

        :param path: Path to look for private keys
        :param username: username to use if path is not pfassed
        :param password: password to use if path is not passed
        :param connect: bool, Whether to create an ssh connection to the instances
        :return:
        """
        try:
            euinstances = []
            keys = self.get_all_current_local_keys(path=path) or []
            for keypair in keys:
                self.debug('Looking for instances using keypair:'+keypair.name)
                instances = self.get_instances(state='running',key=keypair.name) or []
                for instance in instances:
                    if not connect:
                        keypair=None
                        euinstances.append(instance)
                    else:
                        euinstances.append(EuInstance.make_euinstance_from_instance( instance, 
                                                                                     self, 
                                                                                     username=username,
                                                                                     password=password,
                                                                                     keypair=keypair ))
            return euinstances
        except Exception, e:
            self.debug("Failed to find a pre-existing instance we can connect to:"+str(e))
            pass
    
    
    def get_all_attributes(self, obj, verbose=True):
        """
        Get a formatted list of all the key pair values pertaining to the object 'obj'

        :param obj: Object to extract information from
        :param verbose: Print key value pairs
        :return: Buffer of key value pairs
        """
        buf=""
        alist = sorted(obj.__dict__)
        for item in alist:
            if verbose:
                print str(item)+" = "+str(obj.__dict__[item])
            buf += str(item)+" = "+str(obj.__dict__[item])+"\n"
        return buf
    

    def terminate_instances(self, reservation=None, timeout=480):
        """
        Terminate instances in the system

        :param reservation: Reservation object to terminate all instances in, default is to terminate all instances
        :raise: Exception when instance does not reach terminated state
        """
        ### If a reservation is not passed then kill all instances
        aggregate_result = False
        instance_list = []
        monitor_list = []
        if reservation and not isinstance(reservation, types.ListType):
            if isinstance(reservation, Reservation):
                instance_list = reservation.instances or []
            elif isinstance(reservation, Instance):
                instance_list.append(reservation)
            else:
                raise Exception('Unknown type:' + str(type(reservation)) + ', for reservation passed to terminate_instances')
        else:
            if reservation is None:
                reservation = self.ec2.get_all_instances()
            #first send terminate for all instances
            for res in reservation:
                if isinstance(res, Reservation):
                    instance_list.extend(res.instances)
                elif isinstance(res, Instance):
                    instance_list.append(res)
                else:
                    raise Exception('Need type instance or reservation in terminate_instances. type:' + str(type(res)))

        for instance in instance_list:
            self.debug( "Sending terminate for " + str(instance))
            try:
               instance.terminate()
               instance.update()
               if instance.state != 'terminated':
                    monitor_list.append(instance)
               else:
                    self.debug('Instance: ' + str(instance.id) + ' in terminated state:' + str(instance.state))
            except EC2ResponseError, e:
                if e.status == 400:
                    pass
                else:
                    raise e

        self.print_euinstance_list(euinstance_list=monitor_list)
        try:
            self.monitor_euinstances_to_state(instance_list=monitor_list, state='terminated', timeout=timeout)
            aggregate_result = True
        except Exception, e:
            self.debug('Caught Exception in monitoring instances to terminated state:' + str(e))

        return aggregate_result
    
    def stop_instances(self,reservation, timeout=480):
        """
        Stop all instances in a reservation

        :param reservation: boto.ec2.reservation object
        :raise: Exception when instance does not reach stopped state
        """
        instance_list = reservation
        if isinstance(reservation, Reservation):
            instance_list = reservation.instances
        for instance in instance_list:
            self.debug( "Sending stop for " + str(instance) )
            instance.stop()
        if self.wait_for_reservation(reservation, state="stopped", timeout=timeout) is False:
            return False
        return True
    
    def start_instances(self, reservation, timeout=480):
        """
        Start all instances in a reservation

        :param reservation: boto.ec2.reservation object or list of instances
        :raise: Exception when instance does not reach running state
        """
        instance_list = reservation
        if isinstance(reservation, Reservation):
            instance_list = reservation.instances
        for instance in instance_list:
            self.debug( "Sending start for " + str(instance) )
            instance.start()
        if self.wait_for_reservation(reservation, state="running", timeout=timeout) is False:
            return False
        return True

    def start_bundle_instance_task( self,
                                    instance,
                                    bucket_name = None,
                                    prefix = None,
                                    ):
        """
        REQUIRED PARAMETERS
        :rtype : BundleInstanceTask
        :param instance: boto instance to bundle
        :param bucket_name: Name of the bucket to upload. Default='win+ramdom'
        :param prefix:  The prefix for the image file name:Default='windows-bun + emi + random.'
        :param access_key:  String, Access Key ID of the owner of the bucket
        :param secret_key:  String, Secret key used to sign the upload policy
        :return : bundle task object

        """

        if not bucket_name:
            # Count images already registered with this instance id for concurrent tests
            try:
                id_count = len(self.get_images(location=instance.id))
            except:
                id_count = 0
            bucket_name =  str(instance.id) + "-" \
                           + str(id_count)
        prefix = prefix or 'bundleof-' + str(instance.id)
        s3_upload_policy = self.generate_default_s3_upload_policy(bucket_name,prefix)
        bundle_task = self.ec2.bundle_instance(instance.id, bucket_name, prefix, s3_upload_policy)
        self.print_bundle_task(bundle_task)
        return bundle_task



    def print_bundle_task(self,bundle, header=True, footer=True, printout=True):

        """
        Prints formatted output of bundle task attributes.
        :param bundle: BundleInstanceTask object to be printed
        :param header: boolean to print header containing column titles
        :param footer: boolean to print footer containing closing row line
        :param printout: boolean to print output using self.debug, else will return a buffer to be printed later.
        :return: string containing formatted output.
        """
        id_len = 15
        instance_id_len = 12
        bucket_len = 36
        prefix_len = 36
        state_len = 15
        start_time_len = 25
        update_time_len = 25
        buf = ""
        line = "-----------------------------------------------------------------------------------------------------" \
               "--------------------------------------------------------------"
        if header:
            buf += str("\n" + line +"\n")
            buf += str('BUNDLE_ID').center(id_len) + '|' \
                   + str('INSTANCE').center(instance_id_len) + '|' \
                   + str('BUCKET').center(bucket_len) + '|' \
                   + str('PREFIX').center(prefix_len) + '|' \
                   + str('STATE').center(state_len) + '|' \
                   + str('START_TIME').center(start_time_len) + '|' \
                   + str('UPDATE_TIME').center(update_time_len) + '\n'
            buf += str(line + "\n")
        buf += str(bundle.id).center(id_len) + '|' \
               + str(bundle.instance_id).center(instance_id_len) + '|' \
               + str(bundle.bucket).center(bucket_len) + '|' \
               + str(bundle.prefix).center(prefix_len) + '|' \
               + str(bundle.state).center(state_len) + '|' \
               + str(bundle.start_time).center(start_time_len) + '|' \
               + str(bundle.update_time).center(update_time_len)
        if footer:
            buf += str("\n" + line)
        if printout:
            self.debug(buf)
        return buf


    def bundle_instance_monitor_and_register(self,
                                             instance,
                                             bucket_name=None,
                                             prefix=None,
                                             poll_interval_seconds=20,
                                             timeout_minutes=25):
        """
        Attempts to start a bundle task and monitor it to completion.
        :param instance: boto instance to bundle
        :param bucket_name: Name of the bucket to upload. Default='win+ramdom'
        :param prefix:  The prefix for the image file name:Default='windows-bun + emi + random.'
        :param access_key:  String, Access Key ID of the owner of the bucket
        :param secret_key:  String, Secret key used to sign the upload policy
        :param poll_interval_seconds: Seconds to wait between polling for bundle task status
        :param timeout_minutes: int, minutes to wait before timing out.
        :return : image
        """
        return_dict = {}
        return_dict['manifest'] = None
        return_dict['image'] = None

        bundle_task = self.start_bundle_instance_task(instance,
                                                      bucket_name=bucket_name,
                                                      prefix=prefix,
                                                      )
        self.debug("bundle_instance_monitor_and_register: Got bundle task id:" +str(bundle_task.id)
                   + ", now monitor to completed state")
        self.monitor_bundle_tasks(bundle_task.id,
                                  poll_interval_seconds=poll_interval_seconds,
                                  timeout_minutes=timeout_minutes)
        self.debug("bundle_instance_monitor_and_register:" + str(bundle_task.id)
                   + " monitored to completed, now get manifest and register...")
        manifest = self.get_manifest_string_from_bundle_task(bundle_task)
        image = self.register_manifest(manifest)
        self.debug("bundle_instance_monitor_and_register:" + str(bundle_task.id)
                   + ", registered as image:" + str(image.id))
        self.debug("bundle_instance_monitor_and_register:" + str(bundle_task.id)
                   + ", now make sure original instance " + (instance.id) + " returns to running state...")
        self.monitor_euinstances_to_state(instance_list=[instance],
                                          state='running',
                                          timeout=600)
        return image


    def get_bundle_task_by_id(self,bundle_task_id):
        bundles = self.ec2.get_all_bundle_tasks(bundle_ids=[bundle_task_id])
        if bundles:
            return bundles[0]

    def get_manifest_string_from_bundle_task(self,bundle):

        """
        Create a manifest string from a BundleInstanceTask obj
        :param bundle: BundleInstanceTask
        :return: manifest string
        """
        return str(bundle.bucket) + "/" + str(bundle.prefix) + ".manifest.xml"

    def monitor_bundle_tasks(self, bundle_list, poll_interval_seconds=20, timeout_minutes=25, eof=True):
        """
        Attempts to monitor the state of the bundle task id provided until completed or failed.

        :param bundle_id: string bundle id to poll status for
        :param poll_interval_seconds: sleep period in seconds between polling for bundle task status
        :param timeout_minutes: timeout specified in minutes
        :param eof: boolean, end on first failure otherwise delay error until all bundle tasks have completed or failed
        """
        monitor_list = []
        fail_msg = ""
        if not isinstance(bundle_list, types.ListType):
            bundle_list = [bundle_list]

        for bundle in bundle_list:
            if isinstance(bundle, BundleInstanceTask ):
                monitor_list.append(bundle.id)
            else:
                monitor_list.append(bundle)
        start = time.time()
        elapsed = 0
        timeout = timeout_minutes * 60
        while monitor_list and elapsed < timeout:
            for bundle_id in monitor_list:
                self.debug('Waiting for bundle task:' + str(bundle_id) + ' to finish. Elapsed:' + str(elapsed))
                try:
                    bundle_task = self.get_bundle_task_by_id(bundle_id)
                    if bundle_task:
                        self.print_bundle_task(bundle_task)
                    else:
                        self.debug(str(bundle_id) + ": Assuming bundle task is complete, fetch came back empty?")
                        monitor_list.remove(bundle_id)
                    if bundle_task.state is None or bundle_task.state == 'none':
                        raise Exception(str(bundle_id) + ": Bundle task state err, state is: '"
                                        + str(bundle_task.state) + "' in monitor")
                    if bundle_task.state == 'failed':
                        raise Exception(str(bundle_id) + ": Bundle task reporting failed state during monitor")
                    if bundle_task.state == 'complete':
                        self.debug(str(bundle_id) +":  Bundle task reported state is completed during monitor")
                        monitor_list.remove(bundle_id)
                except Exception, e:
                    fail_msg += 'Monitor_bundle_task ERROR: '+str(e) + "\n"
                    if eof:
                        raise Exception('Monitor_bundle_task ERROR: '+str(e))
                    else:
                        monitor_list.remove(bundle_id)

            time.sleep(poll_interval_seconds)
            elapsed = int(time.time()-start)
        if fail_msg:
            raise Exception(fail_msg)
        return bundle_list



    def register_manifest(self,
                          manifest,
                          root_device_name=None,
                          description=None,
                          architecture=None,
                          virtualization_type=None,
                          platform=None,
                          bdmdev=None,
                          name=None,
                          ramdisk=None,
                          kernel=None):
        """
        Attempts to register the provided manifest and return the image id created by it
        :param manifest: manifest string to register
        :return: : image id string
        """
        image = self.register_image(manifest,
                                    root_device_name=root_device_name,
                                    description=description,
                                    architecture=architecture,
                                    virtualization_type=virtualization_type,
                                    platform=platform,
                                    bdmdev=bdmdev,
                                    name=name,
                                    ramdisk=ramdisk,
                                    kernel=kernel)
        #check to see if really registered by getting image obj to be returned
        try:
            image_obj = self.get_emi(emi=image)
        except Exception, e:
            raise Exception('Failed to retrieve image after registering. Image:' + str(image) + ", err:" + str(e))
        self.debug("Registered '" + str(manifest) + "as image:" + str(image))
        return image_obj

    def _register_image_custom_params(self,
                                     name=None,
                                     description=None,
                                     image_location=None,
                                     architecture=None,
                                     kernel_id=None,
                                     ramdisk_id=None,
                                     root_device_name=None,
                                     block_device_map=None,
                                     dry_run=False,
                                     virtualization_type=None,
                                     sriov_net_support=None,
                                     snapshot_id=None,
                                     platform=None,
                                     **custom_params):
        '''
        Register method to allow testing of 'custom_params' dict if provided
        '''
        params = custom_params or {}
        if name:
            params['Name'] = name
        if description:
            params['Description'] = description
        if architecture:
            params['Architecture'] = architecture
        if kernel_id:
            params['KernelId'] = kernel_id
        if ramdisk_id:
            params['RamdiskId'] = ramdisk_id
        if image_location:
            params['ImageLocation'] = image_location
        if platform:
            params['Platform'] = platform
        if root_device_name:
            params['RootDeviceName'] = root_device_name
        if snapshot_id:
            root_vol = BlockDeviceType(snapshot_id=snapshot_id)
            block_device_map = BlockDeviceMapping()
            block_device_map[root_device_name] = root_vol
        if block_device_map:
            block_device_map.ec2_build_list_params(params)
        if dry_run:
            params['DryRun'] = 'true'
        if virtualization_type:
            params['VirtualizationType'] = virtualization_type
        if sriov_net_support:
            params['SriovNetSupport'] = sriov_net_support


        rs = self.ec2.get_object('RegisterImage', params,
                                 ResultSet, verb='POST')
        image_id = getattr(rs, 'imageId', None)
        return image_id



    def create_image(self, instance, name, description=None, no_reboot=False, block_device_mapping=None, dry_run=False,
                     timeout=600):
        """
        :type instance_id: string
        :param instance_id: the ID of the instance to image.

        :type name: string
        :param name: The name of the new image

        :type description: string
        :param description: An optional human-readable string describing
            the contents and purpose of the AMI.

        :type no_reboot: bool
        :param no_reboot: An optional flag indicating that the
            bundling process should not attempt to shutdown the
            instance before bundling.  If this flag is True, the
            responsibility of maintaining file system integrity is
            left to the owner of the instance.

        :type block_device_mapping: :class:`boto.ec2.blockdevicemapping.BlockDeviceMapping`
        :param block_device_mapping: A BlockDeviceMapping data structure
            describing the EBS volumes associated with the Image.

        :type dry_run: bool
        :param dry_run: Set to True if the operation should not actually run.

        :type timeout: int
        :param timeout: Time to allow image to get to "available" state.

        :raise Exception: On not reaching the correct state or when more than one image is returned
        """
        if isinstance(instance, Instance):
            instance_id = instance.id
        else:
            instance_id = instance
        image_id = self.ec2.create_image(instance_id, name=name,description=description,no_reboot=no_reboot,
                                     block_device_mapping=block_device_mapping, dry_run=dry_run)
        def get_emi_state():
            images = self.ec2.get_all_images(image_ids=[image_id])
            if len(images) == 0:
                raise Exception("Image not found after sending create image request: " + image_id)
            elif len(images) == 1:
                state = images[0].state
                self.debug( image_id + " returned state: " + state)
                return state
            else:
                raise Exception("More than one image returned for: " + image_id)
        self.wait_for_result(get_emi_state, "available", timeout=timeout,poll_wait=20)
        return image_id

    def get_all_conversion_tasks(self, taskid=None):
        params = {}
        if taskid:
            params['ConversionTaskId'] = str(taskid)
        return self.ec2.get_list('DescribeConversionTasks',
                                  params,
                                  [('item', ConversionTask),
                                   ('euca:item', ConversionTask)],
                                  verb='POST')

    def get_conversion_task(self, taskid):
        params = {'ConversionTaskId':str(taskid)}
        task = self.ec2.get_object('DescribeConversionTasks',
                                   params,
                                   ConversionTask,
                                   verb='POST')
        if not task:
            raise ResourceNotFoundException('"{0}". Conversion task not found'
                                            .format(taskid))
        return task

    def monitor_conversion_tasks(self,
                                 tasks,
                                 states='completed',
                                 time_per_gig=90,
                                 base_timeout=600,
                                 interval=10,
                                 exit_on_failure=False):
        """
        Monitors a list a task or list of tasks. Will monitor each
        task's state to the provided 'state', or until failure, timeout.
        Note: timeout is calculated by size of the largest task multiplied by
              'time_per_gig' added to the 'base_timeout'.
        :param tasks: list of tasks.
        :param state: string representing desired state to monitor to.
                      (pending, active, cancelled, completed, failed)
        :param time_per_gig: time in seconds per largest task size in GB
                             to append to base timeout
        :param base_timeout: base timeout in seconds
        :param interval: seconds between polling tasks
        :param exit_on_failure: Will stop monitoring and raise an exception
                                upon first found failure. Otherwise will
                                continue monitoring remaining tasks in list
                                and raise the error when all tasks are
                                complete or timed out.
        """
        err_buf = ""
        monitor_list = []
        if not isinstance(states, types.ListType):
            states = [states]
        #Sanitize provided list...
        if not isinstance(tasks, types.ListType):
            tasks = [tasks]
        for task in tasks:
            if (not isinstance(task,ConversionTask) and
                    isinstance(task,types.StringType)):
                task = self.get_conversion_task(taskid=task)
            monitor_list.append(task)
        checking_list = copy.copy(monitor_list)
        done_list = []
        start = time.time()
        elapsed = 0
        timeout = 0
        for task in checking_list:
            for im in task.importvolumes:
                task_timeout = int(im.volume_size) * int(time_per_gig)
                if task_timeout > timeout:
                    timeout = task_timeout
        timeout += base_timeout
        while checking_list and elapsed < timeout:
            for task in checking_list:
                task.update()
                self.debug(task)
                #If the task volume is present add it to the resources list.
                found = False
                for vol in task.volumes:
                    for resvol in self.test_resources['volumes']:
                        if resvol.id == vol.id:
                            found = True
                            break
                    if not found and not vol in self.test_resources['volumes']:
                        self.test_resources['volumes'].append(vol)
                found = False
                if task.instanceid:
                    for resins in self.test_resources['reservations']:
                        if resins.id == task.instanceid:
                            found = True
                            break
                        if resins.id == task.instance.reservation.id:
                            found = True
                            break
                    if not found:
                        ins = self.get_instances(idstring=task.instanceid)
                        if ins:
                            ins = ins[0]
                            if not ins in self.test_resources['reservations']:
                                self.test_resources['reservations'].append(ins)
                #notfound flag is set if task is not found during update()
                if task.notfound:
                    err_msg = 'Task "{0}" not found after elapsed:"{1}"'\
                        .format(task.conversiontaskid, elapsed)
                    err_buf += "\n" + err_msg
                    self.debug(err_msg)
                    done_list.append(task)
                    continue
                self.debug('Monitoring task:"{0}:{1}", elapsed:'
                           '"{2}/{3}"'
                           .format(task.conversiontaskid,
                                   task.state,
                                   elapsed,
                                   timeout))
                task_state = task.state.lower()
                in_state = False
                #Check state of task against all desired states provided
                for state in states:
                    if task_state == state:
                        in_state = True
                        break
                if in_state:
                    self.debug('Task:"{0}" found in desired state:"{1}"'.
                               format(task.conversiontaskid, task.state))
                    done_list.append(task)
                    continue
                # Fail fast for tasks found a final state that doesnt match
                # the desired state provided
                for final_state in ["completed", "cancelled", "failed"]:
                    if re.search(final_state, task_state):
                        err_msg = ('Task "{0}" found in a final state:"{1}" '
                                   'after elapsed:"{2}", msg:"{3}"'
                                   .format(task.conversiontaskid,
                                           task.state,
                                           elapsed,
                                           task.statusmessage))
                        err_buf += "\n" + err_msg
                        self.debug(err_msg)
                        done_list.append(task)
                        continue
            try:
                self.print_conversion_task_list(clist=monitor_list)
            except Exception as PE:
                self.debug('failed to print conversion task list, err:' +
                    str(PE))
            if exit_on_failure and err_buf:
                break
            for done_task in done_list:
                if done_task in checking_list:
                    checking_list.remove(done_task)
            if checking_list:
                self.debug('Waiting for "{0}" remaining tasks to reach '
                           'desired state:"{1}". Sleeping:"{2}"'
                           .format(len(checking_list), state, interval))
                time.sleep(interval)
            elapsed = int(time.time() - start)
        self.print_conversion_task_list(clist=tasks)
        #Any tasks still in checking_list are failures
        for task in checking_list:
            err_buf += ('Monitor complete. Task "{0}:{1}" not in desired '
                        'state "{2}" after elapsed:"{3}"\n'
                        .format(task.conversiontaskid,
                                task.state,
                                state,
                                elapsed))
        if err_buf:
            err_buf = "Exit on first failure set to:" + str(exit_on_failure) \
                      + "\n" + err_buf
            raise Exception('Monitor conversion tasks failures detected:\n'
                            + str(err_buf))

    def print_conversion_task_list(self,
                                   clist=None,
                                   doprint=True,
                                   printmethod=None):
        clist = clist or self.get_all_conversion_tasks()
        printmethod = printmethod or self.debug
        taskidlen = 19
        statusmsglen = 24
        availzonelen=14
        volumelen=16
        snaplen=13
        instancelen=13
        imagelen=13
        header = ('TASKID'.center(taskidlen) + " | " +
                  'SNAPSHOTS'.center(snaplen) + " | " +
                  'INSTANCE'.center(instancelen) + " | " +
                  'IMAGE ID'.center(imagelen) + " | " +
                  'ZONE'.center(availzonelen) + " | " +
                  'VOLUMES'.center(volumelen) + " | " +
                  'STATUS MSG'.center(statusmsglen) + " |\n" )
        line = ""
        for x in xrange(0, len(header)):
            line += '-'
        line += "\n"
        buf = "\n" + line + header + line
        for task in clist:
            sizestr = None
            instancestr = "???"
            instancestatus = ""
            imagesize = None
            vollist = []
            volbytes = []
            for importvol in task.importvolumes:
                bytesconverted = importvol.bytesconverted
                volume_id = importvol.volume_id
                if importvol.image:
                    imagesize = long(importvol.image.size)
                if imagesize is not None:
                    sizegb = "%.3f" % float(
                        long(imagesize) / float(1073741824))
                    gbconverted = "%.3f" % float(
                        long(bytesconverted) / float(1073741824))
                    sizestr = ("{0}/{1}gb".format(gbconverted, sizegb))
                vollist.append(str(volume_id))
                volbytes.append(sizestr)
            volumes = ",".join(vollist)
            volbytescon = ",".join(volbytes)
            volstatus = ",".join([str('(' + str(vol.status) + ':' +
                                      str(vol.size) + ')')
                                  for vol in task.volumes]) or "???"
            snaps = ",".join([str(snap.id ) for snap in task.snapshots]) or \
                    "???"
            snapstatus = ",".join([str('(' + snap.status + ')')
                                   for snap in task.snapshots])
            if task.instance:
                instancestr = str(task.instance.id)
                instancestatus = '(' + str(task.instance.state) + ')'
            image_id = task.image_id or "???"
            buf += (str(task.conversiontaskid).center(taskidlen) + " | " +

                    str(snaps).center(snaplen) + " | " +
                    str(instancestr).center(instancelen) + " | " +
                    str(image_id ).center(imagelen) + " | " +
                    str(task.availabilityzone).center(availzonelen) + " | " +
                    str(volumes).center(volumelen) + " | " +
                    str(task.statusmessage[:statusmsglen]).ljust(statusmsglen)
                    + " |\n")
            buf += (str('(' + task.state + ')').center(taskidlen) + " | " +
                    str(snapstatus).center(snaplen) + " | " +
                    str(instancestatus).center(instancelen) + " | " +
                    str('').center(imagelen) + " | " +
                    str('').center(availzonelen) + " | " +
                    str(volstatus).center(volumelen) + " | " +
                    str(task.statusmessage[
                        statusmsglen:(2*statusmsglen)]).ljust(statusmsglen)
                    + " |\n")
            buf += (str('').center(taskidlen) + " | " +
                    str('').center(snaplen) + " | " +
                    str('').center(instancelen) + " | " +
                    str('').center(imagelen) + " | " +
                    str('').center(availzonelen) + " | " +
                    str(volbytescon).center(volumelen) + " | " +
                    str(task.statusmessage[
                        (2*statusmsglen):(3*statusmsglen)]).ljust(statusmsglen)
                    + " |\n")
            buf += line
        if doprint:
            printmethod(buf)
        return buf

    def cancel_conversion_tasks(self, tasks, timeout=180):
        tasks = tasks or self.test_resources['conversion_tasks']
        if not isinstance(tasks, types.ListType):
            tasks = [tasks]
        printbuf = self.print_conversion_task_list(clist=tasks, doprint=False)
        self.debug('Cancel Conversion task list...\n' + str(printbuf))
        cancel_tasks = copy.copy(tasks)
        for task in tasks:
            task.update()
            for state in ['canceled', 'failed', 'completed']:
                if task.state == state:
                    cancel_tasks.remove(task)
                    break
        for task in cancel_tasks:
            task.cancel()
        self.monitor_conversion_tasks(tasks=cancel_tasks, states=['canceled'])
        printbuf = self.print_conversion_task_list(clist=tasks, doprint=False)
        self.debug('Done with canceling_conversion_tasks...' + str(printbuf))


    def cleanup_conversion_task_resources(self, tasks=None):
        tasks = tasks or self.test_resources['conversion_tasks']
        if not isinstance(tasks, types.ListType):
            tasks = [tasks]
        error_msg = ""
        try:
            self.cancel_conversion_tasks(tasks)
        except Exception as CE:
                tb = self.get_traceback()
                self.critical('Failed to cancel some tasks:' + str(CE))

        for task in tasks:
            self.debug('Attempting to delete all resources associated '
                       'with task: "{0}"'
                       .format(getattr(task, 'id', 'UNKOWN_ID')))
            try:
                assert isinstance(task,ConversionTask)
                task.update()
                try:
                    if task.instance:
                        self.terminate_single_instance(task.instance)
                except Exception, e:
                    tb = self.get_traceback()
                    error_msg += str(tb) + '\n"{0}":Cleanup_error:"{1}"\n'\
                        .format(task.conversiontaskid, str(e))
                try:
                    if task.image_id:
                        image = self.get_images(emi=task.image_id)
                        if image:
                            self.delete_image(image=image)
                except Exception, e:
                    tb = self.get_traceback()
                    error_msg += str(tb) + '\n"{0}":Cleanup_error:"{1}"\n'\
                        .format(task.conversiontaskid, str(e))
                try:
                    if task.snapshots:
                        self.delete_snapshots(snapshots=task.snapshots)
                except Exception, e:
                    tb = self.get_traceback()
                    error_msg += str(tb) + '\n"{0}":Cleanup_error:"{1}"\n'\
                        .format(task.conversiontaskid, str(e))
                try:
                    if task.volumes:
                        self.delete_volumes(volume_list=task.volumes)
                except Exception, e:
                    tb = self.get_traceback()
                    error_msg += str(tb) + '\n"{0}":Cleanup_error:"{1}"\n'\
                        .format(task.conversiontaskid, str(e))
            except Exception as TE:
                tb = self.get_traceback()
                error_msg += '{0}\n"{1}" Failed to cleanup task, err:"{1}"'\
                    .format(str(tb), getattr(task, 'id', 'UNKOWN_ID'), str(TE))
        if error_msg:
            raise Exception(error_msg)


    def create_web_servers(self, keypair, group, zone, port=80, count=2, image=None, filename="test-file", cookiename="test-cookie"):
        if not image:
            image = self.get_emi()
        reservation = self.run_instance(image, keypair=keypair, group=group, zone=zone, min=count, max=count)
        self.authorize_group(group=group,port=port)

        ### TODO edit this so that the proper port is open on the apache instance
        for instance in reservation.instances:
            assert isinstance(instance, EuInstance)
            try:
                instance.sys("which apt-get", code=0)
                ## Debian based Linux
                instance.sys("apt-get update", code=0)
                instance.sys("apt-get install -y apache2", code=0)
                instance.sys("echo \"" + instance.id +"\" > /var/www/" + filename)
                instance.sys("echo \"CookieTracking on\" >> /etc/apache2/apache2.conf")
                instance.sys("echo CookieName " + cookiename +" >> /etc/apache2/apache2.conf")
            except eutester.sshconnection.CommandExitCodeException, e:
                ### Enterprise Linux
                instance.sys("yum install -y httpd", code=0)
                instance.sys("echo \"" + instance.id +"\" > /var/www/html/" + filename)
                instance.sys("echo \"CookieTracking on\" >> /etc/httpd/conf/httpd.conf")
                instance.sys("echo CookieName " + cookiename +" >> /etc/httpd/conf/httpd.conf")
                instance.sys("service httpd start")
                instance.sys("chkconfig httpd on")
        return (reservation, filename)

    def generate_default_s3_upload_policy(self, bucket, prefix, expiration=24, acl='ec2-bundle-read', encode=True):
        """
        Generates s3 upload policy for bundle instance operation

        :param bucket: bucket string
        :param prefix: prefix string
        :param expiration: int representing hours
        :param acl: acl to be used
        :return: s3 upload encoded policy
        """

        delta = timedelta(hours=expiration)
        expiration_time = (datetime.utcnow() + delta).replace(microsecond=0)
        expiration_str = expiration_time.isoformat()
        
        policy = '{"expiration": "%s",' % expiration_str + \
        '"conditions": [' + \
        '{"bucket": "%s" },' % bucket + \
        '{"acl": "%s" },' % acl + \
        '["starts-with", "$key", "%s"]' % prefix + \
        ']' + \
        '}'

        if encode:
            policy = base64.b64encode(policy)
        return policy



    def sign_policy(self, policy):
        my_hmac = hmac.new(self.aws_secret_access_key, policy, digestmod=hashlib.sha1)
        return base64.b64encode(my_hmac.digest())



    def get_euzones(self, zones=None):
        ret_list = []

        if zones is not None and not isinstance(zones, types.ListType):
            get_zones = [zones]
        else:
            get_zones = zones
        myzones = self.ec2.get_all_zones(zones=get_zones)
        for zone in myzones:
            ret_list.append(EuZone.make_euzone_from_zone(zone, self))
        return ret_list


    def get_vm_type_list_from_zone(self, zone):
        euzone = self.get_euzones(zone)[0]
        return euzone.vm_types

    def get_vm_type_from_zone(self,zone, vmtype_name):
        vm_type = None
        type_list = self.get_vm_type_list_from_zone(zone)
        for type in type_list:
            if type.name == vmtype_name:
                vm_type = type
                break
        return vm_type

    def print_block_device_map(self,block_device_map, printmethod=None ):
        printmethod = printmethod or self.debug
        buf = '\n'
        device_w = 16
        snap_w = 15
        volume_w = 15
        dot_w = 7
        size_w = 6
        status_w = 7
        ephemeral_name_w = 12
        attach_time_w = 12
        no_device_w = 7
        line = ''
        titles = str('DEVICE').ljust(device_w) + "|" + \
                 str('VOLUME_ID').center(volume_w) + "|" + \
                 str('SNAP_ID').center(snap_w) + "|" + \
                 str('D.O.T.').center(dot_w) + "|" + \
                 str('SIZE').center(size_w) + "|" + \
                 str('EPHEMERAL').center(ephemeral_name_w) + "|" + \
                 str('NO DEV').center(no_device_w) + "|" + \
                 str('ATTACH TM').center(attach_time_w) + "|" + \
                 str('STATUS').center(status_w) + "\n"

        for x in titles:
            if x == '|':
                line += '|'
            else:
                line += "-"
        line = line+"\n"
        header = str('BLOCK DEVICE MAP').center(len(line)) + "\n"
        buf += line + header + line + titles + line
        for device in block_device_map:
            bdm = block_device_map[device]
            buf += str(device).center(device_w) + "|" + \
                   str(bdm.volume_id).center(volume_w) + "|" + \
                   str(bdm.snapshot_id).center(snap_w) + "|" + \
                   str(bdm.delete_on_termination).center(dot_w) + "|" + \
                   str(bdm.size).center(size_w) + "|" + \
                   str(bdm.ephemeral_name).center(ephemeral_name_w) + "|" + \
                   str(bdm.no_device).center(no_device_w) + "|" + \
                   str(bdm.attach_time).center(attach_time_w) + "|" + \
                   str(bdm.status).center(status_w) + "\n"
        buf += line
        printmethod(buf)

    def print_all_vm_types(self,zone=None, debugmethod=None):
        debugmethod = debugmethod or self.debug
        buf = "\n"
        if zone:
            zones = [zone]
        else:
            zones = self.ec2.get_all_zones()
        for zone in zones:
            buf += "------------------------( " + str(zone) + " )--------------------------------------------\n"
            for vm in self.get_vm_type_list_from_zone(zone):
                vminfo = self.get_all_attributes(vm, verbose=False)
                buf +=  "---------------------------------"
                buf += self.get_all_attributes(vm, verbose=False)
        debugmethod(buf)

    def monitor_instances(self, instance_ids):
        self.debug('Enabling monitoring for instance(s) ' + str(instance_ids))
        self.ec2.monitor_instances(instance_ids)

    def unmonitor_instances(self, instance_ids):
        self.debug('Disabling monitoring for instance(s) ' + str(instance_ids))
        self.ec2.unmonitor_instances(instance_ids)

class VolumeStateException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class ResourceNotFoundException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
