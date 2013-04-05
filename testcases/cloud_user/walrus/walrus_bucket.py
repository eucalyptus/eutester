# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2011, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author: zach@eucalyptus.com

'''
Created on Apr 12, 2012

@author: zach@eucalyptus.com
'''
import unittest
import sys, argparse, string, time
import boto
import test_utils
import eucaops.s3ops
from eucaops.s3ops import S3ops
from eucaops import Eucaops
from test_utils import print_header
from boto.s3.connection import OrdinaryCallingFormat
from boto.s3.connection import S3Connection
from boto.s3.bucket import Bucket
from boto.s3.key import Key
from boto.s3.acl import ACL, Policy, Grant
from boto.exception import S3ResponseError
from boto.exception import S3CreateError
from boto.s3.connection import Location
import boto.s3


config = None

class BucketTest(unittest.TestCase):    
    walrus = None
    test_user_id="123456"
    bucket_prefix = "bucket_test_123"
    s3tester = None
 
    @classmethod
    def setUpClass(cls):
        print_header("Setting up Bucket Test")
        
        host = config.endpoint
        path = config.path
        port = config.port
        access_key = config.access_key
        secret_key = config.secret_key
        
        print "Config = (" + host + ":" + str(port) + path + "--" + access_key + "--" + secret_key + ")"                
        #cls.walrus = S3Connection(host=host,path=path,port=port,aws_access_key_id=access_key,aws_secret_access_key=secret_key,is_secure=False,calling_format=OrdinaryCallingFormat(), debug=2)
        cls.walrus = eucaops.S3ops(config_file="config",password="foobar")        
        
        #Clean up existing buckets etc to make sure the test is clear.
        print "Cleaning existing buckets with " + BucketTest.bucket_prefix + " prefix from previous tests"
        try :
            listing = BucketTest.walrus.get_all_buckets()        
            for bucket in listing:
                if bucket.name.startswith(BucketTest.bucket_prefix):
                    print "Getting bucket listing for " + bucket.name   
                    key_list = bucket.list()
                    for k in key_list:
                        if isinstance(k, boto.s3.prefix.Prefix):
                            print "Skipping prefix"
                            continue
                        print "Deleting key: " + k.name
                        bucket.delete_key(k)
                    bucket.delete()
                else:
                    print "skipping bucket: " + bucket.name
        except S3ResponseError as e:
            print "Exception caught doing bucket cleanup."
                        
        print "Done with test setup\n\n"
    
    def test_bucket_get_put_delete(self):
        '''Tests creating and deleting buckets as well as getting the bucket listing'''
        test_bucket=self.bucket_prefix + "simple_test_bucket"
        print_header("Starting get/put/delete bucket test using bucket name: " + test_bucket)
 
        try :
            bucket = BucketTest.walrus.create_bucket(test_bucket)                
            if bucket == None:
                BucketTest.walrus.delete_bucket(test_bucket)
                self.fail(test_bucket + " was not created correctly")
        except (S3ResponseError, S3CreateError) as e:
            self.fail(test_bucket + " create caused exception: " + e)
        
        try :    
            bucket = BucketTest.walrus.get_bucket(test_bucket)
            if bucket == None:
                BucketTest.walrus.delete_bucket(test_bucket)
                self.fail(test_bucket +" was not fetched by get_bucket call")
        except S3ResponseError as e:
            BucketTest.walrus.delete_bucket(test_bucket)
            self.fail("Exception getting bucket" + e)
            
        
        BucketTest.walrus.delete_bucket(test_bucket)        
        try :
            if BucketTest.walrus.get_bucket(test_bucket) != None:
                BucketTest.walrus.delete_bucket(test_bucket)            
                self.fail("Delete of " + test_bucket + " failed, still exists")
        except S3ResponseError as e:
            print "Correctly got exception trying to get a deleted bucket! "
            
        print "Testing an invalid bucket names, calls should fail."
        try:
            bad_bucket = BucketTest.bucket_prefix + "bucket123/"
            BucketTest.create_bucket(bad_bucket)
            should_fail = True            
            try:
                BucketTest.delete_bucket(bad_bucket)
            except:
                print "Exception deleting bad bucket, shouldn't be here anyway. Test WILL fail"
                
            if should_fail:
                self.fail("Should have caught exception for bad bucket name: " + bad_bucket)
        except:
            print "Correctly caught the exception"
        
        try:
            bad_bucket = BucketTest.bucket_prefix + "bucket.123"
            BucketTest.create_bucket(bad_bucket)
            should_fail = True            
            try:
                BucketTest.delete_bucket(bad_bucket)
            except:
                print "Exception deleting bad bucket, shouldn't be here anyway. Test WILL fail"
                
            if should_fail:
                self.fail("Should have caught exception for bad bucket name: " + bad_bucket)
        except:
            print "Correctly caught the exception"
        
        try:
            bad_bucket = BucketTest.bucket_prefix + "bucket&123"
            BucketTest.create_bucket(bad_bucket)
            should_fail = True            
            try:
                BucketTest.delete_bucket(bad_bucket)
            except:
                print "Exception deleting bad bucket, shouldn't be here anyway. Test WILL fail"
                
            if should_fail:
                self.fail("Should have caught exception for bad bucket name: " + bad_bucket)
        except:
            print "Correctly caught the exception"
        
        try:
            bad_bucket = BucketTest.bucket_prefix + "bucket*123"
            BucketTest.create_bucket(bad_bucket)
            should_fail = True            
            try:
                BucketTest.delete_bucket(bad_bucket)
            except:
                print "Exception deleting bad bucket, shouldn't be here anyway. Test WILL fail"
                
            if should_fail:
                self.fail("Should have caught exception for bad bucket name: " + bad_bucket)
        except:
            print "Correctly caught the exception"
        
        try:
            bad_bucket = BucketTest.bucket_prefix + "/bucket123"
            BucketTest.create_bucket(bad_bucket)
            should_fail = True            
            try:
                BucketTest.delete_bucket(bad_bucket)
            except:
                print "Exception deleting bad bucket, shouldn't be here anyway. Test WILL fail"
                
            if should_fail:
                self.fail("Should have caught exception for bad bucket name: " + bad_bucket)
        except:
            print "Correctly caught the exception"
        
        print "Finished bucket get/put/delete test"
        print "Bucket GET/PUT/DELETE: PASSED"
        pass
            
    def test_bucket_acl(self):
        test_bucket = BucketTest.bucket_prefix + "acl_bucket_test"
        print_header('Starting ACL test with bucket name: ' + test_bucket)        
        try: 
            acl_bucket = BucketTest.walrus.create_bucket(test_bucket)
        except S3CreateError:
            print "Can't create the bucket, already exists. Deleting it an trying again"
            try :
                BucketTest.walrus.delete_bucket(test_bucket)            
                acl_bucket = BucketTest.walrus.create_bucket(test_bucket)
            except:
                print "Couldn't delete and create new bucket. Failing test"
                self.fail("Couldn't make the test bucket: " + test_bucket)
                                
        policy = acl_bucket.get_acl()
        
        if policy == None:
            self.fail("No acl returned")
        
        print policy
        #Check that the acl is correct: owner full control.
        if policy.acl.grants.__len__() > 1:
            BucketTest.walrus.delete_bucket(test_bucket)
            self.fail("Expected only 1 grant in acl. Found: " + policy.acl.grants.grants.__len__())

        if policy.acl.grants[0].display_name != "eucalyptus" or policy.acl.grants[0].permission != "FULL_CONTROL":
            BucketTest.walrus.delete_bucket(test_bucket)
            self.fail("Unexpected grant encountered: " + policy.acl.grants[0].display_name + "  " + policy.acl.grants[0].permission)
                    
        #upload a new acl for the bucket
        new_acl = policy
        new_acl.acl.add_user_grant(permission="READ", user_id=BucketTest.test_user_id, display_name="eucalyptus_test")        
        
        try:
            acl_bucket.set_acl(new_acl)                
            acl_check = acl_bucket.get_acl()
        except S3ResponseError:
            self.fail("Failed to set or get new acl")
        
        print "Got ACL: " + acl_check.acl.to_xml()
        
        expected_result='<AccessControlList><Grant><Grantee xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="CanonicalUser"><ID>INSERT_USER_ID_HERE</ID><DisplayName>eucalyptus</DisplayName></Grantee><Permission>FULL_CONTROL</Permission></Grant><Grant><Grantee xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="CanonicalUser"><ID>123456</ID><DisplayName></DisplayName></Grantee><Permission>READ</Permission></Grant></AccessControlList>'
        
        if acl_check == None or acl_check.acl.to_xml() != expected_result.replace("INSERT_USER_ID_HERE",BucketTest.test_user_id):
            BucketTest.walrus.delete_bucket(test_bucket) 
            self.fail("Incorrect acl length or acl not found: " + str(acl_check.acl.to_xml()))
        
        print "Grants 0 and 1: " + acl_check.acl.grants[0].to_xml() + " -- " + acl_check.acl.grants[1].to_xml()
        
        #Check each canned ACL string in boto to make sure Walrus does it right
        for acl in boto.s3.acl.CannedACLStrings:
            try: 
                acl_bucket.set_acl(acl)
                acl_check = acl_bucket.get_acl()
            except Exception as e:
                BucketTest.walrus.delete_bucket(test_bucket)
                self.fail("Got exception trying to set acl to " + acl + ": " + str(e))
            
            print "Expecting a " + acl + " acl, got: " + acl_check.acl.to_xml()
            
            expected_acl = test_utils.get_canned_acl(BucketTest.test_user_id,'private')
            if expected_acl == None:
                BucketTest.walrus.delete_bucket(test_bucket)
                self.fail("Got None when trying to generate expected acl for canned acl string: " + acl)
            
            
            if expected_acl != acl_check.acl:
                BucketTest.walrus.delete_bucket(test_bucket)
                self.fail("Invalid " + acl + " acl returned from Walrus: " + acl_check.acl.to_xml())
            else:
                print "Got correct acl for: " + acl            
        
        
        try:
            acl_bucket.set_acl('invalid-acl')
        except:            
            print "Caught expected exception from invalid canned-acl"
        
        
        
        BucketTest.walrus.delete_bucket(test_bucket)
        print "Bucket ACL: PASSED"      
        pass    
        
    def test_bucket_location(self):        
        test_bucket = BucketTest.bucket_prefix + "location_test_bucket"
        print_header('Starting bucket location test using bucket: ' + test_bucket)
        BucketTest.walrus.create_bucket(test_bucket)
        
        bucket = BucketTest.walrus.get_bucket(test_bucket)
        if bucket != None and (bucket.get_location() == Location.DEFAULT or bucket.get_location() == 'US'):
            BucketTest.walrus.delete_bucket(test_bucket)
        else:
            bucket.delete()
            self.fail("Bucket location test failed, could not get bucket or location is not 'US'")        
        
        test_bucket = BucketTest.bucket_prefix + "eu_location_test"
        bucket = BucketTest.walrus.create_bucket(test_bucket,location=Location.EU)
        
        if bucket == None:
            self.fail("Bucket creation at location EU failed")
        else:
            loc = bucket.get_location()
            
        if loc == Location.EU:
            print "Got correct bucket location, EU"
            bucket.delete()
        else:                        
            print "Incorrect bucket location, failing"
            bucket.delete()
            self.fail("Bucket location incorrect, expected: EU, got: " + loc)
            
        pass
        
    def test_bucket_logging(self):
        """This is not a valid test at the moment, logging requires at least an hour of time between logging enabled and file delivery of events to the dest bucket"""
        self.fail("Not valid test...yet")
        
        print "\n\nStarting bucket logging test"
        test_bucket = BucketTest.bucket_prefix + "logging_test_bucket"
        log_dest_bucket = BucketTest.bucket_prefix + "logging_destination_test_bucket"
        log_prefix = "log_prefix_test"

        try:
            bucket = BucketTest.walrus.create_bucket(test_bucket)
        except S3CreateError:
            print "Bucket exists, trying to delete and re-create"
            try:
                BucketTest.walrus.delete_bucket(test_bucket)
                bucket = BucketTest.walrus.create_bucket(test_bucket)
            except:
                print "Couldn't delete and create new bucket...failing"
                self.fail("Couldn't get clean bucket already existed and could not be deleted")
        
        try:        
            dest_bucket = BucketTest.walrus.create_bucket(log_dest_bucket)
        except S3CreateError:
            print "Bucket exists, trying to delete and re-create"
            try:
                BucketTest.walrus.delete_bucket(log_dest_bucket)
                dest_bucket = BucketTest.walrus.create_bucket(log_dest_bucket)
            except:
                print "Couldn't delete and create new bucket...failing"
                self.fail("Couldn't get clean bucket already existed and could not be deleted")
        
        log_delivery_policy = dest_bucket.get_acl()
        log_delivery_policy.acl.add_grant(Grant(type="Group",uri="http://acs.amazonaws.com/groups/s3/LogDelivery",permission="WRITE"))
        log_delivery_policy.acl.add_grant(Grant(type="Group",uri="http://acs.amazonaws.com/groups/s3/LogDelivery",permission="READ_ACP"))        
        dest_bucket.set_acl(log_delivery_policy)
        bucket.enable_logging(log_dest_bucket,target_prefix=log_prefix)        
        
        #test the logging by doing something that will require logging
        k = bucket.new_key('key1')
        k.set_contents_from_string('content123')
        
        k = bucket.new_key('key2')
        k.set_contents_from_string("content456")
        
        k = bucket.get_key('key1')
        result1 = k.get_contents_as_string()
        print "Got content:\n\t " + result1
        
        k = bucket.get_key('key2')
        result2 = k.get_contents_as_string()
        print "Got content:\n\t " + result2
        
        keylist = bucket.list()
        print "Listing keys..."
        for k in keylist:
            if isinstance(k, boto.s3.prefix.Prefix):
                print "Prefix found"
            else:
                print k.name
                
        #Allow some time for the op writes to be logged... this may need to be tweaked
        time.sleep(15)
        
        #Now check the log to be sure something was logged
        log_bucket = BucketTest.walrus.get_bucket(log_dest_bucket)
        for k in log_bucket.list(prefix=log_prefix):
            print k.name
            log_obj = log_bucket.get_key(k)
            print "Log content:\n\t" + k.get_contents_as_string()
        
        log_data = log_obj.get_content_as_string()
        print "Log data is: " + log_data        
                
    def test_bucket_versioning(self):
        test_bucket = BucketTest.bucket_prefix + "versioning_test_bucket"
        print_header('Testing bucket versioning using bucket:' + test_bucket)
        version_bucket = BucketTest.walrus.create_bucket(test_bucket)
        
        version_status = version_bucket.get_versioning_status().get("Versioning")
        
        #Test the default setup after bucket creation. Should be disabled.
        if version_status != None:
            version_bucket.delete()            
            self.fail("Expected versioning disabled, found: " + str(version_status))
        elif version_status == None:
            print("Null version status returned, correct since it should be disabled")
        
        #Turn on versioning, confirm that it is 'Enabled'
        version_bucket.configure_versioning(True)        
        version_status = version_bucket.get_versioning_status().get("Versioning")
        if version_status == None or version_status != "Enabled":
            version_bucket.delete()
            self.fail("Expected versioning enabled, found: " + str(version_status))
        elif version_status == None:
            version_bucket.delete()
            self.fail("Null version status returned")    
        print "Versioning of bucket is set to: " + version_status
        
        #Turn off/suspend versioning, confirm.
        version_bucket.configure_versioning(False)
        version_status = version_bucket.get_versioning_status().get("Versioning")
        if version_status == None or version_status != "Suspended":
            version_bucket.delete()
            self.fail("Expected versioning suspended, found: " + str(version_status))
        elif version_status == None:
            version_bucket.delete()
            self.fail("Null version status returned")    
        
        print "Versioning of bucket is set to: " + version_status        
        
        version_bucket.configure_versioning(True)
        version_status = version_bucket.get_versioning_status().get("Versioning")
        if version_status == None or version_status != "Enabled":
            version_bucket.delete()
            self.fail("Expected versioning enabled, found: " + str(version_status))    
        elif version_status == None:
            version_bucket.delete()
            self.fail("Null version status returned")    
        
        print "Versioning of bucket is set to: " + version_status
        
        version_bucket.delete()
        print "Bucket Versioning: PASSED"
               
    def test_bucket_key_listing_paging(self):
        """Test paging of long results lists correctly and in alpha order"""        
        test_bucket_name = BucketTest.bucket_prefix + "pagetestbucket"
        print_header('Testing bucket key listing pagination using bucket: ' + test_bucket_name)
        
        try:
            testbucket = BucketTest.walrus.create_bucket(bucket_name=test_bucket_name)
        except S3CreateError:
            print "Bucket already exists, getting it"
            try:
                testbucket = BucketTest.walrus.get_bucket(bucket_name=test_bucket_name)
            except S3ResponseError as err:
                print "Fatal error: could not get bucket or create it"
                for b in BucketTest.walrus.get_all_buckets():
                    print b.name                    
                self.fail("Could not get bucket, " + test_bucket_name + " to start test: " + err.error_message)                       
                        
        key_name_prefix = "testkey"
        
        for i in range(100):
            key_name = key_name_prefix + str(i)
            print "creating object: " + key_name
            testbucket.new_key(key_name).set_contents_from_string("testcontents123testtesttesttest")
            
        for i in range(100):
            key_name = key_name_prefix + "/key" + str(i)
            print "creating object: " + key_name
            testbucket.new_key(key_name).set_contents_from_string("testafadsoavlsdfoaifafdslafajfaofdjasfd")
                
        key_list = testbucket.get_all_keys(max_keys=50)        
        print "Got " + str(len(key_list)) + " entries back"
        
        if len(key_list) != 50:
            self.fail("Expected 50 keys back, got " + str(len(key_list)))

        for k in key_list:
            print k.key()            
        
        for i in range(100):
            key_name = key_name_prefix + str(i)
            print "Deleting key: " + key_name
            testbucket.delete_key(key_name)
            key_name = key_name_prefix + "/key" + str(i)
            print "Deleting key: " + key_name
            testbucket.delete_key(key_name)
                                
        print "Cleaning up the bucket"
        
        key_list = testbucket.get_all_keys()
        
        for k in key_list:
            print "Deleting key: " + k.key()
            testbucket.delete_key(k)

        print "Deleting the bucket"
        self.walrus.delete_bucket(testbucket)  
                    
    def test_bucket_key_list_delim_prefix(self):
        """Tests the prefix/delimiter functionality of key listings and parsing"""
        test_bucket_name = BucketTest.bucket_prefix + "testbucketdelim"
        print_header('Testing bucket key list delimiters and prefixes using bucket: ' + test_bucket_name)        
        
        try: 
            testbucket = self.walrus.create_bucket(bucket_name=test_bucket_name)
        except S3CreateError:
            print "bucket already exists, using it"
            try:
                testbucket = self.walrus.get_bucket(bucket_name=test_bucket_name)
            except S3ResponseError as err:
                print "Fatal error: could to create or get bucket"
                for b in self.walrus.get_all_buckets():
                    print b.name                
                self.fail("Could not setup bucket, " + test_bucket_name + " for test: " + err.error_message )

        prefix = "users"
        delim = "/"
        
        for i in range(10):
            tmp = str(i)
            print "adding keys iteration " + tmp
            key = testbucket.new_key("testobject" + tmp)
            key.set_content_from_string("adlsfjaoivajsdlajsdfiajsfdlkajsfkajdasd")
            
            key = testbucket.new_key(prefix + "testkey" + tmp)
            key.set_content_from_string("asjaoidjfafdjaoivnw")
            
            key = testbucket.new_key(prefix + delim + "object" + tmp)
            key.set_content_from_string("avjaosvdafajsfd;lkaj")
            
            key = testbucket.new_key(prefix + delim + "objects" + delim + "photo" + tmp + ".jpg")
            key.set_content_from_string("aoiavsvjasldfjadfiajss")
    
        keys = testbucket.get_all_keys(prefix=prefix, delimiter=delim, max_keys=10)
        print "Prefix with 10 keys max returned: " + keys.size() + " results"
        
        for k in keys:
            print k.key()
            
        keys = testbucket.get_all_keys(prefix=prefix, delimiter=delim, max_keys=20)
        print "Prefix with 20 keys max returned: " + keys.size() + " results"
        
        for k in keys:
            print k.key()
            
        print "Cleaning up the bucket"
        for i in range(10):
            testbucket.delete_key("testobject" + str(i))
            testbucket.delete_key(prefix + "testkey" + str(i))
            testbucket.delete_key(prefix + delim + "object" + str(i))
            testbucket.delete_key(prefix + delim + "objects" + delim + "photo" + str(i) + ".jpg")

        print "Deleting the bucket"
        self.walrus.delete_bucket(testbucket)
    
    def test_list_multipart_uploads(self):
        self.fail("Feature Not implemented")

    def test_bucket_lifecycle(self):        
        self.fail("Feature Not implemented")
        
    def test_bucket_policy(self):
        self.fail("Feature Not implemented")
        
    def test_bucket_website(self):
        self.fail("FeatureNot implemented")        

    def testName(self):
        print "BucketTest"
        return "BucketTest"
    
def suite():
    #tests = ['test_bucket_get_put_delete', 'test_bucket_acl', 'test_bucket_versioning', 'test_bucket_logging', 'test_bucket_location', 'test_bucket_key_listing_paging', 'test_bucket_key_list_delim_prefix' ]
    tests = ['test_bucket_get_put_delete', 'test_bucket_acl', 'test_bucket_versioning', 'test_bucket_location']  
    return unittest.TestSuite(map(BucketTest, tests))

if __name__ == "__main__":
    config = test_utils.get_config()
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)  
    #unittest.main()
    