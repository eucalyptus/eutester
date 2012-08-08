#!/usr/bin/python
import unittest
import time
import sys
sys.path.append("../cloud_user/instances/")
sys.path.append("../cloud_user/s3/")
from instancetest import InstanceBasics
from bucket_tests import BucketTestSuite
from eutester.eutestcase import EutesterTestCase
from eucaops import Eucaops 
import os
import re
import random

class HAtests(EutesterTestCase, InstanceBasics, BucketTestSuite):
    def __init__(self, config_file="cloud.conf", password="foobar"):
        self.tester = Eucaops( config_file=config_file, password=password)
        self.servman = self.tester.service_manager
        self.tester.poll_count = 120
        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = os.curdir + "/" + self.keypair.name + ".pem"
        self.image = self.tester.get_emi(root_device_type="instance-store")
        self.reservation = None
        self.private_addressing = False
        self.bucket_prefix = "buckettestsuite-" + str(int(time.time())) + "-"
        self.test_user_id = self.tester.s3.get_canonical_user_id()
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name
    
    def tearDown(self):
        try:
            self.tester.terminate_instances()
        except Exception, e: 
            self.tester.critical("Unable to terminate all instances")
        
        self.servman.start_all()
        
        try:
            super(HAtests, self).tearDown()
        except Exception, e: 
            self.tester.critical("Unable to teardown group and keypair")
            
    def run_testcase(self, testcase_callback, **kwargs):
        poll_count = 10
        poll_interval = 60       
        while (poll_count > 0):
            try:
                testcase_callback(**kwargs)
                break
            except Exception, e:
                self.tester.debug("Attempt failed due to: " + str(e)  + "\nRetrying testcase in " + str(poll_interval) )
            self.tester.sleep(poll_interval)     
            poll_count = poll_count - 1  
        if poll_count is 0:
            self.fail("Could not run an instance after " + str(poll_count) +" tries with " + str(poll_interval) + "s sleep in between")
        
    def failoverService(self, service_aquisition_callback, testcase_callback, **kwargs):
        ### Process Take down
        primary_service = service_aquisition_callback()
        secondary_service = self.tester.service_manager.wait_for_service(primary_service, state="DISABLED")
        self.tester.debug("Primary Service: " + primary_service.machine.hostname + " Secondary Service: " + secondary_service.machine.hostname)
        primary_service.stop()    
        
        if "clc" in primary_service.machine.components:
            self.tester.debug("Switching ec2 connection to host: " +  secondary_service.machine.hostname)
            self.tester.clc = secondary_service.machine
            self.tester.ec2.host = secondary_service.machine.hostname
        
        if "ws" in primary_service.machine.components:
            self.tester.debug("Switching walrus connection to host: " +  secondary_service.machine.hostname)
            self.tester.walrus = secondary_service.machine
            self.tester.s3.DefaultHost = secondary_service.machine.hostname
            
        self.tester.sleep(30)
            
        self.run_testcase(testcase_callback, **kwargs)
        self.tester.terminate_instances(self.reservation)
        after_failover = self.tester.service_manager.wait_for_service(primary_service, state="ENABLED")
          
        if primary_service.hostname is after_failover.hostname:
            self.fail("The enabled CLC was the same before and after the failover")     
        
        primary_service.start()
        
        try:
            self.servman.wait_for_service(primary_service, state ="DISABLED")
        except Exception, e:
            self.fail("The secondary service never went to disabled")
        
    
    
    def failoverReboot(self, service_aquisition_callback, testcase_callback, **kwargs):
        ### Reboot the current enabled component
        primary_service = service_aquisition_callback()
        secondary_service = self.tester.service_manager.wait_for_service(primary_service, state="DISABLED")
        self.tester.debug("Primary Service: " + primary_service.machine.hostname + " Secondary Service: " + secondary_service.machine.hostname)
        
        primary_service.machine.reboot()    
        
        if "clc" in primary_service.machine.components:
            self.tester.debug("Switching ec2 connection to host: " +  secondary_service.machine.hostname)
            self.tester.clc = secondary_service.machine
            self.tester.ec2.host = secondary_service.machine.hostname
        
        if "ws" in primary_service.machine.components:
            self.tester.debug("Switching walrus connection to host: " +  secondary_service.machine.hostname)
            self.tester.walrus = secondary_service.machine
            self.tester.s3.DefaultHost = secondary_service.machine.hostname
            
        self.tester.sleep(30)
            
        self.run_testcase(testcase_callback, **kwargs)
        self.tester.terminate_instances(self.reservation)
        after_failover =  self.tester.service_manager.wait_for_service(primary_service, state="ENABLED")
               
        if primary_service.hostname is after_failover.hostname:
            self.fail("The enabled CLC was the same before and after the failover")     
             
        try:
            self.servman.wait_for_service(primary_service, state ="DISABLED")
        except Exception, e:
            self.fail("The secondary service never went to disabled")
            
    def failoverNetwork(self, service_aquisition_callback, testcase_callback, **kwargs):
        
        ### Reboot the current enabled component
        primary_service = service_aquisition_callback()
        secondary_service = self.tester.service_manager.wait_for_service(primary_service, state="DISABLED")
        self.tester.debug("Primary Service: " + primary_service.machine.hostname + " Secondary Service: " + secondary_service.machine.hostname)
        primary_service.machine.interrupt_network(360)    
        
        if "clc" in primary_service.machine.components:
            self.tester.debug("Switching ec2 connection to host: " +  secondary_service.machine.hostname)
            self.tester.clc = secondary_service.machine
            self.tester.ec2.host = secondary_service.machine.hostname
        
        if "ws" in primary_service.machine.components:
            self.tester.debug("Switching walrus connection to host: " +  secondary_service.machine.hostname)
            self.tester.walrus = secondary_service.machine
            self.tester.s3.DefaultHost = secondary_service.machine.hostname
            
        self.tester.sleep(30)
            
        self.run_testcase(testcase_callback, **kwargs)
        self.tester.terminate_instances(self.reservation)
        after_failover =  self.tester.service_manager.wait_for_service(primary_service, state="ENABLED")
                     
        if primary_service.hostname is after_failover.hostname:
            self.fail("The enabled CLC was the same before and after the failover")     
             
        try:
            self.servman.wait_for_service(primary_service, state ="DISABLED")
        except Exception, e:
            self.fail("The secondary service never went to disabled")
    
    def post_run_checks(self):
        for service in self.servman.get_all_services():
            service.machine.refresh_ssh()
        self.servman.all_services_operational()
        
    def failoverCLC(self):
        self.failoverService(self.servman.get_enabled_clc, self.MetaData)
        self.post_run_checks()
        self.failoverReboot(self.servman.get_enabled_clc, self.MetaData)
        self.post_run_checks()
        self.failoverNetwork(self.servman.get_enabled_clc, self.MetaData)
        self.post_run_checks()
    
    def failoverWalrus(self):
        self.failoverService(self.servman.get_enabled_walrus, self.test_bucket_get_put_delete)
        self.post_run_checks()
        self.failoverReboot(self.servman.get_enabled_walrus,self.test_bucket_get_put_delete)
        self.post_run_checks()
        self.failoverNetwork(self.servman.get_enabled_walrus, self.test_bucket_get_put_delete)
        self.post_run_checks()
    
    def failoverCC(self):
        zone = self.servman.partitions.keys()[0]
        self.failoverService(self.servman.partitions[zone].get_enabled_cc, self.MetaData,self.zone)
        self.post_run_checks()
        self.failoverReboot(self.servman.partitions[zone].get_enabled_cc, self.MetaData,self.zone)
        self.post_run_checks()
        self.failoverNetwork(self.servman.partitions[zone].get_enabled_cc, self.MetaData,self.zone)
        self.post_run_checks()
    
    def failoverSC(self):    
        zone = self.servman.partitions.keys()[0]
        self.failoverService(self.servman.partitions[zone].get_enabled_sc, InstanceBasics.Reboot, self.zone)
    
    def failoverVB(self):
        zone = self.servman.partitions.keys()[0]
        if len(self.servman.partitions[zone].vbs) > 1:
            self.failoverService(self.servman.partitions[zone].get_enabled_vb, InstanceBasics.MetaData ,self.zone)
    
    def run_suite(self):  
        self.testlist = [] 
        testlist = self.testlist
        testlist.append(self.create_testcase_from_method(self.failoverCLC))
        testlist.append(self.create_testcase_from_method(self.failoverWalrus()))       
        self.run_test_case_list(testlist)

if __name__ == "__main__":
    import sys
    ## If given command line arguments, use them as test names to launch
    parser = HAtests.get_parser()       
    args = parser.parse_args()
    hasuite = HAtests(config_file=args.config, password = args.password)
    hasuite.run_suite()
