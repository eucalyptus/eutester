#! ../share/python_lib/vic-dev/bin/python
import unittest
import time
import sys
from instancetest import InstanceBasics
from eucaops import Eucaops 
import os
import re


class HAtests(InstanceBasics):
    def setUp(self):
        super(HAtests, self).setUp()
        self.servman = self.tester.service_manager
    
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
            
    def run_testcase(self, testcase_callback,zone):
        poll_count = 10
        poll_interval = 60       
        while (poll_count > 0):
            try:
                testcase_callback(zone)
                break
            except Exception, e:
                self.tester.debug("Attempt failed, retrying in " + str(poll_interval) )
            self.tester.sleep(poll_interval)     
            poll_count = poll_count - 1  
        if poll_count is 0:
            self.fail("Could not run an instance after " + str(poll_count) +" tries with " + str(poll_interval) + "s sleep in between")
        
    def failoverService(self, service_aquisition_callback, testcase_callback, zone=None):
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
            
        self.run_testcase(testcase_callback, zone)
        self.tester.terminate_instances(self.reservation)
        after_failover = self.tester.service_manager.wait_for_service(primary_service, state="ENABLED")
          
        if primary_service.hostname is after_failover.hostname:
            self.fail("The enabled CLC was the same before and after the failover")     
        
        primary_service.start()
        
        try:
            self.servman.wait_for_service(primary_service, state ="DISABLED")
        except Exception, e:
            self.fail("The secondary service never went to disabled")
        
    
    
    def failoverReboot(self, service_aquisition_callback, testcase_callback, zone=None):
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
            
        self.run_testcase(testcase_callback, zone)
        self.tester.terminate_instances(self.reservation)
        after_failover =  self.tester.service_manager.wait_for_service(primary_service, state="ENABLED")
               
        if primary_service.hostname is after_failover.hostname:
            self.fail("The enabled CLC was the same before and after the failover")     
             
        try:
            self.servman.wait_for_service(primary_service, state ="DISABLED")
        except Exception, e:
            self.fail("The secondary service never went to disabled")
            
    def failoverNetwork(self, service_aquisition_callback, testcase_callback, zone=None):
        
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
            
        self.run_testcase(testcase_callback, zone)
        self.tester.terminate_instances(self.reservation)
        after_failover =  self.tester.service_manager.wait_for_service(primary_service, state="ENABLED")
                     
        if primary_service.hostname is after_failover.hostname:
            self.fail("The enabled CLC was the same before and after the failover")     
             
        try:
            self.servman.wait_for_service(primary_service, state ="DISABLED")
        except Exception, e:
            self.fail("The secondary service never went to disabled")
    
    def failoverCLC(self):
        self.failoverService(self.servman.get_enabled_clc, super(HAtests, self).MetaData)
        self.servman.all_services_operational()
        self.failoverReboot(self.servman.get_enabled_clc, super(HAtests, self).MetaData)
        self.servman.all_services_operational()
        self.failoverNetwork(self.servman.get_enabled_clc, super(HAtests, self).MetaData)
        self.servman.all_services_operational()
    
    def failoverWalrus(self):
        self.failoverService(self.servman.get_enabled_walrus, super(HAtests, self).MetaData)
        self.servman.all_services_operational()
        self.failoverReboot(self.servman.get_enabled_walrus, super(HAtests, self).MetaData)
        self.servman.all_services_operational()
        self.failoverNetwork(self.servman.get_enabled_walrus, super(HAtests, self).MetaData)
        self.servman.all_services_operational()
    
    def failoverCC(self):
        zone = self.servman.partitions.keys()[0]
        self.failoverService(self.servman.partitions[zone].get_enabled_cc, super(HAtests, self).MetaData,zone)
        self.servman.all_services_operational()
        self.failoverReboot(self.servman.partitions[zone].get_enabled_cc, super(HAtests, self).MetaData,zone)
        self.servman.all_services_operational()
        self.failoverNetwork(self.servman.partitions[zone].get_enabled_cc, super(HAtests, self).MetaData,zone)
        self.servman.all_services_operational()
    
    def failoverSC(self):    
        zone = self.servman.partitions.keys()[0]
        self.failoverService(self.servman.partitions[zone].get_enabled_sc, self.Reboot, zone)
    
    def failoverVB(self):
        zone = self.servman.partitions.keys()[0]
        if len(self.servman.partitions[zone].vbs) > 1:
            self.failoverService(self.servman.partitions[zone].get_enabled_vb, self.MetaData ,zone)


if __name__ == "__main__":
    import sys
    ## If given command line arguments, use them as test names to launch
    if (len(sys.argv) > 1):
        tests = sys.argv[1:]
    else:
    ### Other wise launch the whole suite
        #tests = ["BasicInstanceChecks","ElasticIps","MaxSmallInstances","LargestInstance","MetaData","Reboot", "Churn"]
        tests = ["failoverCLC"]
    for test in tests:
        result = unittest.TextTestRunner(verbosity=2).run(HAtests(test))
        if result.wasSuccessful():
            pass
        else:
            exit(1)       

    
