#!/usr/bin/python
import unittest
import time
from eucaops import Eucaops
from eutester import xmlrunner
import os
import re
import random

class InstanceBasics(unittest.TestCase):
    def setUp(self):
        # Setup basic eutester object
        self.tester = Eucaops( config_file="../input/2b_tested.lst", password="foobar")
        self.tester.poll_count = 40
        
        ### Determine whether virtio drivers are being used
        self.device_prefix = "sd"
        if self.tester.get_hypervisor() == "kvm":
            self.device_prefix = "vd"
        self.ephemeral = "/dev/" + self.device_prefix + "a2"
        
        ### Add and authorize a group for the instance
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name

    
    def tearDown(self):
        self.reservation = None
        self.group = None
        self.keypair = None
        self.tester = None
        self.ephemeral = None
    
    def GenerateKeypairs(self):
        """
        Create and delete keypairs in series
        """
        for i in xrange(100):
            keypair = self.tester.add_keypair()
            self.tester.delete_keypair(keypair)
        
    def suite():
        tests = ["GenerateKeypairs"]
        for test in tests:
            result = unittest.TextTestRunner(verbosity=2).run(InstanceBasics(test))
            if result.wasSuccessful():
               pass
            else:
               exit(1)
    
if __name__ == "__main__":
    import sys
    ## If given command line arguments, use them as test names to launch
    if (len(sys.argv) > 1):
        tests = sys.argv[1:]
    else:
    ### Other wise launch the whole suite
        tests = ["BasicInstanceChecks","ElasticIps","PrivateIPAddressing","MaxSmallInstances","LargestInstance","MetaData","Reboot", "Churn"]
    for test in tests:
        result = unittest.TextTestRunner(verbosity=2).run(InstanceBasics(test))
        if result.wasSuccessful():
            pass
        else:
            exit(1)