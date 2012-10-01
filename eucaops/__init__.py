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
# Author: vic.iglesias@eucalyptus.com
# Author: matt.clark@eucalyptus.com
from boto.ec2.image import Image
from boto.ec2.volume import Volume

from iamops import IAMops
from ec2ops import EC2ops
from s3ops import S3ops
from stsops import STSops
import time
from eutester.euservice import EuserviceManager
from boto.ec2.instance import Reservation
from eutester.euconfig import EuConfig
from eutester.machine import Machine
from eutester import eulogger
import re
import os

class Eucaops(EC2ops,S3ops,IAMops,STSops):
    
    def __init__(self, config_file=None, password=None, keypath=None, credpath=None, aws_access_key_id=None, aws_secret_access_key = None,  account="eucalyptus", user="admin", username=None, region=None, ec2_ip=None, s3_ip=None, download_creds=True,boto_debug=0):
        self.config_file = config_file 
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
        self.hypervisor = None
        self.clc_index = 0
        self.credpath = credpath
        self.download_creds = download_creds
        self.logger = eulogger.Eulogger(identifier="EUTESTER")
        self.debug = self.logger.log.debug
        self.critical = self.logger.log.critical
        self.info = self.logger.log.info
        
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
            if self.password is not None and self.download_creds:
                clc_array = self.get_component_machines("clc")
                self.clc = clc_array[0]
                walrus_array = self.get_component_machines("ws")
                self.walrus = walrus_array[0]

                if self.credpath is None:
                    ### TRY TO GET CREDS ON FIRST CLC if it fails try on second listed clc, if that fails weve hit a terminal condition
                    try:
                        self.debug("Attempting to get credentials and setup sftp")
                        self.sftp = self.clc.ssh.connection.open_sftp()
                        self.credpath = self.get_credentials(account,user)
                        self.debug("Successfully downloaded and synced credentials")
                    except Exception, e:
                        self.debug("Caught an exception when getting credentials from first CLC: " + str(e))
                        ### If i only have one clc this is a critical failure, else try on the other clc
                        if len(clc_array) < 2:
                            raise Exception("Could not get credentials from first CLC and no other to try")
                        self.swap_clc()
                        self.sftp = self.clc.ssh.connection.open_sftp()
                        self.credpath = self.get_credentials(account,user)
                        
                self.service_manager = EuserviceManager(self)
                self.clc = self.service_manager.get_enabled_clc().machine
                self.walrus = self.service_manager.get_enabled_walrus().machine 
        EC2ops.__init__(self, credpath=self.credpath, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, username=username, region=region, ec2_ip=ec2_ip, s3_ip=s3_ip, boto_debug=boto_debug)
        self.test_resources = {}
        self.setup_s3_resource_trackers()
        self.setup_ec2_resource_trackers()
    
    def get_available_vms(self, type=None, zone=None):
        """
        Get available VMs of a certain type or return a dictionary with all types and their available vms
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
                zone_index += 7
            if zone_index > (len(zones) - 1)   :
                self.fail("Was not able to find AZ: " + zone)
                raise Exception("Unable to find Availability Zone")    
        else:
            zone = zones[0].name
            
        ### Inline switch statement
        type_index = {
                      'm1.small': 2,
                      'c1.medium': 3,
                      'm1.large': 4,
                      'm1.xlarge': 5,
                      'c1.xlarge': 6,
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
        command = self.eucapath + "/usr/sbin/euca-modify-property -p " + property + "=" + value
        if self.found(command, property):
            self.debug("Properly modified property " + property)
        else:
            raise Exception("Setting property " + property + " failed")
    
   
    def cleanup_artifacts(self):
        self.debug("Starting cleanup of artifacts")
        for key,array in self.test_resources.iteritems():
            for item in array:
                try:
                    ### SWITCH statement for particulars of removing a certain type of resources
                    self.debug("Deleting " + str(item))
                    if isinstance(item, Image):
                        item.deregister()
                    elif isinstance(item, Reservation):
                        self.terminate_instances(item)
                    elif isinstance(item, Volume):
                        try:
                            self.detach_volume(item)
                        except:
                            pass
                        self.delete_volume(item)
                    else:
                        item.delete()
                except Exception, e:
                    self.fail("Unable to delete item: " + str(item) + "\n" + str(e))
                    
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
            self.testconf = EuConfig(filepath)
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
               
                ### We dont want to login to ESX boxes
                if re.search("vmware", machine_dict["distro"], re.IGNORECASE):
                    connect=False
                else:
                    connect=True
                ### ADD the machine to the array of machine
                cloud_machine = Machine(   machine_dict["hostname"], 
                                        distro = machine_dict["distro"], 
                                        distro_ver = machine_dict["distro_ver"], 
                                        arch = machine_dict["arch"], 
                                        source = machine_dict["source"], 
                                        components = machine_dict["components"],
                                        connect = connect,
                                        password = self.password,
                                        keypath = self.keypath,
                                        username = username
                                        )
                machines.append(cloud_machine)
                
            ### LOOK for network mode in config file if not found then set it unknown
            try:
                if re.search("^network",line, re.IGNORECASE):
                    config_hash["network"] = line.split()[1].lower()
            except:
                self.debug("Could not find network type setting to unknown")
                config_hash["network"] = "unknown"
        #f.close()   
        config_hash["machines"] = machines 
        return config_hash
    
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
        if self.walrus is all_walruses[0]: 
            self.debug("Swapping Walrus from " + all_walruses[0].hostname + " to " + all_walruses[1].hostname)
            self.walrus = all_walruses[1]
        elif self.walrus is all_walruses[1]:
            self.debug("Swapping Walrus from " + all_walruses[1].hostname + " to " + all_walruses[0].hostname)
            self.walrus = all_walruses[0]
            
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
         
    def get_component_machines(self, component):
        #loop through machines looking for this component type
        """ Parse the machine list and a list of bm_machine objects that match the component passed in"""
        component.lower()
        machines_with_role = [machine for machine in self.config['machines'] if re.search(component, " ".join(machine.components))]
        if len(machines_with_role) == 0:
            raise Exception("Could not find component "  + component + " in list of machines")
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
        self.debug("Downloading credentials from " + self.clc.hostname)
        self.sftp.get(admin_cred_dir + "/creds.zip" , admin_cred_dir + "/creds.zip")
        os.system("unzip -o " + admin_cred_dir + "/creds.zip -d " + admin_cred_dir )
    
    def send_creds_to_machine(self, admin_cred_dir, machine):
        self.debug("Sending credentials to " + machine.hostname)
        try:
            machine.sftp.listdir(admin_cred_dir + "/creds.zip")
            self.debug("Machine " + machine.hostname + " already has credentials in place")
        except IOError, e:
            machine.sys("mkdir " + admin_cred_dir)
            machine.sftp.put( admin_cred_dir + "/creds.zip" , admin_cred_dir + "/creds.zip")
            machine.sys("unzip -o " + admin_cred_dir + "/creds.zip -d " + admin_cred_dir )
            machine.sys("sed -i 's/" + self.clc.hostname + "/" + machine.hostname  +"/g' " + admin_cred_dir + "/eucarc")
            
        
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
    

    
