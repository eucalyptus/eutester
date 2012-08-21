#!/usr/bin/env python

import unittest
import time
from eucaops import Eucaops
from eutester import xmlrunner
import os
import argparse
import boto.ec2, boto.sts, boto.ec2.regioninfo, boto.regioninfo, boto.s3, boto.s3.connection

arg_credpath = None

class StsBasics(unittest.TestCase):
    """
    Tests for AWS STS / Temporary Security Credentials.

    Available tests are:
      - testIssueToken - basic test for token issuance
      - testIssueTokenWithDuration - test for token issuance with a specified duration
      - testEC2TemporaryCredentials - test access to EC2 using temporary credentials
      - testS3TemporaryCredentials - test access to S3 using temporary credentials
    """

    def setUp(self):
        self.tester = Eucaops( credpath=arg_credpath )

    def tearDown(self):
        self.tester = None

    def testIssueToken(self):
        """
        Test basic token issuance
        """
        credentials = self.tester.issue_session_token()
        self.assertIsNotNone( credentials, msg='Could not get credentials' )
        self.assertIsNotNone( credentials.access_key , msg='Credentials missing access_key' )
        self.assertIsNotNone( credentials.secret_key , msg='Credentials missing secret_key' )
        self.assertIsNotNone( credentials.session_token , msg='Credentials missing session_token' )
        self.assertIsNotNone( credentials.expiration , msg='Credentials missing expiration' )

    def testIssueTokenWithDuration(self):
        """
        Test issuing a token with a specified duration
        """
        credentials = self.tester.issue_session_token( duration=3600 )
        self.assertIsNotNone( credentials, msg='Could not get credentials' )
        self.assertIsNotNone( credentials.access_key , msg='Credentials missing access_key' )
        self.assertIsNotNone( credentials.secret_key , msg='Credentials missing secret_key' )
        self.assertIsNotNone( credentials.session_token , msg='Credentials missing session_token' )
        self.assertIsNotNone( credentials.expiration , msg='Credentials missing expiration' )

    def testEC2TemporaryCredentials(self):
        """
        Test access to EC2 using temporary credentials
        """
        credentials = self.tester.get_session_token()
        ec2connection = boto.connect_ec2(
            aws_access_key_id=credentials.access_key,
            aws_secret_access_key=credentials.secret_key,
            security_token=credentials.session_token,
            region=self.tester.ec2.region,
            port=self.tester.ec2.port,
            path=self.tester.ec2.path,
            api_version=self.tester.ec2.APIVersion,
            is_secure=self.tester.ec2.is_secure )
        ec2connection.create_key_pair('testEC2TemporaryCredentials_key')
        ec2connection.delete_key_pair('testEC2TemporaryCredentials_key')
        ec2connection.close()

    def testS3TemporaryCredentials(self):
        """
        Test access to S3 using temporary credentials
        """
        credentials = self.tester.get_session_token()
        calling_format=boto.s3.connection.OrdinaryCallingFormat()
        s3connection = boto.connect_s3(
            aws_access_key_id=credentials.access_key,
            aws_secret_access_key=credentials.secret_key,
            security_token=credentials.session_token,
            host=self.tester.s3.host,
            port=self.tester.s3.port,
            path=self.tester.s3.path,
            is_secure=self.tester.s3.is_secure,
            calling_format=calling_format)
        s3connection.create_bucket('testEC2TemporaryCredentials_bucket')
        s3connection.delete_bucket('testEC2TemporaryCredentials_bucket')
        s3connection.close()

if __name__ == "__main__":
    ## If given command line arguments, use them as test names to launch
    parser = argparse.ArgumentParser(prog='ststest.py',
        version='Test Case [ststest.py] Version 0.1',
        description='''Run interactive test of operations to
                       test instance functionality and features
                       on a Eucalyptus Cloud.''',
        usage="%(prog)s --credpath=<path to creds> [--xml] [--tests=test1,..testN]")
    parser.add_argument('--credpath',
        help="path to user credentials", default=".eucarc")
    parser.add_argument('--xml',
        help="to provide JUnit style XML output", action="store_true", default=False)
    parser.add_argument('--tests', nargs='+',
        help="test cases to be executed",
        default= ["testIssueToken","testIssueTokenWithDuration","testEC2TemporaryCredentials","testS3TemporaryCredentials"])
    args = parser.parse_args()
    arg_credpath = args.credpath
    for test in args.tests:
        if args.xml:
            try:
                os.mkdir("results")
            except OSError:
                pass
            file = open("results/test-" + test + "result.xml", "w")
            result = xmlrunner.XMLTestRunner(file).run(StsBasics(test))
            file.close()
        else:
            result = unittest.TextTestRunner(verbosity=2).run(StsBasics(test))
        if result.wasSuccessful():
            pass
        else:
            exit(1)


