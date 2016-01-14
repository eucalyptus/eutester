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
from boto.exception import BotoServerError
from boto.exception import S3CreateError
import boto
import boto.s3
from boto.s3.bucket import Bucket
from boto.s3.key import Key
from boto.s3.acl import ACL, Policy, Grant
from boto.s3.connection import Location
from boto.s3.lifecycle import Lifecycle, Rule, Expiration
from boto.s3.cors import CORSConfiguration, CORSRule


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
        
    def test_cors_config_mgmt(self):
        '''
        Method: Tests setting, getting, and deleting the CORS config on a bucket
        '''
        test_bucket=self.bucket_prefix + "-simple-test-bucket"
        self.buckets_used.add(test_bucket)
        self.tester.debug("Starting CORS config management tests, using bucket name: " + test_bucket)
 
        try :
            bucket = self.tester.s3.create_bucket(test_bucket)                
            if bucket == None:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail(test_bucket + " was not created correctly")
        except (S3ResponseError, S3CreateError) as e:
            self.fail(test_bucket + " create caused exception: " + str(e))
        
        # Get the CORS config (none yet). 
        # Should get 404 Not Found, with "NoSuchCORSConfiguration" in the body.
        try :    
            self.tester.debug("Getting (empty) CORS config")
            bucket.get_cors()
            self.tester.s3.delete_bucket(test_bucket)
            self.fail("Did not get an S3ResponseError getting CORS config when none exists yet.")
        except S3ResponseError as e:
            if (e.status == 404 and e.reason == "Not Found" and e.code == "NoSuchCORSConfiguration"):
                self.tester.debug("Caught S3ResponseError with expected contents, " + 
                                  "getting CORS config when none exists yet.")
            else:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail("Caught S3ResponseError getting CORS config when none exists yet," +
                          "but exception contents were unexpected: " + str(e))

        # Set a simple CORS config.
        try :    
            self.tester.debug("Setting a CORS config")
            bucket_cors_set = CORSConfiguration()
            bucket_rule_id = "ManuallyAssignedId1"
            bucket_allowed_methods = ['GET', 'PUT']
            bucket_allowed_origins = ['*']
            bucket_allowed_headers = ['*']
            bucket_max_age_seconds = 3000
            #bucket_expose_headers = []
            bucket_cors_set.add_rule(bucket_allowed_methods, 
                                     bucket_allowed_origins, 
                                     bucket_rule_id,
                                     bucket_allowed_headers, 
                                     bucket_max_age_seconds)
            bucket.set_cors(bucket_cors_set)
        except S3ResponseError as e:
            self.tester.s3.delete_bucket(test_bucket)
            self.fail("Caught S3ResponseError setting CORS config: " + str(e))
                    
        # Get the CORS config. Should get the config we just set.
        try :    
            self.tester.debug("Getting the CORS config we just set")
            bucket_cors_retrieved = bucket.get_cors()
            assert (bucket_cors_retrieved.to_xml() == bucket_cors_set.to_xml()), 'Bucket CORS config: Expected ' + bucket_cors_set.to_xml() + ', Retrieved ' + bucket_cors_retrieved.to_xml()
            
        except S3ResponseError as e:
            self.tester.s3.delete_bucket(test_bucket)
            self.fail("Caught S3ResponseError getting CORS config, after setting it successfully: " + str(e))
        
        # Delete the CORS config.
        try :    
            self.tester.debug("Deleting the CORS config")
            bucket.delete_cors()
        except S3ResponseError as e:
            self.tester.s3.delete_bucket(test_bucket)
            self.fail("Caught S3ResponseError deleting CORS config, after setting and validating it successfully: " + str(e))

        # Get the CORS config (none anymore). 
        # Should get 404 Not Found, with "NoSuchCORSConfiguration" in the body.
        try :    
            self.tester.debug("Getting (empty again) CORS config")
            bucket.get_cors()
            self.tester.s3.delete_bucket(test_bucket)
            self.fail("Did not get an S3ResponseError getting CORS config after being deleted.")
        except S3ResponseError as e:
            self.tester.s3.delete_bucket(test_bucket)
            if (e.status == 404 and e.reason == "Not Found" and e.code == "NoSuchCORSConfiguration"):
                self.tester.debug("Caught S3ResponseError with expected contents, " + 
                                  "getting CORS config after being deleted.")
            else:
                self.fail("Caught S3ResponseError getting CORS config after being deleted," +
                          "but exception contents were unexpected: " + str(e))


    def test_cors_preflight_requests(self):
        '''
        Method: Tests creating a bucket, 
        setting up a complex CORS config,
        getting it back and validating its contents,  
        sending various preflight OPTIONS requests,
        and validating the preflight responses against the CORS config.
        '''
        self.fail("Feature Not implemented")
        
    def clean_method(self):
        '''This is the teardown method'''
        #Delete the testing bucket if it is left-over
        self.tester.info('Deleting the buckets used for testing')
        # Can't iterate over a list if we're deleting from it as we iterate, so make a copy
        buckets_used = self.buckets_used.copy() 
        for bucket_name in buckets_used:
            try:
                self.tester.info('Checking bucket ' + bucket_name + ' for possible cleaning/delete')
                self.tester.s3.get_bucket(bucket_name)
                self.tester.info('Found bucket exists, cleaning and deleting it')
                self.tester.clear_bucket(bucket_name)
                self.buckets_used.remove(bucket_name)
            except BotoServerError as e:
                self.tester.info('Exception checking bucket' + bucket_name + ': ' + str(e))
        return
          
if __name__ == "__main__":
    testcase = CorsTestSuite()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    test_list = testcase.args.tests or [ 'test_cors_config_mgmt'#, \
                                   #'test_cors_preflight_requests'
                                   ]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in test_list:
        unit_list.append( testcase.create_testunit_by_name(test) )
    ### Run the EutesterUnitTest objects

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)