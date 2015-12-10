#!/usr/bin/env python

#
###########################################
#                                         #
#   objectstorage/S3 CORS Test Cases      #
#                                         #
###########################################

#Author: Lincoln Thomas <lincoln.thomas@hpe.com>

from datetime import date

from eucaops import Eucaops
import argparse
import time
import re

from eutester.eutestcase import EutesterTestCase
from eucaops import S3ops
from boto.exception import S3ResponseError
from boto.exception import S3CreateError
import boto
import boto.s3
from boto.s3.bucket import Bucket
from boto.s3.key import Key
from boto.s3.acl import ACL, Policy, Grant
from boto.s3.connection import Location
from boto.s3.lifecycle import Lifecycle, Rule, Expiration


class CorsTestSuite(EutesterTestCase):
    
    def __init__(self):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--endpoint", default=None)
        self.get_args()
        # Setup basic eutester object
        if self.args.endpoint:
            self.tester = S3ops(credpath=self.args.credpath, endpoint=self.args.endpoint)
        else:
            self.tester = Eucaops( credpath=self.args.credpath, config_file=self.args.config, password=self.args.password)

        self.bucket_prefix = "eutester-cors-test-suite-" + str(int(time.time()))
        self.buckets_used = set()
        
    def test_cors_get_config(self):
        '''
        Method: Tests creating a bucket and getting the current CORS config
        '''
        test_bucket=self.bucket_prefix + "-simple-test-bucket"
        self.buckets_used.add(test_bucket)
        self.tester.debug("Starting get bucket CORS config with no CORS yet, using bucket name: " + test_bucket)
 
        try :
            bucket = self.tester.s3.create_bucket(test_bucket)                
            if bucket == None:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail(test_bucket + " was not created correctly")
        except (S3ResponseError, S3CreateError) as e:
            self.fail(test_bucket + " create caused exception: " + e)
        
        try :    
            bucket = self.tester.s3.get_bucket_cors_config(test_bucket)
            if bucket == None:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail(test_bucket +" CORS configuration was not fetched by get_bucket_cors_config call")
        except S3ResponseError as e:
            self.tester.s3.delete_bucket(test_bucket)
            self.fail(test_bucket + " get_bucket_cors_config caused exception: " + e)
                    
        self.tester.s3.delete_bucket(test_bucket)        
        

    def test_cors_set_config(self):
        '''
        Method: Tests creating a bucket, setting a CORS config, and
        getting it back to verify.
        '''
        self.fail("Feature Not implemented")
        
    def test_cors_delete_config(self):
        '''
        Method: Tests creating a bucket, setting a CORS config, and
        deleting it.
        '''
        self.fail("Feature Not implemented")
        
    def test_cors_preflight_requests(self):
        '''
        Method: Tests creating a bucket, setting a CORS config, 
        sending various preflight OPTIONS requests, and validating the responses.
        '''
        self.fail("Feature Not implemented")
        
    def clean_method(self):
        '''This is the teardown method'''
        #Delete the testing bucket if it is left-over
        self.tester.info('Deleting the buckets used for testing')
        for bucket in self.buckets_used:
            try:
                self.tester.info('Checking bucket ' + bucket + ' for possible cleaning/delete')
                if self.tester.s3.bucket_exists(bucket):
                    self.tester.info('Found bucket exists, cleaning it')
                    self.tester.clear_bucket(bucket)
                    self.buckets_used.remove(bucket)
                else:
                    self.tester.info('Bucket ' + bucket + ' not found, skipping')
            except:
                self.tester.info('Exception checking bucket ' + str(bucket))

        return
          
if __name__ == "__main__":
    testcase = CorsTestSuite()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    test_list = testcase.args.tests or [ 'test_cors_get_config', \
                                   'test_cors_set_config', \
                                   'test_cors_delete_config', \
                                   'test_cors_preflight_requests']
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in test_list:
        unit_list.append( testcase.create_testunit_by_name(test) )
    ### Run the EutesterUnitTest objects

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)