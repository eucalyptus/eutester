#!/usr/bin/env python
#
#
# Description:  This script encompasses test cases/modules concerning cluster specific actions and
#               features for Eucalyptus.  The test cases/modules that are executed can be 
#               found in the script under the "tests" list.
#
#
##########################
#                        #
#       Test Cases       #
#                        #
##########################
#
# [iptables_Cruft]
#
#               This case was developed to test the integrity of iptables upon
#               deletion of security groups. Based up the arguments passed, the test 
#               creates at least 3 security groups and launches an instance for each one.
#               Once each instance has been launched, a snapshot of iptables is taken.
#               Then each instance is terminated, followed by each security group being terminated.
#		        Another snapshot of iptables is done.  There is a comparison of iptables. 
#		        The results are logged. 
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

options = None

class ClusterBasics(unittest.TestCase):
    def setUp(self):
           
        if options.config_file:
            self.tester = Eucaops(config_file=options.config_file, password=options.clc_password)
        else:
            print "\tNeed to pass --config_file option. Try --help for more information\n"	
            exit(1)
       
        ## If specific image wants to be tested, use that; if not, use any instance-store backed image.
        if options.image:
            self.image = self.tester.get_emi(emi=options.image)
        else:
            self.image = self.tester.get_emi(root_device_type="instance-store")
		
        self.keypair = self.tester.add_keypair(options.prefix + "-" + str(time.time())) 
        self.keypath = os.curdir + "/" + self.keypair.name + ".pem"
	
        ### Identify type of instance to run
        if options.type == "random":
            options.type = random.choice(["m1.small","c1.medium","m1.large","m1.xlarge","c1.xlarge"])
            
        ### Identify number of instances to run (i.e. number of security groups)
        self.num_vms = self.tester.get_available_vms(options.type)

        if self.num_vms >= options.number:
            self.available = options.number
        else:
            options.type = "m1.small"
            avail_vms = self.tester.get_available_vms(options.type)
            if avail_vms < options.number:
                self.tester.fail("Not enough m1.small vm types to run test with minimal of 3 security groups.")
            else:
                self.available = options.number
        
        self.security_groups = []
        self.reservations = []

    def tearDown(self):
        ### Clean up after running test case
        for reservation in self.reservations:
            self.tester.terminate_instances(reservation)
        for security_group in self.security_groups:
            self.tester.delete_group(security_group)
        self.tester.delete_keypair(self.keypair)
        os.remove(self.keypath)
        self.keypath = None
        self.keypair = None
        self.image = None
        self.num_vms = None
        self.available = None
        self.security_groups = None
        self.tester = None

    ### Test Cases ###
    def iptables_Cruft(self):
        ### Launch number of instances based upon number of security groups wanting to be tested.
        ### Take snapshot of iptables before creating security groups and launching instances.
        ### Use service manager to get to enabled CC to get iptables rules
        partition = self.tester.service_manager.partitions.keys()
        part = list(partition)[0]
        main_part = self.tester.service_manager.partitions.get(part)
        cc_machine = main_part.get_enabled_cc()
        cc_shell = self.tester.create_ssh(hostname=cc_machine.hostname, password=options.cc_password)
        pre_stdin, pre_iptables, pre_stderr = cc_shell.exec_command("iptables-save | grep -v \"#\" | grep -v \"\:PRE\" | grep -v \"\:POST\" | grep -v \"\:INPUT\" | grep -v \"\:FORWARD\" | grep -v \"\:OUT\"")

        self.pre_iptables = list(pre_iptables)

        self.assertTrue(pre_stderr, "pre_Iptables_Snapshot failed.")
            
        ### Create security group for number of security groups we want to test.
        
        while self.available > 0:
            ### Create unique security group and authorize SSH and PING
            sec_group = self.tester.add_group(group_name=options.prefix + "-" + str(time.time()))
            self.assertNotEqual(len(sec_group.name), 0, "Could not create group.")
            self.assertTrue(self.tester.authorize_group_by_name(group_name=sec_group.name),
                    "Could not authorize group for SSH")
            self.assertTrue(self.tester.authorize_group_by_name(group_name=sec_group.name, port=-1, protocol="icmp" ),
                 "Could not authorize group for PING")
            self.security_groups.append(sec_group)
          
            ### Launch instance for the unique security group 
            try:
                reservation = self.tester.run_instance(self.image,keypair=self.keypair.name, group=sec_group.name ,type=options.type)  
            except Exception, e:
                self.fail("Caught an exception when running the instance: " + str(e))

            self.reservations.append(reservation)

            ### Decrement count of security groups and instances left to create
            self.available -= 1 

        ### Take snapshot of iptables after deleting security groups and terminating instances.
        ### Use service manager to get to enabled CC to get iptables rules
        partition = self.tester.service_manager.partitions.keys()
        part = list(partition)[0]
        main_part = self.tester.service_manager.partitions.get(part)
        cc_machine = main_part.get_enabled_cc()
        cc_shell = self.tester.create_ssh(hostname=cc_machine.hostname, password=options.cc_password)
        post_stdin, post_iptables, post_stderr = cc_shell.exec_command("iptables-save | grep -v \"#\" | grep -v \"\:PRE\" | grep -v \"\:POST\" | grep -v \"\:INPUT\" | grep -v \"\:FORWARD\" | grep -v \"\:OUT\"")

        self.post_iptables = list(post_iptables)

        self.assertTrue(post_stderr, "post_Iptables_Snapshot failed.")

        ### Evaluate pre and post iptables outputs to see if there is a difference.
        if (len(self.pre_iptables) != len(self.post_iptables)):
            ## Get different lines and print them
            iptables_diff = set(self.post_iptables) - set(self.pre_iptables)
            pp = pprint.PrettyPrinter(indent=4)

            self.tester.critical("\n======================================\n") 
            self.tester.critical("Diffences between iptables snapshots: ") 
            self.tester.critical("PRE-IPTABLES SNAPSHOT LENGTH: %i", len(self.pre_iptables))
            self.tester.critical("POST-IPTABLES SNAPSHOT LENGTH: %i", len(self.post_iptables))
            self.tester.critical("\n---------------------------------------\n")
            pp.pprint(list(iptables_diff))
            self.tester.critical("\n======================================\n")
    
    def ConnectivityTest(self):
        '''
        Test that:
            2 instances in the same security group
                - Instances can ping each other on their private addresses
                - Can ping each other on their public IPs
            2 instances in different groups
                - Cannot ping each other on their private addresses
                - Can ping each other on their public IPs
        '''
        sec_group_a = self.tester.add_group()
        sec_group_b = self.tester.add_group()
        group_a = self.tester.run_instance(self.image,keypair=self.keypair.name, group=sec_group_a.name, number= 2)
        group_b = self.tester.run_instance(self.image,keypair=self.keypair.name, group=sec_group_b.name)
        instance_1a = groupa.instances[0]
        instance_2a = groupa.instances[1]
        instance_1b = groupb.instances[0]
        self.assertTrue(instance_1a.found("ping -c 1 " + instance_2a.public_dns_name, "1 packets received"))
        self.assertTrue(instance_1a.found("ping -c 1 " + instance_2a.private_dns_name, "1 packets received"))
        self.assertTrue(instance_2a.found("ping -c 1 " + instance_1a.public_dns_name, "1 packets received"))
        self.assertTrue(instance_2a.found("ping -c 1 " + instance_1a.private_dns_name, "1 packets received"))
        self.assertFalse(instance_1b.found("ping -c 1 " + instance_1a.private_dns_name, "1 packets received"))
        self.assertFalse(instance_1b.found("ping -c 1 " + instance_2a.private_dns_name, "1 packets received"))
        self.assertTrue(instance_1b.found("ping -c 1 " + instance_1a.public_dns_name, "1 packets received"))
        self.assertTrue(instance_1b.found("ping -c 1 " + instance_2a.public_dns_name, "1 packets received"))
        
        
def get_options():
    ### Parse args
    parser = argparse.ArgumentParser(prog="clusterbasics.py", 
        version="Test Case [clusterbasics.py] Version 0.1.1",
        description="Run an iterative test of operations on a cloud to test Eucalyptus Cluster \
            functionality.  For more information, please refer to \
            https://github.com/hspencer77/eutester/wiki/clusterbasics")
    parser.add_argument("-n", "--number", dest="number", type=int,
        help="Number of security groups to create", default=3)
    parser.add_argument("-i", "--image", dest="image", 
        help="Specific image to run", default=None)
    parser.add_argument("-t", "--type",  dest="type",
        help="Type of instance to launch Default: random", default="random")
    parser.add_argument( "--prefix", dest="prefix", 
        help="Prefix to tack on to keypairs", default="cluster-test")
    parser.add_argument("-z", "--zone",  dest="zone",
        help="AZ to run script against", default="PARTI00")
    parser.add_argument("-U", "--username",  dest="username",
        help="User account on physical CC and CLC machine", default="root")
    parser.add_argument("--clc-password",  dest="clc_password",
        help="Password for user account on physical CLC machine", default=None)
    parser.add_argument("--cc-password",  dest="cc_password",
        help="Password for user account on physical CC machine", default=None)
    parser.add_argument("--config_file",  dest="config_file",
        help="Cloud config of AZ", default=None)
    parser.add_argument("-d", "--debug", action="store_false", dest="print_debug",
        help="Whether or not to print debugging")
    parser.add_argument('--xml', action="store_true", default=False)
    parser.add_argument('--tests', nargs='+', default= ['iptables_Cruft'])
    parser.add_argument('unittest_args', nargs='*')

    ## Grab arguments passed via commandline
    options = parser.parse_args() 
    sys.argv[1:] = options.unittest_args
    return options

if __name__ == "__main__":
    ## If given command line arguments, use them as test names to launch
    options = get_options()
    for test in options.tests:
        if options.xml:
            file = open("test-" + test + "result.xml", "w")
            result = xmlrunner.XMLTestRunner(file).run(ClusterBasics(test))
        else:
            result = unittest.TextTestRunner(verbosity=2).run(ClusterBasics(test))
        if result.wasSuccessful():
            pass
        else:
            exit(1)
