#!/usr/bin/python
import unittest
import time
import sys

from testcases.cloud_user.instances.instancetest import InstanceBasics
from testcases.cloud_user.s3.bucket_tests import BucketTestSuite
from eutester.eutestcase import EutesterTestCase
from eucaops import Eucaops 
import os
import re
import random

class HAtests(InstanceBasics, BucketTestSuite):
    def __init__(self, config_file="cloud.conf", password="foobar"):
        self.tester = Eucaops( config_file=config_file, password=password)
        self.servman = self.tester.service_manager
        self.tester.poll_count = 120
        ### Add and authorize a group for the instance
        self.start_time = str(int(time.time()))
        self.group = self.tester.add_group(group_name="group-" + self.start_time )
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + self.start_time)
        self.keypath = os.curdir + "/" + self.keypair.name + ".pem"
        self.image = self.tester.get_emi(root_device_type="instance-store")
        self.reservation = None
        self.private_addressing = False
        self.bucket_prefix = "buckettestsuite-" + self.start_time + "-"
        self.test_user_id = self.tester.s3.get_canonical_user_id()
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name
        
        
        ### Create standing resources that will be checked after all failures
        ### Instance, volume, buckets
        ### 
        self.standing_reservation = self.tester.run_instance(keypair=self.keypair.name,group=self.group.name, zone=self.zone)
        self.volume = self.tester.create_volume(self.zone)
        self.device = self.standing_reservation.instances[0].attach_volume(self.volume)
        self.standing_bucket_name = "failover-bucket-" + self.start_time
        self.standing_bucket = self.tester.create_bucket(self.standing_bucket_name)
        self.standing_key_name = "failover-key-" + self.start_time
        self.standing_key = self.tester.upload_object(self.standing_bucket_name, self.standing_key_name)
        self.standing_key = self.tester.get_objects_by_prefix(self.standing_bucket_name, self.standing_key_name)
        

        
            
    def run_testcase(self, testcase_callback, **kwargs):
        poll_count = 20
        poll_interval = 20       
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
            self.tester.s3.host = secondary_service.machine.hostname
            
        self.tester.sleep(30)
            
        self.run_testcase(testcase_callback, **kwargs)

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
            self.tester.s3.host = secondary_service.machine.hostname
            
        self.tester.sleep(30)
            
        self.run_testcase(testcase_callback, **kwargs)

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
        primary_service.machine.interrupt_network(600)    
        
        if "clc" in primary_service.machine.components:
            self.tester.debug("Switching ec2 connection to host: " +  secondary_service.machine.hostname)
            self.tester.clc = secondary_service.machine
            self.tester.ec2.host = secondary_service.machine.hostname
        
        if "ws" in primary_service.machine.components:
            self.tester.debug("Switching walrus connection to host: " +  secondary_service.machine.hostname)
            self.tester.walrus = secondary_service.machine
            self.tester.s3.host = secondary_service.machine.hostname
            
        self.tester.sleep(30)
            
        self.run_testcase(testcase_callback, **kwargs)

        after_failover =  self.tester.service_manager.wait_for_service(primary_service, state="ENABLED")
                     
        if primary_service.hostname is after_failover.hostname:
            self.fail("The enabled CLC was the same before and after the failover")     
             
        try:
            self.servman.wait_for_service(primary_service, state ="DISABLED")
        except Exception, e:
            self.fail("The secondary service never went to disabled")
    
    def post_run_checks(self):
        
        ## Refresh all SSH connections to machines
        for service in self.servman.get_all_services():
            service.machine.refresh_ssh()
        
        ## Ensure instance still has volume attached
        for instance in self.standing_reservation.instances:
            instance.ssh.refresh_connection()
            instance.assertFilePresent(self.device)
        
        #key = self.tester.get_objects_by_prefix(self.standing_bucket_name, self.standing_key_name)
        #if key.etag is not self.standing_key.etag:
        #    raise Exception("Key no longer has same etag as before failover. Before: " + str(self.standing_key.etag) + " After:" + str(key.etag))
        
        
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
        self.failoverService(self.servman.partitions[zone].get_enabled_cc, self.MetaData, zone=self.zone)
        self.post_run_checks()
        self.failoverReboot(self.servman.partitions[zone].get_enabled_cc, self.MetaData, zone=self.zone)
        self.post_run_checks()
        self.failoverNetwork(self.servman.partitions[zone].get_enabled_cc, self.MetaData, zone=self.zone)
        self.post_run_checks()
    
    def failoverSC(self):    
        zone = self.servman.partitions.keys()[0]
        self.failoverService(self.servman.partitions[zone].get_enabled_sc, self.Reboot, self.zone)
    
    def failoverVB(self):
        zone = self.servman.partitions.keys()[0]
        if len(self.servman.partitions[zone].vbs) > 1:
            self.failoverService(self.servman.partitions[zone].get_enabled_vb, self.MetaData ,self.zone)
    
    def cleanup(self):
        try:
            self.tester.terminate_instances()
        except Exception, e: 
            self.tester.critical("Unable to terminate all instances")
        self.servman.start_all()
    
    def run_suite(self):  
        self.testlist = [] 
        testlist = self.testlist
        testlist.append(self.create_testcase_from_method(self.failoverCLC))
        testlist.append(self.create_testcase_from_method(self.failoverWalrus))
        testlist.append(self.create_testcase_from_method(self.failoverCC))       
        self.run_test_case_list(testlist)
        self.cleanup() 

if __name__ == "__main__":
    parser = HAtests.get_parser()       
    args = parser.parse_args()
    hasuite = HAtests(config_file=args.config, password = args.password)
    hasuite.run_suite()
   
