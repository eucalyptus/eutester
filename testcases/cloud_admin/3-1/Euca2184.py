#!/usr/bin/python
'''
Created on Oct 9, 2012
@author: mmunn
Unit test          : EUCA-2184 EBS backed stopped instances still reports IPs
                     This test assumes you have created and registered an ebs-image
                     you can use:
                     create_bfebs_img_test.py  
                     --url http://mirror.qa.eucalyptus-systems.com/bfebs-image/vmware/bfebs_vmwaretools.img
                     --config ../../cloud_admin/cloud.conf
                     -p foobar
setUp              : creates tester and credentials
test               : start and stop ebs backed instance and make sure the ip addresses are not displayed
tearDown           : terminate instance remove credentials

cloud.conf:( put in same directory as this testcase )
IP_ADDRESS  CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP_ADDRESS  CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca2184(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf"      
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.doAuth()
       
    def tearDown(self):
        self.tester.cleanup_artifacts()
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath)
        
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)
        
    def testOutput(self):
        # Get the existing EBS emi 
        self.emi = self.tester.get_emi(root_device_type='ebs')
        # Start instance
        self.reservation = self.tester.run_instance(self.emi, keypair=self.keypair.name, group=self.group, is_reachable=False)
        # Make sure the instance is running set instance variables
        for instance in self.reservation.instances:
            if instance.state == "running":
                self.dns = instance.public_dns_name
                self.pub_ip = instance.ip_address
                self.priv_ip = instance.private_ip_address                
        
        # Stop Instance       
        self.tester.stop_instances(self.reservation)
        for instance in self.reservation.instances:
            if instance.state == "stopped":
                self.instance = instance
                self.pub_ip = instance.ip_address
                self.priv_ip = instance.private_ip_address
                
        self.tester.debug("Public  IP = " +  self.pub_ip)
        self.tester.debug("Private IP = " +  self.priv_ip)
        
        # Check Ip address to make sure they are empty
        if(len(self.pub_ip) == 0 and len(self.priv_ip) == 0):
            self.tester.debug("Success ips are empty.")
            pass
        else:
            self.fail("Fail ip addresses still displayed.")

if __name__ == "__main__":
    unittest.main("Euca2184")
