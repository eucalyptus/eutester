#!/usr/bin/python
import time
import re
import boto

from testcases.cloud_user.instances.instancetest import InstanceBasics
from testcases.cloud_user.s3.bucket_tests import BucketTestSuite
from eucaops import Eucaops
import os
import random

class HAtests(InstanceBasics, BucketTestSuite):
    def __init__(self):
        self.setuptestcase()
        self.setup_parser()
        self.get_args()
        if not boto.config.has_section('Boto'):
            boto.config.add_section('Boto')
            boto.config.set('Boto', 'num_retries', '1')
            boto.config.set('Boto', 'http_socket_timeout', '20')
        self.tester = Eucaops( config_file=self.args.config_file, password=self.args.password)
        self.tester.ec2.connection.timeout = 30
        self.servman = self.tester.service_manager
        self.instance_timeout = 120
        ### Add and authorize a group for the instance
        self.start_time = str(int(time.time()))
        try:
            self.group = self.tester.add_group(group_name="group-" + self.start_time )
            self.tester.authorize_group_by_name(group_name=self.group.name )
            self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
            ### Generate a keypair for the instance
            self.keypair = self.tester.add_keypair( "keypair-" + self.start_time)
            self.keypath = os.curdir + "/" + self.keypair.name + ".pem"
            if self.args.emi:
                self.image = self.tester.get_emi(self.args.emi)
            else:
                self.image = self.tester.get_emi(root_device_type="instance-store")
            self.reservation = None
            self.private_addressing = False
            self.bucket_prefix = "buckettestsuite-" + self.start_time + "-"
            self.test_user_id = self.tester.s3.get_canonical_user_id()
            zones = self.tester.ec2.get_all_zones()
            self.zone = random.choice(zones).name

            self.tester.clc = self.tester.service_manager.get_enabled_clc().machine
            self.version = self.tester.clc.sys("cat " + self.tester.eucapath + "/etc/eucalyptus/eucalyptus-version")[0]
            ### Create standing resources that will be checked after all failures
            ### Instance, volume, buckets
            ###
            self.standing_reservation = self.tester.run_instance(image=self.image ,keypair=self.keypair.name,group=self.group.name, zone=self.zone)
            self.volume = self.tester.create_volume(self.zone)
            self.device = self.standing_reservation.instances[0].attach_volume(self.volume)
            for instance in self.standing_reservation.instances:
                instance.sys("echo " + instance.id  + " > " + self.device)
            self.standing_bucket_name = "failover-bucket-" + self.start_time
            self.standing_bucket = self.tester.create_bucket(self.standing_bucket_name)
            self.standing_key_name = "failover-key-" + self.start_time
            self.standing_key = self.tester.upload_object(self.standing_bucket_name, self.standing_key_name)
            self.standing_key = self.tester.get_objects_by_prefix(self.standing_bucket_name, self.standing_key_name)
            self.run_instance_params = {'image': self.image, 'keypair': self.keypair.name, 'group': self.group.name,
                                        'zone': self.zone, 'timeout': self.instance_timeout}
        except Exception, e:
            self.clean_method()
            raise Exception("Init for testcase failed. Reason: " + str(e))

    def clean_method(self):
        if hasattr(self,"standing_reservation") and self.standing_reservation:
            self.tester.terminate_instances(self.standing_reservation)
        if hasattr(self,"reservation") and self.reservation:
            self.tester.terminate_instances(self.reservation)
        if hasattr(self,"volume") and self.volume:
            self.tester.delete_volume(self.volume)
        self.servman.start_all()
        self.servman.all_services_operational()

    def clean_testcase(self):
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
        self.reservation = None

    def run_testcase(self, testcase_callback, **kwargs):
        poll_count = 20
        poll_interval = 20
        while (poll_count > 0):
            try:
                testcase_callback(**kwargs)
                break
            except Exception, e:
                self.tester.debug("Attempt failed due to: " + str(e)  + "\nRetrying testcase in " + str(poll_interval) )
            finally:
                self.clean_testcase()
            self.tester.sleep(poll_interval)
            poll_count = poll_count - 1  
        if poll_count is 0:
            self.fail("Could not run an instance after " + str(poll_count) +" tries with " + str(poll_interval) + "s sleep in between")
        
    def failoverService(self, service_aquisition_callback, testcase_callback, **kwargs):
        ### Process Take down

        primary_service = service_aquisition_callback()
        secondary_service = self.tester.service_manager.wait_for_service(primary_service, state="DISABLED")
        self.tester.debug("Primary Service: " + primary_service.machine.hostname + " Secondary Service: " + secondary_service.machine.hostname)
        self.status("Failing over via service stop: " + str(primary_service.machine.hostname))
        primary_service.stop()
        
        if "clc" in primary_service.machine.components:
            self.tester.debug("Switching ec2 connection to host: " +  secondary_service.machine.hostname)
            self.tester.clc = secondary_service.machine
            self.tester.ec2.host = secondary_service.machine.hostname
        
        if "ws" in primary_service.machine.components:
            self.tester.debug("Switching walrus connection to host: " +  secondary_service.machine.hostname)
            self.tester.walrus = secondary_service.machine
            self.tester.s3.host = secondary_service.machine.hostname

        self.run_testcase(testcase_callback, **kwargs)

        after_failover = self.tester.service_manager.wait_for_service(primary_service, state="ENABLED")
        if primary_service.hostname is after_failover.hostname:
            self.fail("The enabled CLC was the same before and after the failover")     

        ### REMOVE DISABLED LOCK FILE FROM NON ACTIVE CLC AFTER 3.1
        #if not re.search("^3.1", self.version):
        #    primary_service.machine.sys("rm -rf " + self.tester.eucapath + "/var/lib/eucalyptus/db/data/disabled.lock")
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
        self.status("Failing over via reboot: " + str(primary_service.machine.hostname))
        primary_service.machine.reboot()    
        
        if "clc" in primary_service.machine.components:
            self.tester.debug("Switching ec2 connection to host: " +  secondary_service.machine.hostname)
            self.tester.clc = secondary_service.machine
            self.tester.ec2.host = secondary_service.machine.hostname
        
        if "ws" in primary_service.machine.components:
            self.tester.debug("Switching walrus connection to host: " +  secondary_service.machine.hostname)
            self.tester.walrus = secondary_service.machine
            self.tester.s3.host = secondary_service.machine.hostname

        after_failover =  self.tester.service_manager.wait_for_service(primary_service, state="ENABLED")

        self.run_testcase(testcase_callback, **kwargs)

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
        self.status("Failing over via network outage: " + str(primary_service.machine.hostname))

        interrupt_length = 800
        interrupt_start = int(time.time())
        primary_service.machine.interrupt_network(interrupt_length)
        
        if "clc" in primary_service.machine.components:
            self.tester.debug("Switching ec2 connection to host: " +  secondary_service.machine.hostname)
            self.tester.clc = secondary_service.machine
            self.tester.ec2.host = secondary_service.machine.hostname
        
        if "ws" in primary_service.machine.components:
            self.tester.debug("Switching walrus connection to host: " +  secondary_service.machine.hostname)
            self.tester.walrus = secondary_service.machine
            self.tester.s3.host = secondary_service.machine.hostname

        after_failover = self.servman.wait_for_service(primary_service, state ="ENABLED", timeout=interrupt_length)

        self.run_testcase(testcase_callback, **kwargs)

        testcase_finish = int(time.time()) - interrupt_start


        if primary_service.hostname is after_failover.hostname:
            self.fail("The enabled CLC was the same before and after the failover")

        outage_window_left = interrupt_length - testcase_finish
        if outage_window_left > 0:
            self.status("Sleeping wating for interfaces to come back up")
            self.tester.sleep(interrupt_length - testcase_finish)

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
        
        key = self.tester.get_objects_by_prefix(self.standing_bucket_name, self.standing_key_name)
        
        self.servman.all_services_operational()
        
    def failoverCLC(self):
        self.failoverReboot(self.servman.get_enabled_clc, self.MetaData)
        self.post_run_checks()
        self.failoverService(self.servman.get_enabled_clc, self.MetaData)
        self.post_run_checks()
        self.failoverNetwork(self.servman.get_enabled_clc, self.MetaData)
        self.post_run_checks()
    
    def failoverWalrus(self):
        enabled_walrus = self.servman.get_enabled_walrus()
        try:
            enabled_walrus.machine.sys("ls " + self.tester.eucapath + "/var/lib/eucalyptus/bukkits/" + self.standing_bucket_name, code=0)
        except Exception, e:
            raise Exception("Unable to find bucket before failovers")
        self.failoverService(self.servman.get_enabled_walrus, self.test_bucket_key_list_delim_prefix)
        self.post_run_checks()
        self.failoverReboot(self.servman.get_enabled_walrus,self.test_bucket_key_list_delim_prefix)
        self.post_run_checks()
        self.failoverNetwork(self.servman.get_enabled_walrus, self.test_bucket_key_list_delim_prefix)
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
        self.failoverService(self.servman.partitions[zone].get_enabled_sc, self.Reboot, zone=self.zone)
        self.post_run_checks()
        self.failoverReboot(self.servman.partitions[zone].get_enabled_sc, self.Reboot, zone=self.zone)
        self.post_run_checks()
        self.failoverNetwork(self.servman.partitions[zone].get_enabled_sc, self.Reboot, zone=self.zone)
        self.post_run_checks()
    
    def failoverVB(self):
        zone = self.servman.partitions.keys()[0]
        if len(self.servman.partitions[zone].vbs) > 1:
            self.failoverService(self.servman.partitions[zone].get_enabled_vb, self.Reboot, zone=self.zone)
            self.post_run_checks()
            self.failoverReboot(self.servman.partitions[zone].get_enabled_vb, self.Reboot, zone=self.zone)
            self.post_run_checks()
            self.failoverNetwork(self.servman.partitions[zone].get_enabled_vb, self.Reboot, zone=self.zone)
            self.post_run_checks()


if __name__ == "__main__":
    testcase = HAtests()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or [ "failoverCLC", "failoverWalrus", "failoverCC", "failoverSC", "failoverVB"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )
        ### Run the EutesterUnitTest objects

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
   
