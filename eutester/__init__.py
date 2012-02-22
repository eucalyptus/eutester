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

from bm_machine import bm_machine
import eulogger

class TimeoutFunctionException(Exception): 
    """Exception to raise on a timeout""" 
    pass 

class Eutester(object):
    def __init__(self, config_file=None, hostname=None, password=None, keypath=None, credpath=None, aws_access_key_id=None, aws_secret_access_key = None, account="eucalyptus",  user="admin", boto_debug=0):
        """  
        EUCADIR => $eucadir, 
        VERIFY_LEVEL => $verify_level, 
        TOOLKIT => $toolkit, 
        DELAY => $delay, 
        FAIL_COUNT => $fail_count, 
        INPUT_FILE => $input_file, 
        PASSWORD => $password }
        , credpath=None, timeout=30, exit_on_fail=0
        EucaTester takes 2 arguments to their constructor
        1. Configuration file to use
        2. Eucalyptus component to connect to [CLC NC00 SC WS CC00] or a hostname
        3. Password to connect to the host
        4. 
        """
        
        ### Default values for configuration
        self.config_file = config_file 
        self.eucapath = "/opt/eucalyptus"
        self.current_ssh = "clc"
        self.boto_debug = boto_debug
        self.ssh = None
        self.hostname = hostname
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
        
        ##### Euca Logs 
        self.cloud_log_buffer = ''
        self.cc_log_buffer  = ''
        self.nc_log_buffer = ''
        self.sc_log_buffer = ''
        self.walrus_log_buffer = ''
        self.logging_thread = False
        
        ### Eutester logs
        self.logger = eulogger.Eulogger(name= "eutester")
        self.debug = self.logger.log.debug
        self.critical = self.logger.log.critical
        self.info = self.logger.log.info
        ### LOGS to keep for printing later
        self.fail_log = []
        self.running_log = self.logger.log
        
        ### SSH Channels for tailing log files
        self.cloud_log_channel = None
        self.cc_log_channel= None
        self.nc_log_channel= None
        
        ### If I have a config file
        ### PRIVATE CLOUD
        if self.config_file != None:
            ## read in the config file
            self.debug("Reading config file: " + config_file)
            self.config = self.read_config(config_file)
            ### Set the eucapath
            if "REPO" in self.config["machines"][0].source:
                self.eucapath="/"
            ### swap in the hostname of the component 
            self.hostname = self.swap_component_hostname(self.current_ssh)
            self.debug("Hostname for SSH connection: " + self.hostname)
            
        ## IF I WASNT PROVIDED KEY TRY TO GET THEM FROM THE EUCARC IN CREDPATH
        ### PRIVATE CLOUD
        if (self.password != None) or (self.keypath != None):
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.debug("Issuing SSH connection root@" +  self.hostname )            
            if keypath == None:   
                client.connect(self.hostname, username="root", password=password, timeout= self.timeout)
            else:
                client.connect(self.hostname,  username="root", key_filename=keypath, timeout= self.timeout)
            self.ssh = client
            self.sftp = self.ssh.open_sftp()
            
        
        ### If i have an ssh session and its to the clc
        ### Private cloud with root access
        if (self.credpath == None) and (self.ssh != None) and (self.password != None):
                self.credpath = self.get_credentials(account,user) 
        

        ### If i have a credpath
        if (self.credpath != None):         
            aws_access_key_id = self.get_access_key()
            aws_secret_access_key = self.get_secret_key()
                 
        ### If you have credentials for the boto connections, create them
        if (aws_access_key_id != None) and (aws_secret_access_key != None):
           self.ec2 = boto.connect_ec2(aws_access_key_id=aws_access_key_id,
                                        aws_secret_access_key=aws_secret_access_key,
                                        is_secure=False,
                                        api_version = '2009-11-30',
                                        region=RegionInfo(name="eucalyptus", endpoint=self.get_clc_ip()),
                                        port=8773,
                                        path="/services/Eucalyptus",
                                        debug=self.boto_debug)
           self.walrus = boto.connect_s3(aws_access_key_id=aws_access_key_id,
                                          aws_secret_access_key=aws_secret_access_key,
                                          is_secure=False,
                                          host=self.get_walrus_ip(),
                                          port=8773,
                                          path="/services/Walrus",
                                          calling_format=OrdinaryCallingFormat(),
                                          debug=self.boto_debug)
           self.euare = boto.connect_iam(aws_access_key_id=aws_access_key_id,
                                          aws_secret_access_key=aws_secret_access_key,
                                          is_secure=False,
                                          host=self.get_clc_ip(),
                                          port=8773,
                                          path="/services/Euare",
                                          debug=self.boto_debug)
    
    def __del__(self):
        self.logging_thread = False
    
    def read_config(self, filepath):
        config_hash = {}
        machines = []
        f = None
        try:
            f = open(filepath, 'r')
        except IOError as (errno, strerror):
            self.debug( "ERROR: Could not find config file " + self.config_file)
            exit(1)
            
        for line in f:
            ### LOOK for the line that is defining a machine description
            line = line.strip()
            re_machine_line = re.compile(".*\[.*]")
            if re_machine_line.match(line):
                #print "Matched Machine :" + line
                machine_details = line.split(None, 5)
                machine_dict = {}
                machine_dict["hostname"] = machine_details[0]
                machine_dict["distro"] = machine_details[1]
                machine_dict["distro_ver"] = machine_details[2]
                machine_dict["arch"] = machine_details[3]
                machine_dict["source"] = machine_details[4]
                machine_dict["components"] = map(str.lower, machine_details[5].strip('[]').split())
                ### ADD the machine to the array of machine
                machine = bm_machine(machine_dict["hostname"], machine_dict["distro"], machine_dict["distro_ver"], machine_dict["arch"], machine_dict["source"], machine_dict["components"])
                machines.append(machine)
               # print machine
            if line.find("NETWORK"):
                config_hash["network"] = line.strip()
        config_hash["machines"] = machines 
        return config_hash

    def get_component_ip(self, component):
        #loop through machines looking for this component type
        component.lower()
        machines_with_role = [machine.hostname for machine in self.config['machines'] if component in machine.components]
        if len(machines_with_role) == 0:
            raise Exception("Could not find component "  + component + " in list of machines")
        else:
             return machines_with_role[0]
         
    def get_component_machines(self, component):
        #loop through machines looking for this component type
        component.lower()
        machines_with_role = [machine.hostname for machine in self.config['machines'] if component in machine.components]
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
       
    def get_credentials(self, account, user):
        admin_cred_dir = "eucarc-" + account + "-" + user
        self.sys("rm -rf " + admin_cred_dir)
        self.sys("mkdir " + admin_cred_dir)
        cmd_download_creds = self.eucapath + "/usr/sbin/euca_conf --get-credentials " + admin_cred_dir + "/creds.zip " + "--cred-user "+ user +" --cred-account " + account 
        cmd_setup_cred_dir = ["rm -rf " + admin_cred_dir,"mkdir " + admin_cred_dir ,  cmd_download_creds, "unzip -o " + admin_cred_dir + "/creds.zip " + "-d " + admin_cred_dir]
        for cmd in cmd_setup_cred_dir:         
            stdout = self.sys(cmd, verbose=1)
        os.system("rm -rf " + admin_cred_dir)
        os.mkdir(admin_cred_dir)
        self.sftp.get(admin_cred_dir + "/creds.zip" , admin_cred_dir + "/creds.zip")
        os.system("unzip -o " + admin_cred_dir + "/creds.zip -d " + admin_cred_dir )
        return admin_cred_dir
        
    def get_access_key(self):
        return self.parse_eucarc("EC2_ACCESS_KEY")   
    
    def get_secret_key(self):
       return self.parse_eucarc("EC2_SECRET_KEY")
    
    def get_account_id(self):
        return self.parse_eucarc("EC2_ACCOUNT_NUMBER")
        
    def parse_eucarc(self, field):
        with open( self.credpath + "/eucarc") as eucarc:
            for line in eucarc.readlines():
                if re.search(field, line):
                    return line.split("=")[1].strip().strip("'")
            raise Exception("Unable to find account id in eucarc")
    
    def get_walrus_ip(self):
        walrus_url = self.parse_eucarc("S3_URL")
        return walrus_url.split("/")[2].split(":")[0]
    
    def get_clc_ip(self):
        ec2_url = self.parse_eucarc("EC2_URL")
        return ec2_url.split("/")[2].split(":")[0]        
        
    def connect_euare(self):
        self.euare = boto.connect_iam(aws_access_key_id=self.get_access_key(),
                                    aws_secret_access_key=self.get_secret_key(),
                                    is_secure=False,
                                    host=self.get_component_ip("clc"),
                                    port=8773,
                                    path="/services/Euare")
        
    def create_ssh(self, hostname, password=None, keypath=None, username="root"):
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
    
    def poll_euca_logs(self):
        self.debug( "Starting logging")
        ## START CLOUD Log
        cloud_ssh =  self.create_ssh("clc", password=self.password)          
        self.cloud_log_channel = cloud_ssh.invoke_shell()
        self.cloud_log_channel.send("tail -f "  + self.eucapath + "/var/log/eucalyptus/cloud-output.log \n")
        ### START WALRUS Log    
        walrus_ssh =  self.create_ssh("ws", password=self.password)
        self.walrus_log_channel = walrus_ssh.invoke_shell()
        self.walrus_log_channel.send("tail -f "  + self.eucapath + "/var/log/eucalyptus/cloud-output.log \n")
        ## START CC Log
        cluster_ssh =  self.create_ssh("cc00", password=self.password)
        self.cc_log_channel = cluster_ssh.invoke_shell()
        self.cc_log_channel.send("tail -f "  + self.eucapath + "/var/log/eucalyptus/cc.log \n")
        ## START SC Log
        storage_ssh =  self.create_ssh("sc00", password=self.password)
        self.sc_log_channel = storage_ssh.invoke_shell()
        self.sc_log_channel.send("tail -f "  + self.eucapath + "/var/log/eucalyptus/cloud-output.log \n")
        ## START NC LOG
        nc_ssh =  self.create_ssh("nc00", password=self.password)
        self.nc_log_channel = nc_ssh.invoke_shell()
        self.nc_log_channel.send("tail -f "  + self.eucapath + "/var/log/eucalyptus/nc.log \n")
        self.logging_thread = True
        
        ### Begin polling channel for any new data
        while self.logging_thread:
            ### CLOUD LOG
            rl, wl, xl = select.select([self.cloud_log_channel],[],[],0.0)
            if len(rl) > 0:
                self.cloud_log_buffer += self.cloud_log_channel.recv(1024)
            ### CC LOG
            rl, wl, xl = select.select([self.cc_log_channel],[],[],0.0)
            if len(rl) > 0:
                self.cc_log_buffer += self.cc_log_channel.recv(1024)
            ### SC LOG
            rl, wl, xl = select.select([self.sc_log_channel],[],[],0.0)
            if len(rl) > 0:
                self.sc_log_buffer += self.sc_log_channel.recv(1024)
            ### WALRUS LOG
            rl, wl, xl = select.select([self.walrus_log_channel],[],[],0.0)
            if len(rl) > 0:
                self.walrus_log_buffer += self.walrus_log_channel.recv(1024)
            ### NC LOG
            rl, wl, xl = select.select([self.nc_log_channel],[],[],0.0)
            if len(rl) > 0:
                self.nc_log_buffer += self.nc_log_channel.recv(1024)
            self.sleep(1)
            
    def start_euca_logs(self):
        '''Start thread to poll logs''' 
        threading.Thread(target=self.poll_euca_logs, args=()).start()
        
    def stop_euca_logs(self):
        '''Terminate thread that is polling logs''' 
        self.logging_thread = False
        
    def save_euca_logs(self):
        '''Save log buffers to a file''' 
        FILE = open("clc.log","w")
        FILE.writelines(self.cloud_log_buffer)
        FILE.close()
        FILE = open("walrus.log","w")
        FILE.writelines(self.walrus_log_buffer)
        FILE.close()
        FILE = open("cc.log","w")
        FILE.writelines(self.cc_log_buffer)
        FILE.close()
        FILE = open("sc.log","w")
        FILE.writelines(self.sc_log_buffer)
        FILE.close()
        FILE = open("nc.log","w")
        FILE.writelines(self.nc_log_buffer)
        FILE.close()
            
                
    def grep_euca_log(self,component="cloud", regex="ERROR" ):
        previous_ssh = self.current_ssh
        if component == "cloud":
            self.swap_ssh("clc")
            log = self.sys("cat "  + self.eucapath + "/var/log/eucalyptus/cloud-output.log | grep " + regex)
            self.swap_ssh(previous_ssh)
            return log
        if component == "cc00":
            self.swap_ssh("cc00")
            log = self.sys("cat "  + self.eucapath + "/var/log/eucalyptus/cc.log | grep " + regex)
            self.swap_ssh(previous_ssh)
            return log
        if component == "nc00":
            self.swap_ssh("nc00")
            log = self.sys("cat "  + self.eucapath + "/var/log/eucalyptus/nc.log | grep " + regex)
            self.swap_ssh(previous_ssh)
            return log
        
    def test_report(self):
        full_report = []
        self.get_euca_logs()
        full_report.append("Test run started at " + str(self.start_time) + "\n\n\n")
        full_report.append("Failures " + str(self.fail_count) + "\n")
        full_report.append("CLC Log:\n" + self.cloud_log_buffer + "\n\n\n") 
        full_report.append("CC00 Log:\n" + self.cc_log_buffer + "\n\n\n")
        full_report.append("NC00 Log:\n" + self.nc_log_buffer + "\n\n\n")
        self.cloud_log_buffer = ''
        self.cc_log_buffer = ''
        self.nc_log_buffer = ''
        return full_report
        
    def swap_ssh(self, hostname, password=None, keypath=None):
        self.ssh = self.create_ssh(hostname, password=password, keypath=keypath, username="root")
        self.sftp = self.ssh.open_sftp()
        self.current_ssh = hostname
        return self.ssh               
                               
    def handle_timeout(self, signum, frame): 
        raise TimeoutFunctionException()
    
    def sys(self, cmd, verbose=1, timeout=-2):
        cmd = str(cmd)
        # default timeout is to use module-defined timeout
        # -1 should be reserved for "no timeout" option
        if timeout == -2:
            timeout = self.timeout
        time.sleep(self.delay)
        old = signal.signal(signal.SIGALRM, self.handle_timeout) 
        signal.alarm(timeout) 
        cur_time = time.strftime("%I:%M:%S", time.gmtime())
        output = []
        std_out_return = []
        if verbose:
            if self.ssh == None:
                self.hostname ="localhost"
            self.debug( "[root@" + str(self.hostname) + "]# " + cmd)
        try:
            
            if self.ssh == None:
                for item in os.popen("ls").readlines():
                    if re.match(self.credpath,item):
                        cmd = ". " + self.credpath + "/eucarc && " + cmd
                std_out_return = os.popen(cmd).readlines()
            else:
                stdin_ls, stdout_ls, stderr_ls = self.ssh.exec_command("ls")
                ls_result = stdout_ls.readlines()
                if self.credpath != None:
                    for item in ls_result: 
                        if re.match(self.credpath,item): 
                            cmd = ". " + self.credpath + "/eucarc && " + cmd
                            break
                stdin, stdout, stderr = self.ssh.exec_command(cmd)
                std_out_return = stdout.readlines() 
                output = std_out_return
        except Exception, e: 
            self.fail("Command timeout after " + str(timeout) + " seconds\nException:" + str(e)) 
            return []
        signal.alarm(0)      
        if verbose:
            self.debug("".join(std_out_return))
        return std_out_return

    def found(self, command, regex):
        result = self.sys(command)
        for line in result:
            found = re.search(regex,line)
            if found:
                return True
        return False 
    
    def grep(self, string,list):
        expr = re.compile(string)
        return filter(expr.search,list)
        
    def diff(self, list1, list2):
        return list(set(list1)-set(list2))
    
    def test_name(self, message):
        self.debug("[TEST_REPORT] " + message)
    
    def fail(self, message):
        #self.debug( "[TEST_REPORT] FAILED: " + message)
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
        return time.time() - self.start_time
       
    def clear_fail_count(self):
        self.fail_count = 0

    def do_exit(self):       
        exit_report  = "******************************************************\n"
        exit_report += "*" + "    Failures:" + str(self.fail_count) + "\n"
        for message in self.fail_log:
            exit_report += "*" + "            " + message + "\n"
        exit_report += "*" + "    Time to execute: " + str(self.get_exectuion_time()) +"\n"
        exit_report += "******************************************************\n"           
        self.debug( exit_report)    
        if self.fail_count > 0:
            exit(1)
        else:
            exit(0)
        
    def sleep(self, seconds=1):
        time.sleep(seconds)
        
    def __str__(self):
        s  = "+++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
        s += "+" + "Eucateser Configuration" + "\n"
        s += "+" + "+++++++++++++++++++++++++++++++++++++++++++++++\n"
        s += "+" + "Host:" + self.hostname + "\n"
        s += "+" + "Config File: " + self.config_file +"\n"
        s += "+" + "Fail Count: " +  str(self.fail_count) +"\n"
        s += "+" + "Eucalyptus Path: " +  str(self.eucapath) +"\n"
        s += "+" + "Credential Path: " +  str(self.credpath) +"\n"
        s += "+++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
        return s

