#!/usr/bin/python
import unittest
import time
from eucaops import Eucaops
from eutester import xmlrunner
import os
import re
import random
import argparse

class LoadGenerator(unittest.TestCase):
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
        for i in xrange(10):
            key_name = "key-generator-" + str(i)
            keypair = self.tester.add_keypair()
            self.tester.delete_keypair(keypair)
        
    def suite():
        tests = ["GenerateKeypairs"]
        for test in tests:
            result = unittest.TextTestRunner(verbosity=2).run(LoadGenerator(test))
            if result.wasSuccessful():
               pass
            else:
               exit(1)
    
if __name__ == "__main__":
    import sys
    ## If given command line arguments, use them as test names to launch
    parser = argparse.ArgumentParser(description='Parse test suite arguments.')
    parser.add_argument('--xml', action="store_true", default=False)
    parser.add_argument('--tests', nargs="?", default=None)
    args = parser.parse_args()
    if args.tests is not None:
        tests = args.tests[1:]
    else:
    ### Other wise launch the whole suite
        tests = ["GenerateKeypairs"]
    for test in tests:
        if args.xml:
            result = xmlrunner.XMLTestRunner().run(LoadGenerator(test))
        else:
            result = unittest.TextTestRunner(verbosity=2).run(LoadGenerator(test))
        if result.wasSuccessful():
            pass
        else:
            exit(1)