#!/usr/bin/python
# Description: Test case was written to check the bug with euca-disassociate-address
#       which does not properly disassociate Elastic IP address from a running instance
#       It happens to diassociate the current assigned Elastic IP address as well automatically
#       associate a new Elastic IP address to that instance

import unittest
import time
from eucaops import Eucaops
import os
import re

class ElasticIPTest(unittest.TestCase):
    def setUp(self):
        # Setup basic eutester object
        self.tester = Eucaops(credpath="/root/.euca")
        self.tester.poll_count = 40
        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = os.curdir + "/" + self.keypair.name + ".pem"
        self.image = self.tester.get_emi(root_device_type="instance-store")
        self.private_addressing = True
        self.reservation = None

    
    def tearDown(self):
        if self.reservation:
            self.assertTrue(self.tester.terminate_instances(self.reservation), "Unable to terminate instance(s)")
        self.tester.delete_group(self.group)
        self.tester.delete_keypair(self.keypair)
        os.remove(self.keypath)
        self.reservation = None
        self.group = None
        self.keypair = None
        self.tester = None
        self.ephemeral = None


    def ElasticIps(self):
        """ Basic test for elastic IPs
            Allocate an IP, associate it with an instance, ping the instance
            Disassociate the IP, ping the instance
            Release the address, Check Public and Private IPs"""
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group.name,private_addressing=self.private_addressing)
        self.tester.sleep(10)
        for instance in self.reservation.instances:
            address = self.tester.allocate_address()
            self.assertTrue(address,'Unable to allocate address')
            self.assertTrue(self.tester.associate_address(instance, address))
            self.tester.sleep(30)
            instance.update()
            self.assertTrue(self.tester.ping(instance.public_dns_name), "Could not ping instance with new IP")
            address.disassociate()
            self.tester.sleep(30)
            instance.update()
            self.assertTrue(self.tester.ping(instance.public_dns_name), "Could not ping instance with new IP")
            address.release()
            if (instance.public_dns_name != instance.private_dns_name):
                print "Instance has still got a Public IP"
                print "Public IP: " + instance.public_dns_name
                print "Private IP: " + instance.private_dns_name
            else:
                print "Instance is now having only private IP"
                print "Public IP: " + instance.public_dns_name
                print "Private IP: " + instance.private_dns_name
        return self.reservation



if __name__ == "__main__":

    result = unittest.TextTestRunner(verbosity=2).run(ElasticIPTest("ElasticIps"))
    if result.wasSuccessful():
        pass
    else:
        exit(1) 
