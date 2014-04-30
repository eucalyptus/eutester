#!/usr/bin/python
#
#
# Description:  This script encompasses test cases/modules concerning testing CanonicalizedAmzHeaders Element 
#               construction for Eucalyptus Walrus. (The HTTP status errors should match what happens on AWS S3)
#
##########################
#                        #
#       Test Cases       #
#                        #
##########################
#
# [CanonicalizedAmzHeaders]
#
#       This case was developed to see if HTTP status was sent back when doing a GET request 
#       for a listing of buckets with null CanonicalizedAmzHeaders.  
#
# [CanonicalizedAmzCommaHeaders]
#
#       This case was developed to see if HTTP status was sent back when doing a GET request 
#       for a listing of buckets with comma separated CanonicalizedAmzHeaders.  
#
# [CanonicalizedAmzSeparateHeaders]
#
#       This case was developed to see if HTTP status was sent back when doing a GET request 
#       for a listing of buckets with separated CanonicalizedAmzHeaders.  
# 
# [CanonicalizedAmzSeparateHeadersBroken]
#
#       This case was developed to see if HTTP status was sent back when doing a GET request 
#       for a listing of buckets with separated CanonicalizedAmzHeaders, but in a broken format.  
#

import unittest
import time
from eucaops import Eucaops
from eutester import xmlrunner
from rest import S3Connection, Auth
import os
import random
import argparse
import sys

class WalrusBasics(unittest.TestCase):

    def setUp(self):
        if options.credpath:
            self.tester = Eucaops(credpath=options.credpath)
        else:
            print "\tNeed to pass --credpath option. Try --help for more information\n"  
            exit(1)

        protocol = "http://"
        self.server = protocol + self.tester.s3.server_name() + self.tester.s3.path
        self.auth = Auth(self.tester.get_access_key(), self.tester.get_secret_key())
        """
        Create auth and attempt to authenticate to Walrus via S3Connection
        """
        try:
            self.connection = S3Connection(self.server, self.auth)
        except Exception, e:
            exit('Failed to establish authentication to Walrus due to: ' + str(e))

    def CanonicalizedAmzNullHeaders(self):
        self.tester.debug("###")
        self.tester.debug("\tStarting CanonicalizedAmzNullHeaders test")
        self.tester.debug("###")
        """
        Create null headers
        """
        test_headers = {}
        """
        Check to see if GET will work with null headers
        """
        status = self.connection.request("GET", "/", self.connection.fix_resource("/"), '', headers=test_headers)
        """
        status should return 200, with body in response
        """
        self.assertEqual(status[0], 200, 'Expected status code to be 200, actual status code is ' + str(status[0]))
        self.assertNotEqual(status[1], 0, 'Expected status length is greater than 0')

        self.tester.debug("###")
        self.tester.debug("\tSuccessfully completed CanonicalizedAmzNullHeaders test")
        self.tester.debug("###")

    def CanonicalizedAmzCommaHeaders(self):
        self.tester.debug("###")
        self.tester.debug("\tStarting CanonicalizedAmzCommaHeaders test")
        self.tester.debug("###")
        """
        Create x-amz-wutang comma headers
        """
        test_headers = {'x-amz-wutang': 'RZA,GZA,Ol Dirty Bastard,Method Man,Raekwon,Ghostface Killah,Inspectah Deck,U-God,Masta Killa'}
        """
        Check to see if GET will work with x-amz-wutang comma headers
        """
        status = self.connection.request("GET", "/", self.connection.fix_resource("/"), '', headers=test_headers)
        """
        status should return 200, with body in response
        """
        self.assertEqual(status[0], 200, 'Expected status code to be 200, actual status code is ' + str(status[0]))
        self.assertNotEqual(status[1], 0, 'Expected status length is greater than 0')

        self.tester.debug("###")
        self.tester.debug("\tSuccessfully completed CanonicalizedAmzCommaHeaders test")
        self.tester.debug("###")

    def CanonicalizedAmzSeparateHeaders(self):
        self.tester.debug("###")
        self.tester.debug("\tStarting CanonicalizedAmzSeparateHeaders test")
        self.tester.debug("###")
        """
        Create x-amz-wutang separated header 
        """
        test_headers = {'x-amz-wutang': ['RZA','GZA','Ol Dirty Bastard','Method Man','Raekwon','Ghostface Killah','Inspectah Deck','U-God','Masta Killa']}
        """
        Check to see if GET will work with x-amz-wutang separated header
        """
        status = self.connection.request("GET", "/", self.connection.fix_resource("/"), '', headers=test_headers)
        """
        status should return 200, with body in response
        """
        self.assertEqual(status[0], 200, 'Expected status code to be 200, actual status code is ' + str(status[0]))
        self.assertNotEqual(status[1], 0, 'Expected status length is greater than 0')

        self.tester.debug("###")
        self.tester.debug("\tSuccessfully completed CanonicalizedAmzSeparateHeaders test")
        self.tester.debug("###")

    def CanonicalizedAmzSeparateHeadersBroken(self):
        self.tester.debug("###")
        self.tester.debug("\tStarting CanonicalizedAmzSeparateHeadersBroken test")
        self.tester.debug("###")
        """
        Create x-amz-wutang separated headers broken up 
        """
        test_header1 = {'x-amz-wutang': ['RZA','GZA','Method Man','Raekwon','Ghostface Killah','Inspectah Deck','U-God','Masta Killa']}
        test_header2 = ['x-amz-wutang:RZA']
        """
        Check to see if GET will work with x-amz-wutang separated header broken up;
        should come back with 403 error complaining about mismatch signature
        """
        status = self.connection.request("GET", "/", self.connection.fix_resource("/"), '', headers=test_header1, x_amz_headerlist=test_header2)
        """
        status should return 403, with body in response
        """
        self.assertEqual(status[0], 403, 'Expected status code to be 403, actual status code is ' + str(status[0]))
        self.assertNotEqual(status[1], 0, 'Expected status length is greater than 0')

        self.tester.debug("###")
        self.tester.debug("\tSuccessfully completed CanonicalizedAmzSeparateHeadersBroken test")
        self.tester.debug("###")

    def tearDown(self):
        self.tester=None
        self.server=None
        self.auth=None
        self.connection=None

def get_options():
    ### Parse args
    ## If given command line arguments, use them as test names to launch
    parser = argparse.ArgumentParser(prog="canonical_headers_test.py", 
        description='Test Case [canonical_headers_test.py] Version 0.0.1 - Unit test for CanonicalizedAmzHeaders elements against Eucalyptus Walrus')
    parser.add_argument('--credpath', dest='credpath', required=True, help='Path to folder containing credentials')
    parser.add_argument('--xml', action="store_true", default=False)
    parser.add_argument('--tests', nargs='+', default= ["CanonicalizedAmzNullHeaders","CanonicalizedAmzCommaHeaders","CanonicalizedAmzSeparateHeaders","CanonicalizedAmzSeparateHeadersBroken"])
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
            result = xmlrunner.XMLTestRunner(file).run(WalrusBasics(test))
        else:
            result = unittest.TextTestRunner(verbosity=2).run(WalrusBasics(test))
        if result.wasSuccessful():
            pass
        else:
            exit(1)