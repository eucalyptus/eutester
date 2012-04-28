#!/usr/bin/env python
#
# Description:  This case was developed to test the integrity of iptables upon
#               deletion of security groups. Based up the arguments passed, the test 
#               creates at least 3 security groups and launches an instance for each one.
#               Once each instance has been launched, a snapshot of iptables is taken.
#               Then each instance is terminated, followed by each security group being terminated.
#		Another snapshot of iptables is done.  There is a comparison of iptables. 
#		The results are logged. 
#

from eucaops import Eucaops
import argparse
import random
import os
import unittest
import time
import string
import re
import sys
import pprint

class ClusterBasics(unittest.TestCase):
    def setUp(self):
        self.options = options

        ### Make sure --config_file or --credpath is provied
        self.got_creds = False
        while self.got_creds == False:      
            try:
	        if self.options.config_file:
            	    self.tester = Eucaops(config_file=self.options.config_file, password=self.options.password)
	        elif self.options.credpath:
            	    self.tester = Eucaops(credpath=self.options.credpath, password=self.options.password)
                else:
		    print "\tNeed to pass either --credpath or --config_file option. Try --help for more information"	
		    exit(1)
            except Exception,e:
                print str(e) 
                self.time.sleep(30)
                continue
            self.got_creds = True

        self.tester.start_euca_logs()

    def tearDown(self):
        ### Clean up after running test case
        self.tester.delete_keypair(self.keypair)
        os.remove(self.keypath)
        self.tester.stop_euca_logs()
        self.tester.save_euca_logs()
        self.keypath = None
        self.keypair = None
        self.tester = None
        self.image = None
        self.options = None
        self.got_creds = None
        self.time = None
        self.num_vms = None
        self.available = None
        self.security_groups = None

    ### Test Cases ###
    def iptables_Cruft(self):
        ### Launch number of instances based upon number of security groups wanting to be tested.

        ## If specific image wants to be tested, use that; if not, use any instance-store backed image.
        if (self.options.image):
    	    self.image = self.tester.get_emi(emi=self.options.image)
        else:
	    self.image = self.tester.get_emi(root_device_type="instance-store")

        self.keypair = self.tester.add_keypair(self.options.prefix + "-" + str(time.time())) 
        self.keypath = os.curdir + "/" + self.keypair.name + ".pem"

        ### Identify type of instance to run
        if self.options.type == "random":
                self.options.type = random.choice(["m1.small","c1.medium","m1.large","m1.xlarge","c1.xlarge"])
            
        ### Identify number of instances to run (i.e. number of security groups)
        self.num_vms = self.tester.get_available_vms(self.options.type)

	if self.num_vms >= self.options.number:
            self.available = self.options.number
        else:
            self.options.type = "m1.small"
            avail_vms = self.tester.get_available_vms(self.options.type)
            if avail_vms < self.options.number:
                self.tester.fail("Not enough m1.small vm types to run test with minimal of 3 security groups.")
            else:
                self.available = self.options.number

        ### Take snapshot of iptables before creating security groups and launching instances.
        self.pre_iptables = self.tester.sys("iptables-save | grep -v \"#\" | grep -v \"\:PRE\" | grep -v \"\:POST\" | grep -v \"\:INPUT\" | grep -v \"\:FORWARD\" | grep -v \"\:OUT\"")
        self.assertNotEqual(len(self.pre_iptables), 0, "pre_Iptables_Snapshot failed.")
            
        ### Create security group for number of security groups we want to test.
	self.security_groups = []
	while self.available > 0:
            ### Create unique security group and authorize SSH and PING
            reservation = None
            sec_group = None
            sec_group = self.tester.add_group(group_name=self.options.prefix + "-" + str(time.time()))
            self.assertNotEqual(len(sec_group.name), 0, "Could not create group.")
            self.assertTrue(self.tester.authorize_group_by_name(group_name=sec_group.name),
                    "Could not authorize group for SSH")
            self.assertTrue(self.tester.authorize_group_by_name(group_name=sec_group.name, port=-1, protocol="icmp" ),
                    "Could not authorize group for PING")
            self.security_groups.append(sec_group)
          
            ### Launch instance for the unique security group 
            try:
               reservation = self.tester.run_instance(self.image,keypair=self.keypair.name, group=sec_group.name ,type=self.options.type)  
            except Exception, e:
               self.fail("Caught an exception when running the instance: " + str(e))

            for instance in reservation.instances:
                ### Wait for instance to run; error otherwise
                self.assertTrue(self.tester.wait_for_reservation(reservation) ,'Instance did not go to running')

                ### Ping the instance
                ping_result = self.tester.ping(instance.public_dns_name)
                self.assertTrue(ping_result, "Ping to instance failed.")
               
                ### If test is running from Eucalyptus component, access instance and run "uname -a" 
                if (self.options.config_file):
                    uname_result = instance.sys("uname -a")
                    self.assertNotEqual(len(uname_result), 0, "uname -a failed.")

            ### Decrement count of security groups and instances left to create
	    self.available -= 1 


        ### Loop through and terminate instances                
        ### Grab total number of instances ran from by test case
        total_reservations = self.tester.ec2.get_all_instances()
        ### Terminate each instance
        for reservation in total_reservations:
            self.assertTrue(self.tester.terminate_instances(reservation), "Failure when terminating instance.")

        ### Loop through and delete security groups                
        for group in self.security_groups: 
            self.assertTrue(self.tester.delete_group(group), "Failure when deleting group " + group.name)

        ### Take snapshot of iptables after deleting security groups and launching instances.
        self.post_iptables = self.tester.sys("iptables-save | grep -v \"#\" | grep -v \"\:PRE\" | grep -v \"\:POST\" | grep -v \"\:INPUT\" | grep -v \"\:FORWARD\" | grep -v \"\:OUT\"")
        self.assertNotEqual(len(self.post_iptables), 0, "post_Iptables_Snapshot failed.")

        ### Evaluate pre and post iptables outputs to see if there is a difference.
        if (len(self.pre_iptables) != len(self.post_iptables)):
            ## Get different lines and print them

            iptables_diff = set(self.post_iptables) - set(self.pre_iptables)
            pp = pprint.PrettyPrinter(indent=4)

            print "\n======================================\n" 
            print "Diffences between iptables snapshots: " 
            print "PRE-IPTABLES SNAPSHOT LENGTH: " + str(len(self.pre_iptables))
            print "POST-IPTABLES SNAPSHOT LENGTH: " + str(len(self.post_iptables))
            print "\n---------------------------------------\n"
            pp.pprint(list(iptables_diff))
            print "\n======================================\n" 
        else:
            print "\n======================================\n" 
            print "No difference between iptables."
            print "PRE-IPTABLES SNAPSHOT LENGTH: " + str(len(self.pre_iptables))
            print "POST-IPTABLES SNAPSHOT LENGTH: " + str(len(self.post_iptables))
            print "\n======================================\n" 

def get_options():
    ### Parse args
    parser = argparse.ArgumentParser(prog="iptables_security_group_test.py", 
        version="Test Case [iptables_security_group_test.py] Version 0.1.1",
        description="Run an iterative test of operations on a cloud to test integrity of iptables \
            state upon deletion of security groups.  For more information, please refer to \
            https://github.com/hspencer77/eutester/wiki/iptables_security_group_test")
    parser.add_argument("-n", "--number", dest="number", type=int,
        help="Number of security groups to create", default=3)
    parser.add_argument("-e", "--exit", action="store_true", dest="exit_on_fail",
        help="Whether or not to stop the script after a failure")
    parser.add_argument("-i", "--image", dest="image", 
        help="Specific image to run", default=None)
    parser.add_argument("-t", "--type",  dest="type",
        help="Type of instance to launch Default: random", default="random")
    parser.add_argument( "--prefix", dest="prefix", 
        help="Prefix to tack on to keypairs", default="iptables-secgrp-test")
    parser.add_argument("-z", "--zone",  dest="zone",
        help="AZ to run script against", default="PARTI00")
    parser.add_argument("-u", "--user",  dest="user",
        help="User to run script as", default="admin")
    parser.add_argument("-a", "--account",  dest="account",
        help="Account to run script as", default="eucalyptus")
    parser.add_argument("-U", "--username",  dest="username",
        help="User account on physical CC machine", default="root")
    parser.add_argument("-P", "--password",  dest="password",
        help="Password for user account on physical CC machine", default=None)
    parser.add_argument("--config_file",  dest="config_file",
        help="Cloud config of AZ", default=None)
    parser.add_argument("--credpath",  dest="credpath",
        help="AZ to run script against", default=None)
    parser.add_argument('unittest_args', nargs='*')

    ## Grab arguments passed via commandline
    options = parser.parse_args() 
    sys.argv[1:] = options.unittest_args
    return options

if __name__ == '__main__':
    options = get_options()
    tests = ['iptables_Cruft']
    for test in tests:
        result = unittest.TextTestRunner(verbosity=2).run(ClusterBasics(test)) 
        if result.wasSuccessful():
            pass
        else:
            exit(1)
