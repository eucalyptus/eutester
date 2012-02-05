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
import paramiko
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
    def __init__(self, config_file=None, hostname=None, password=None, keypath=None, credpath=None, aws_access_key_id=None, aws_secret_access_key = None, account="eucalyptus",  user="admin", boto_debug=2):
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
        
        ##### LOGGING 
        self.cloud_log_buffer = ''
        self.cc_log_buffer  = ''
        self.nc_log_buffer = ''
        self.cloud_log_process = None
        self.cc_log_process = None
        self.nc_log_process = None
        ### EUCALOGGER
        self.logger = eulogger.Eulogger(name='euca').log
        
        ### LOGS to keep for printing later
        self.fail_log = []
        self.running_log = []
        
        ### SSH Channels for tailing log files
        self.cloud_log_channel = None
        self.cc_log_channel= None
        self.nc_log_channel= None
       
        
        ## CHOOSE A RANDOM HOST OF THIS COMPONENT TYPE
        
        ### If I have a config file
        ### PRIVATE CLOUD
        if self.config_file != None:
            ## read in the config file
            self.config = self.read_config(config_file)
            
            ### Set the eucapath
            if "REPO" in self.config["machines"][0].source:
                self.eucapath="/"
            ### swap in the hostname of the component 
            self.hostname = self.swap_component_hostname(self.hostname)
        
        ## IF I WASNT PROVIDED KEY TRY TO GET THEM FROM THE EUCARC IN CREDPATH
        ### PRIVATE CLOUD
        if (self.password != None) or (self.keypath != None):
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())            
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

    def read_config(self, filepath):
        config_hash = {}
        machines = []
        f = None
        try:
            f = open(filepath, 'r')
        except IOError as (errno, strerror):
            self.tee( "ERROR: Could not find config file " + self.config_file)
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
    
    def start_euca_logs(self):
        """CURRENTLY ONLY WORKS ON CC00 AND CLC AND  the first NC00""" 
        self.tee( "Starting logging")
        previous_ssh = self.current_ssh
        ## START CLOUD Log       
        self.swap_ssh("clc")        
        self.cloud_log_channel = self.ssh.invoke_shell()
        self.cloud_log_channel.send("tail -f "  + self.eucapath + "/var/log/eucalyptus/cloud-output.log > cloud-test.log & \n")
        ## START CC Log
        self.swap_ssh("cc00")
        self.cc_log_channel = self.ssh.invoke_shell()
        self.cc_log_channel.send("tail -f "  + self.eucapath + "/var/log/eucalyptus/cc.log > cc-test.log &\n") 
        self.cc_log_channel.close()
        #self.cc_log_process = Thread(target=poll_euca_logs, args=(self, "cc00",))      
        #self.cc_log_process.start()
        ## START NC LOG
        self.swap_ssh("nc00") 
        self.nc_log_channel = self.ssh.invoke_shell()
        self.nc_log_channel.send("tail -f "  + self.eucapath + "/var/log/eucalyptus/nc.log > nc-test.log &\n")
        self.nc_log_channel.close()
        #self.nc_log_process = Thread(target=poll_euca_logs, args=(self,"nc00",))   
        #self.nc_log_process.start()
        self.swap_ssh(previous_ssh)
        
    def get_euca_logs(self, component="cloud"):
        ## in case there is any delay in the logs propagating
        #if component == "cloud": 
            print "Gathering log on CLC"
            previous_ssh = self.current_ssh
            ## START CLOUD Log       
            self.swap_ssh("clc") 
            self.cloud_log_buffer = "\n".join(self.sys("tail -200 "  + self.eucapath + "/var/log/eucalyptus/cloud-output.log",verbose=0))
        #if component == "cc00":
            print "Gathering log on CC00"
            self.swap_ssh("cc00")
            self.cc_log_buffer = "\n".join(self.sys("tail -200 "  + self.eucapath + "/var/log/eucalyptus/cc.log",verbose=0))
        #if component == "nc00":
            print "Gathering log on NC00"
            self.swap_ssh("nc00") 
            self.nc_log_buffer = "\n".join(self.sys("tail -200 "  + self.eucapath + "/var/log/eucalyptus/nc.log",verbose=0))
            self.swap_ssh(previous_ssh)
                
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
        full_report.append("Running Log: " + "\n".join(self.running_log) + "\n\n\n")
        full_report.append("CLC Log:\n" + self.cloud_log_buffer + "\n\n\n") 
        full_report.append("CC00 Log:\n" + self.cc_log_buffer + "\n\n\n")
        full_report.append("NC00 Log:\n" + self.nc_log_buffer + "\n\n\n")
        self.cloud_log_buffer = ''
        self.cc_log_buffer = ''
        self.nc_log_buffer = ''
        return full_report
        
    def swap_ssh(self, hostname, password=None, keypath=None):
        self.ssh = self.create_ssh(hostname, password=password, keypath=keypath, username="root")
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
        #print "Using timeout of " + str(timeout)
        time.sleep(self.delay)
        old = signal.signal(signal.SIGALRM, self.handle_timeout) 
        signal.alarm(timeout) 
        cur_time = time.strftime("%I:%M:%S", time.gmtime())
        output = []
        std_out_return = []
        if verbose:
            if self.ssh == None:
                self.hostname ="localhost"
            self.tee( "[root@" + str(self.hostname) + "-" + str(cur_time) +"]# " + cmd)
        try:
            
            if self.ssh == None:
                for item in os.popen("ls").readlines():
                    if re.match(self.credpath,item):
                        cmd = ". " + self.credpath + "/eucarc && " + cmd
                        break
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
            self.tee("".join(std_out_return))
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
    
    def tee(self, message):
        print message
        self.running_log.append(message)
        
    
    def diff(self, list1, list2):
        return [item for item in list1 if not item in list2]
    
    def test_name(self, message):
        self.tee("[TEST_REPORT] " + message)
    
    def fail(self, message):
        self.tee( "[TEST_REPORT] FAILED: " + message)
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
        self.tee( exit_report)
        #try:
        #    subprocess.call(["rm", "-rf", self.credpath])
        #except Exception, e:
        #    print "No need to delete creds"
            
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
