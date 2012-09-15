#!/usr/bin/env python

#
##########################
#                        #
#       Test Cases       #
#                        #
##########################


from eucaops import Eucaops
import argparse
import time

from eutester.eutestcase import EutesterTestCase
from boto.exception import S3ResponseError
from boto.exception import S3CreateError
import boto

class BucketTestSuite(EutesterTestCase):
    
    def __init__(self, credpath):
        self.bucket_prefix = "buckettestsuite-" + str(int(time.time())) + "-"
        self.tester = Eucaops(credpath=credpath)
        self.test_user_id = self.tester.s3.get_canonical_user_id()
    
    def test_bucket_get_put_delete(self):
        '''Tests creating and deleting buckets as well as getting the bucket listing'''
        test_bucket=self.bucket_prefix + "simple_test_bucket"
        self.tester.debug("Starting get/put/delete bucket test using bucket name: " + test_bucket)
 
        try :
            bucket = self.tester.s3.create_bucket(test_bucket)                
            if bucket == None:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail(test_bucket + " was not created correctly")
        except (S3ResponseError, S3CreateError) as e:
            self.fail(test_bucket + " create caused exception: " + e)
        
        try :    
            bucket = self.tester.s3.get_bucket(test_bucket)
            if bucket == None:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail(test_bucket +" was not fetched by get_bucket call")
        except S3ResponseError as e:
            self.tester.s3.delete_bucket(test_bucket)
            self.fail("Exception getting bucket" + e)
            
        
        self.tester.s3.delete_bucket(test_bucket)        
        try :
            if self.tester.s3.get_bucket(test_bucket) != None:
                self.tester.s3.delete_bucket(test_bucket)            
                self.fail("Delete of " + test_bucket + " failed, still exists")
        except S3ResponseError as e:
            self.tester.debug( "Correctly got exception trying to get a deleted bucket! " )
            
        self.tester.debug( "Testing an invalid bucket names, calls should fail." )
        try:
            bad_bucket = self.bucket_prefix + "bucket123/"
            self.tester.create_bucket(bad_bucket)
            should_fail = True            
            try:
                self.tester.delete_bucket(bad_bucket)
            except:
                self.tester.debug( "Exception deleting bad bucket, shouldn't be here anyway. Test WILL fail" )
                
            if should_fail:
                self.fail("Should have caught exception for bad bucket name: " + bad_bucket)
        except:
            self.tester.debug( "Correctly caught the exception" )
        
        try:
            bad_bucket = self.bucket_prefix + "bucket.123"
            self.tester.create_bucket(bad_bucket)
            should_fail = True            
            try:
                self.tester.delete_bucket(bad_bucket)
            except:
                self.tester.debug( "Exception deleting bad bucket, shouldn't be here anyway. Test WILL fail" )
                
            if should_fail:
                self.fail("Should have caught exception for bad bucket name: " + bad_bucket)
        except:
            self.tester.debug( "Correctly caught the exception" )
        
        try:
            bad_bucket = self.bucket_prefix + "bucket&123"
            self.tester.create_bucket(bad_bucket)
            should_fail = True            
            try:
                self.tester.delete_bucket(bad_bucket)
            except:
                self.tester.debug( "Exception deleting bad bucket, shouldn't be here anyway. Test WILL fail" )
                
            if should_fail:
                self.fail("Should have caught exception for bad bucket name: " + bad_bucket)
        except:
            self.tester.debug( "Correctly caught the exception" )
        
        try:
            bad_bucket = self.bucket_prefix + "bucket*123"
            self.tester.create_bucket(bad_bucket)
            should_fail = True            
            try:
                self.tester.delete_bucket(bad_bucket)
            except:
                self.tester.debug( "Exception deleting bad bucket, shouldn't be here anyway. Test WILL fail" )
                
            if should_fail:
                self.fail("Should have caught exception for bad bucket name: " + bad_bucket)
        except:
            self.tester.debug( "Correctly caught the exception" )
        
        try:
            bad_bucket = self.bucket_prefix + "/bucket123"
            self.tester.create_bucket(bad_bucket)
            should_fail = True            
            try:
                self.tester.delete_bucket(bad_bucket)
            except:
                self.tester.debug( "Exception deleting bad bucket, shouldn't be here anyway. Test WILL fail" )
                
            if should_fail:
                self.fail("Should have caught exception for bad bucket name: " + bad_bucket)
        except:
            self.tester.debug( "Correctly caught the exception" )

    def test_bucket_acl(self):
        test_bucket = self.bucket_prefix + "acl_bucket_test"
        self.tester.debug('Starting ACL test with bucket name: ' + test_bucket)        
        try: 
            acl_bucket = self.tester.s3.create_bucket(test_bucket)
            self.tester.debug('Created bucket: ' + test_bucket)
        except S3CreateError:
            self.tester.debug( "Can't create the bucket, already exists. Deleting it an trying again" )
            try :
                self.tester.s3.delete_bucket(test_bucket)            
                acl_bucket = self.tester.s3.create_bucket(test_bucket)
            except:
                self.tester.debug( "Couldn't delete and create new bucket. Failing test" )
                self.fail("Couldn't make the test bucket: " + test_bucket)
                                
        policy = acl_bucket.get_acl()
        
        if policy == None:
            self.fail("No acl returned")
        
        self.tester.debug( policy )
        #Check that the acl is correct: owner full control.
        if len(policy.acl.grants) > 1:
            self.tester.s3.delete_bucket(test_bucket)
            self.fail("Expected only 1 grant in acl. Found: " + policy.acl.grants.grants.__len__())

        if policy.acl.grants[0].display_name != "eucalyptus" or policy.acl.grants[0].permission != "FULL_CONTROL":
            self.tester.s3.delete_bucket(test_bucket)
            self.fail("Unexpected grant encountered: " + policy.acl.grants[0].display_name + "  " + policy.acl.grants[0].permission)
                    
        #upload a new acl for the bucket
        new_acl = policy
        new_acl.acl.add_user_grant(permission="READ", user_id=self.test_user_id, display_name="eucalyptus_test")        
        
        try:
            acl_bucket.set_acl(new_acl)                
            acl_check = acl_bucket.get_acl()
        except S3ResponseError:
            self.fail("Failed to set or get new acl")
        
        self.tester.debug( "Got ACL: " + acl_check.acl.to_xml() )
        
        expected_result='<AccessControlList><Grant><Grantee xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="CanonicalUser"><ID>INSERT_USER_ID_HERE</ID><DisplayName>eucalyptus</DisplayName></Grantee><Permission>FULL_CONTROL</Permission></Grant><Grant><Grantee xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="CanonicalUser"><ID>INSERT_USER_ID_HERE</ID><DisplayName>eucalyptus</DisplayName></Grantee><Permission>READ</Permission></Grant></AccessControlList>'
        
        if acl_check == None or acl_check.acl.to_xml() != expected_result.replace("INSERT_USER_ID_HERE",self.test_user_id):
            self.tester.s3.delete_bucket(test_bucket) 
            self.fail("Incorrect acl length or acl not found:\n" + str(acl_check.acl.to_xml()) + "\n" + expected_result.replace("INSERT_USER_ID_HERE",self.test_user_id))
        
        self.tester.debug( "Grants 0 and 1: " + acl_check.acl.grants[0].to_xml() + " -- " + acl_check.acl.grants[1].to_xml() )
        
        #Check each canned ACL string in boto to make sure Walrus does it right
        for acl in boto.s3.acl.CannedACLStrings:
            try: 
                acl_bucket.set_acl(acl)
                acl_check = acl_bucket.get_acl()
            except Exception as e:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail("Got exception trying to set acl to " + acl + ": " + str(e))
            
            self.tester.debug( "Expecting a " + acl + " acl, got: " + acl_check.acl.to_xml() )
            
            expected_acl = self.tester.get_canned_acl(self.test_user_id,acl)
            if expected_acl == None:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail("Got None when trying to generate expected acl for canned acl string: " + acl)
            
            
            if expected_acl != acl_check.acl:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail("Invalid " + acl + " acl returned from Walrus:\n" + acl_check.acl.to_xml() + "\nExpected\n" + expected_acl.to_xml())
            else:
                self.tester.debug( "Got correct acl for: " + acl  )          
        
        
        try:
            acl_bucket.set_acl('invalid-acl')
        except:            
            self.tester.debug( "Caught expected exception from invalid canned-acl" )
        
        
        
        self.tester.s3.delete_bucket(test_bucket)
        self.tester.debug( "Bucket ACL: PASSED"  )    
        pass    
    
    def test_bucket_key_list_delim_prefix(self):
        """Tests the prefix/delimiter functionality of key listings and parsing"""
        test_bucket_name = self.bucket_prefix + "testbucketdelim"
        self.tester.debug('Testing bucket key list delimiters and prefixes using bucket: ' + test_bucket_name)        
        try: 
            testbucket = self.tester.s3.create_bucket(bucket_name=test_bucket_name)
        except S3CreateError:
            self.tester.debug( "bucket already exists, using it" )
            try:
                testbucket = self.tester.s3.get_bucket(bucket_name=test_bucket_name)
            except S3ResponseError as err:
                self.tester.debug( "Fatal error: could to create or get bucket" )
                for b in self.tester.s3.get_all_buckets():
                    self.tester.debug( "Bucket: " + b.name   )             
                self.fail("Could not setup bucket, " + test_bucket_name + " for test: " + err.error_message )

        prefix = "users"
        delim = "/"
        
        for i in range(10):
            tmp = str(i)
            self.tester.debug("adding keys iteration " + tmp)
            key = testbucket.new_key("testobject" + tmp)
            key.set_contents_from_string("adlsfjaoivajsdlajsdfiajsfdlkajsfkajdasd")
            
            key = testbucket.new_key(prefix + "testkey" + tmp)
            key.set_contents_from_string("asjaoidjfafdjaoivnw")
            
            key = testbucket.new_key(prefix + delim + "object" + tmp)
            key.set_contents_from_string("avjaosvdafajsfd;lkaj")
            
            key = testbucket.new_key(prefix + delim + "objects" + delim + "photo" + tmp + ".jpg")
            key.set_contents_from_string("aoiavsvjasldfjadfiajss")
    
        keys = testbucket.get_all_keys(prefix=prefix, delimiter=delim, max_keys=10)
        self.tester.debug( "Prefix with 10 keys max returned: " + str(len(keys)) + " results" )
        
        for k in keys:
                self.tester.debug( k )
            
        keys = testbucket.get_all_keys(prefix=prefix, delimiter=delim, max_keys=20)
        self.tester.debug( "Prefix with 20 keys max returned: " + str(len(keys)) + " results" )
        
        for k in keys:
                self.tester.debug( k )
            
        print "Cleaning up the bucket"
        for i in range(10):
            testbucket.delete_key("testobject" + str(i))
            testbucket.delete_key(prefix + "testkey" + str(i))
            testbucket.delete_key(prefix + delim + "object" + str(i))
            testbucket.delete_key(prefix + delim + "objects" + delim + "photo" + str(i) + ".jpg")

        print "Deleting the bucket"
        self.tester.s3.delete_bucket(testbucket)
                
    def run_suite(self):  
        self.testlist = [] 
        testlist = self.testlist
        testlist.append(self.create_testcase_from_method(self.test_bucket_get_put_delete))
        testlist.append(self.create_testcase_from_method(self.test_bucket_key_list_delim_prefix))
        #Failing due to invalid private canned acl being returned
        #testlist.append(self.create_testcase_from_method(self.test_bucket_acl))       
        self.run_test_case_list(testlist)  
              
if __name__ == "__main__":
    ## If given command line arguments, use them as test names to launch

    ## If given command line arguments, use them as test names to launch
    parser = argparse.ArgumentParser(prog="bucket_tests.py",
                                     version="Test Case [bucket_tests.py] Version 0.1",
                                     description="Attempts to tests and provide info on focused areas related to\
                                     Eucalyptus S3 bucket related functionality.",
                                     usage="%(prog)s --credpath=<path to creds> [--xml] [--tests=test1,..testN]")
    
    parser.add_argument('--credpath', 
                        help="path to credentials", default=None)
    parser.add_argument('--xml', 
                        help="to provide JUnit style XML output", action="store_true", default=False)
    parser.add_argument('--tests', nargs='+', 
                        help="test cases to be executed", 
                        default= ['test_bucket_get_put_delete'])
    args = parser.parse_args()
    bucketsuite = BucketTestSuite(credpath=args.credpath)
    kbtime=time.time()
    try:
        bucketsuite.run_suite()
    except KeyboardInterrupt:
        bucketsuite.debug("Caught keyboard interrupt...")
        if ((time.time()-kbtime) < 2):
            ebssuite.clean_created_resources()
            ebssuite.debug("Caught 2 keyboard interupts within 2 seconds, exiting test")
            ebssuite.clean_created_resources()
            raise
        else:          
            ebssuite.print_test_list_results()
            kbtime=time.time()
            pass
    exit(0)
