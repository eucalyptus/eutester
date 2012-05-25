#!/usr/bin/python
# -*- coding: utf-8 -*-
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


__version__ = '0.0.1'

import re
import os
import subprocess
import threading
import paramiko
import select
import boto
import random
import time
import signal
import copy 
from threading import Thread

from boto.ec2.regioninfo import RegionInfo
from boto.s3.connection import OrdinaryCallingFormat

from machine import machine
import eulogger
from euservice import EuserviceManager
from euconfig import EuConfig


class TimeoutFunctionException(Exception): 
    """Exception to raise on a timeout""" 
    pass 

EC2RegionData = {
    'us-east-1' : 'ec2.us-east-1.amazonaws.com',
    'us-west-1' : 'ec2.us-west-1.amazonaws.com',
    'eu-west-1' : 'ec2.eu-west-1.amazonaws.com',
    'ap-northeast-1' : 'ec2.ap-northeast-1.amazonaws.com',
    'ap-southeast-1' : 'ec2.ap-southeast-1.amazonaws.com'}

class Eutester(object):
    def __init__(self, config_file=None, password=None, keypath=None, credpath=None, aws_access_key_id=None, aws_secret_access_key = None,  account="eucalyptus", user="admin", region=None, boto_debug=0):
        """  
        This is the constructor for a eutester object, it takes care of setting up the connections that will be required for a test to run. 
        
        """
        
        ### Default values for configuration
        self.config_file = config_file 
        self.eucapath = "/opt/eucalyptus"
        self.current_ssh = "clc"
        self.boto_debug = boto_debug
        self.ssh = None
        self.sftp = None
        self.clc = None
        self.password = password
        self.keypath = keypath
        self.credpath = credpath
        self.timeout = 30
        self.delay = 0
        self.exit_on_fail = 0
        self.fail_count = 0
        self.start_time = time.time()
        self.key_dir = "./"
        self.account_id = 0000000000001
        self.hypervisor = None
        self.region = RegionInfo()
        
        ##### Euca Logs 
        self.cloud_log_buffer = ''
        self.cc_log_buffer  = ''
        self.nc_log_buffer = ''
        self.sc_log_buffer = ''
        self.walrus_log_buffer = ''
        self.logging_thread = False
        
        ### Eutester logs
        self.logger = eulogger.Eulogger(identifier="EUTESTER")
        
            
        self.debug = self.logger.log.debug
        self.critical = self.logger.log.critical
        self.info = self.logger.log.info
        self.logging_thread_pool = []
        ### LOGS to keep for printing later
        self.fail_log = []
        self.running_log = self.logger.log
        
        ### SSH Channels for tailing log files
        self.cloud_log_channel = None
        self.cc_log_channel= None
        self.nc_log_channel= None
        
        self.clc_index = 0

        ### If I have a config file
        ### PRIVATE CLOUD
        if self.config_file != None:
            ## read in the config file
            self.debug("Reading config file: " + config_file)
            self.config = self.read_config(config_file)

            ### Set the eucapath
            try:
                if "REPO" in self.config["machines"][0].source:
                    self.eucapath="/"
            except Exception, e:
                raise Exception("Could not get REPO info from input file\n" + str(e))
            #self.hypervisor = self.get_hypervisor()
            ### No credpath but does have password and an ssh connection to the CLC
            ### Private cloud with root access 
            ### Need to get credentials for the user if there arent any passed in
            ### Need to create service manager for user if we have an ssh connection and password
            if (self.password != None):
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
                        #try:
                        self.credpath = self.get_credentials(account,user)
                        #except Exception, e:
                        #    raise Exception("Could not get credentials from second CLC and no other to try\n" + str(e))
                        
                self.service_manager = EuserviceManager(self)
                self.clc = self.service_manager.get_enabled_clc().machine
                self.walrus = self.service_manager.get_enabled_walrus().machine 
                
            ### Pull the access and secret keys from the eucarc
        if (self.credpath != None):
            self.debug("Extracting keys from " + self.credpath)         
            self.aws_access_key_id = self.get_access_key()
            self.aws_secret_access_key = self.get_secret_key()
                        
            ### If you have credentials for the boto connections, create them
        if (self.aws_access_key_id != None) and (self.aws_secret_access_key != None):
            if not boto.config.has_section('Boto'):
                boto.config.add_section('Boto')
            boto.config.set('Boto', 'num_retries', '2')  
            self.setup_boto_connections(region=region)
        
    def __del__(self):
        self.logging_thread = False
    
    
    def setup_boto_connections(self, region=None, aws_access_key_id=None, aws_secret_access_key=None, clc_ip=None, walrus_ip=None, is_secure=False):
        
        if aws_access_key_id is None:
            aws_access_key_id = self.aws_access_key_id
        if aws_secret_access_key is None:
            aws_secret_access_key = self.aws_secret_access_key     
        port = 443
        service_path = "/"
        APIVersion = '2009-11-30'

        if region is not None:
            self.debug("Check region: " + str(region))        
            try:
                self.region.endpoint = EC2RegionData[region]
            except KeyError:
                raise Exception( 'Unknown region: %s' % region)
        
        if not self.region.endpoint:
            #self.get_connection_details()
            self.region.name = 'eucalyptus'
            self.region.endpoint = self.get_ec2_ip()       
            port = 8773
            service_path="/services/Eucalyptus"
            
        if walrus_ip is None:
            walrus_ip = self.get_walrus_ip()
        
        try:    
            self.ec2 = boto.connect_ec2(aws_access_key_id=aws_access_key_id,
                                    aws_secret_access_key=aws_secret_access_key,
                                    is_secure=is_secure,
                                    debug=self.boto_debug,
                                    region=self.region,
                                    port=port,
                                    path=service_path,
                                    api_version=APIVersion)
        except Exception, e:
            self.critical("Was unable to create ec2 connection because of exception: " + str(e))

        try:
            self.s3 = boto.connect_s3(aws_access_key_id=aws_access_key_id,
                                                  aws_secret_access_key=aws_secret_access_key,
                                                  is_secure=False,
                                                  host=walrus_ip,
                                                  port=8773,
                                                  path="/services/Walrus",
                                                  calling_format=OrdinaryCallingFormat(),
                                                  debug=self.boto_debug)
        except Exception, e:
            self.critical("Was unable to create S3 connection because of exception: " + str(e))
        
        try:    
            self.euare = boto.connect_iam(aws_access_key_id=aws_access_key_id,
                                                  aws_secret_access_key=aws_secret_access_key,
                                                  is_secure=False,
                                                  host=self.get_ec2_ip(),
                                                  port=8773, 
                                                  path="/services/Euare",
                                                  debug=self.boto_debug)
        except Exception, e:
            self.critical("Was unable to create IAM connection because of exception: " + str(e))
            
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
                ### ADD the machine to the array of machine
                cloud_machine = machine(   machine_dict["hostname"], 
                                        machine_dict["distro"], 
                                        machine_dict["distro_ver"], 
                                        machine_dict["arch"], 
                                        machine_dict["source"], 
                                        machine_dict["components"],
                                        self.password,
                                        self.keypath,
                                        username
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
        if len(machines) == 0:
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
        
        ### Check if this directory exists already
#        if os.path.exists(full_cred_path):
#            self.debug("No need to redownload credentials as they already exist for this system")
#            self.credpath = admin_cred_dir      
    
        ### IF I wasnt passed in credentials, download and sync them
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
                
        ### sync the keys that were given to all CLCs
        
        for clc in clcs:
            self.send_creds_to_machine(admin_cred_dir, clc)
        
        return admin_cred_dir
    
    def create_credentials(self, admin_cred_dir, account, user):
        cmd_download_creds = self.eucapath + "/usr/sbin/euca_conf --get-credentials " + admin_cred_dir + "/creds.zip " + "--cred-user "+ user +" --cred-account " + account 
        if self.found( cmd_download_creds, "The MySQL server is not responding"):
            raise IOError("Error downloading credentials, looks like CLC was not running")
        if self.found( "unzip -o " + admin_cred_dir + "/creds.zip " + "-d " + admin_cred_dir, "cannot find zipfile directory"):
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
        
    def get_access_key(self):
        """Parse the eucarc for the EC2_ACCESS_KEY"""
        return self.parse_eucarc("EC2_ACCESS_KEY")   
    
    def get_secret_key(self):
        """Parse the eucarc for the EC2_SECRET_KEY"""
        return self.parse_eucarc("EC2_SECRET_KEY")
    
    def get_account_id(self):
        """Parse the eucarc for the EC2_ACCOUNT_NUMBER"""
        return self.parse_eucarc("EC2_ACCOUNT_NUMBER")
        
    def parse_eucarc(self, field):
        with open( self.credpath + "/eucarc") as eucarc: 
            for line in eucarc.readlines():
                if re.search(field, line):
                    return line.split("=")[1].strip().strip("'")
            raise Exception("Unable to find " +  field + " id in eucarc")
    
    def get_walrus_ip(self):
        """Parse the eucarc for the S3_URL"""
        walrus_url = self.parse_eucarc("S3_URL")
        return walrus_url.split("/")[2].split(":")[0]
    
    def get_ec2_ip(self):
        """Parse the eucarc for the EC2_URL"""
        ec2_url = self.parse_eucarc("EC2_URL")
        return ec2_url.split("/")[2].split(":")[0]        
        
    def create_ssh(self, hostname, password=None, keypath=None, username="root"):
        """ Returns a paramiko SSHClient object for the hostname provided, either keypath or password must be provided"""
        hostname = self.swap_component_hostname(hostname)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())            
        if keypath == None:
            if password==None:
                password= self.password
            client.connect(hostname, username=username, password=password)
        else:
            client.connect(hostname,  username=username, key_filename=keypath)
        return client    
                               
    def handle_timeout(self, signum, frame): 
        raise TimeoutFunctionException()
    
    def sys(self, cmd, verbose=True, timeout=120):
        """ By default will run a command on the CLC machine, the connection used can be changed by passing a different hostname into the constructor
            For example:
            instance = Eutester( hostname=instance.ip_address, keypath="my_key.pem")
            instance.sys("mount") # check mount points on instance and return the output as a list
        """
        return self.clc.sys(cmd, verbose=verbose, timeout=timeout)

    def local(self, cmd):
        """ Run a command locally on the tester"""
        for item in os.popen("ls").readlines():
            if re.match(self.credpath,item):
                cmd = ". " + self.credpath + "/eucarc && " + cmd
        std_out_return = os.popen(cmd).readlines()
        return std_out_return
    
    def found(self, command, regex, local=False, timeout=120):
        """ Returns a Boolean of whether the result of the command contains the regex"""
        if self.clc is None:
            local = True 
        if local:
            result = self.local(command)
        else:
            result = self.sys(command, timeout=timeout)
        for line in result:
            found = re.search(regex,line)
            if found:
                return True
        return False 
    
    def grep(self, string,list):
        """ Remove the strings from the list that do not match the regex string"""
        expr = re.compile(string)
        return filter(expr.search,list)
        
    def diff(self, list1, list2):
        """Return the diff of the two lists"""
        return list(set(list1)-set(list2))
    
    def fail(self, message):
        self.critical(message)
        self.fail_log.append(message)
        self.fail_count += 1
        if self.exit_on_fail == 1:
            raise Exception("Test step failed")
        else:
            return 0 
    
    def clear_fail_log(self):
        self.fail_log = []
        return
    
    def get_exectuion_time(self):
        """Returns the total execution time since the instantiation of the Eutester object"""
        return time.time() - self.start_time
       
    def clear_fail_count(self):
        ''' The counter for keeping track of all the errors '''
        self.fail_count = 0

    def do_exit(self):
        """Prints a short sumary of the test including the failure messages and time to execute. Exits 0 if no failures were encountered or 1 if there were"""
        self.debug( "******************************************************")
        self.debug( "*" + "    Failures:" + str(self.fail_count) )
        for message in self.fail_log:
            self.debug( "*" + "            " + message + "\n")
        self.debug( "*" + "    Time to execute: " + str(self.get_exectuion_time()) )
        self.debug( "******************************************************" )          
        if self.fail_count > 0:
            exit(1)
        else:
            exit(0)
        
    def sleep(self, seconds=1):
        """Convinience function for time.sleep()"""
        self.debug("Sleeping for " + str(seconds) + " seconds")
        time.sleep(seconds)
        
    def __str__(self):
        '''
        Prints informations about configuration of Eucateser as configuration file, 
        how many errors, the path of the Eucalyptus, and the path of the user credentials
        '''
        s  = "+++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
        s += "+" + "Eucateser Configuration" + "\n"
        s += "+" + "+++++++++++++++++++++++++++++++++++++++++++++++\n"
        s += "+" + "Config File: " + self.config_file +"\n"
        s += "+" + "Fail Count: " +  str(self.fail_count) +"\n"
        s += "+" + "Eucalyptus Path: " +  str(self.eucapath) +"\n"
        s += "+" + "Credential Path: " +  str(self.credpath) +"\n"
        s += "+++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
        return s

