#!/usr/bin/env python

#
###########################################
#                                         #
#   objectstorage/S3 Bucket Test Cases    #
#                                         #
###########################################

#Author: Zach Hill <zach@eucalyptus.com>
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


class BucketTestSuite(EutesterTestCase):
    
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

        self.bucket_prefix = "eutester-bucket-test-suite-" + str(int(time.time()))
        self.buckets_used = set()
        
    def test_bucket_get_put_delete(self):
        '''
        Method: Tests creating and deleting buckets as well as getting the bucket listing
        '''
        test_bucket=self.bucket_prefix + "-simple-test-bucket"
        self.buckets_used.add(test_bucket)
        self.tester.debug("Starting get/put/delete bucket test using bucket name: " + test_bucket)
 
        if self.args.endpoint:
            # If testing against any region besides us-east-1, the location
            # parameter of a create bucket request cannot be blank (us-east-1).
            self.tester.info('WARNING: The following AWS tests will correctly fail if we are testing against any region')
            self.tester.info('besides us-east-1 (endpoint s3.amazonaws.com), because the expected results are for us-east-1.')
        try :
            bucket = self.tester.s3.create_bucket(test_bucket)                
            if bucket == None:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail(test_bucket + " was not created correctly")
        except (S3ResponseError, S3CreateError) as e:
            self.fail(test_bucket + " create caused exception: " + str(e))
        
        try :    
            bucket = self.tester.s3.get_bucket(test_bucket)
            if bucket == None:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail(test_bucket +" was not fetched by get_bucket call")
        except S3ResponseError as e:
            self.tester.s3.delete_bucket(test_bucket)
            self.fail("Exception getting bucket" + str(e))
            
        
        self.tester.s3.delete_bucket(test_bucket)        
        try :
            if self.tester.s3.get_bucket(test_bucket) != None:
                self.tester.s3.delete_bucket(test_bucket)            
                self.fail("Delete of " + test_bucket + " failed, still exists")
        except S3ResponseError as e:
            self.tester.debug( "Correctly got exception trying to get a deleted bucket! " )
            
        self.tester.debug( "Testing an invalid bucket names, calls should fail." )
        def test_creating_bucket_invalid_names(bad_bucket):
            should_fail = False
            try:
                bucket = self.tester.create_bucket(bad_bucket)
                should_fail = True            
                try:
                    self.tester.delete_bucket(bucket)
                except:
                    self.tester.debug( "Exception deleting bad bucket, shouldn't be here anyway. Test WILL fail" )
            except Exception as e:
                self.tester.debug("Correctly caught the exception for bucket name '" + bad_bucket + "' Reason: " + e.reason)
            if should_fail:
                self.fail("Should have caught exception for bad bucket name: " + bad_bucket)

        # with the EUCA-8864 fix, a new property 'objectstorage.bucket_naming_restrictions'
        # has been introduced, now 'bucket..123', 'bucket.' are actually valid bucket names
        # when using 'extended' naming convention.
        # http://docs.aws.amazon.com/AmazonS3/latest/dev/BucketRestrictions.html
        # when DNS is not being used, for now buckets can be created with bucket
        # names like '/bucket123', 'bucket123/', see EUCA-8863
        # TODO check what bucket naming convention is being used for the test
        for bad_bucket in ["bucket&123", "bucket*123"]:
            test_creating_bucket_invalid_names(self.bucket_prefix + bad_bucket)

        """
        Test creating bucket with null name
        """
        try:
            null_bucket_name = ""
            bucket_obj = self.tester.create_bucket(null_bucket_name)
            self.tester.sleep(10)
            if bucket_obj:
                self.fail("Should have caught exception for creating bucket with empty-string name.")
        except S3ResponseError as e:
            assert (e.status == 405), 'Expected response status code to be 405, actual status code is ' + str(e.status)
            assert (re.search("MethodNotAllowed", e.code)), "Incorrect exception returned when creating bucket with null name."
        except Exception, e:
            self.tester.debug("Failed due to EUCA-7059 " + str(e))

    def test_bucket_acl(self):
        '''
        Tests bucket ACL management and adding/removing from the ACL with both valid and invalid usernames
        '''
        
        test_bucket = self.bucket_prefix + 'acl_bucket_test'
        self.buckets_used.add(test_bucket)
        test_user_id = self.tester.s3.get_canonical_user_id()     
        self.tester.debug('Starting ACL test with bucket name: ' + test_bucket + ' and userid ' + test_user_id)
        
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
            self.fail('No acl returned')
        
        self.tester.debug( policy )
        #Check that the acl is correct: owner full control.
        if len(policy.acl.grants) > 1:
            self.tester.s3.delete_bucket(test_bucket)
            self.fail('Expected only 1 grant in acl. Found: ' + policy.acl.grants.grants.__len__())

        if policy.acl.grants[0].id != test_user_id or policy.acl.grants[0].permission != 'FULL_CONTROL':
            self.tester.s3.delete_bucket(test_bucket)
            self.fail('Unexpected grant encountered: ' + policy.acl.grants[0].display_name + ' ' + policy.acl.grants[0].permission + ' ' + policy.acl.grants[0].id)

        #Get the info on the owner from the ACL returned
        owner_display_name = policy.acl.grants[0].display_name
        owner_id = policy.acl.grants[0].id
                                    
        #upload a new acl for the bucket
        # Commented out this test because Euca, AWS West, and AWS East
        # all update the grants differently.
        # Regardless, nothing changes functionally, owner always retains full control.
        # So it's not a very useful test anyway.
        #new_acl = policy
        #new_user_display_name = owner_display_name
        #new_user_id = owner_id
        #new_acl.acl.add_user_grant(permission="READ", user_id=new_user_id, display_name=new_user_display_name)
        #try:
        #    acl_bucket.set_acl(new_acl)
        #    acl_check = acl_bucket.get_acl()
        #except S3ResponseError:
        #    self.fail("Failed to set or get new acl")
        #
        #self.tester.info( "Got ACL: " + acl_check.acl.to_xml() )
        #    
        #if acl_check == None or not self.tester.check_acl_equivalence(acl1=acl_check.acl, acl2=new_acl.acl):
        #    self.tester.s3.delete_bucket(test_bucket)
        #    self.fail("Incorrect acl length or acl not found\n. Got bucket ACL:\n" + acl_check.acl.to_xml() + "\nExpected:" + new_acl.acl.to_xml())
        #else:
        #    self.tester.info("Got expected basic ACL addition")
        #
        #self.tester.info( "Grants 0 and 1: " + acl_check.acl.grants[0].to_xml() + " -- " + acl_check.acl.grants[1].to_xml() )
        
        #Check each canned ACL string in boto to make sure Walrus does it right
        for acl in boto.s3.acl.CannedACLStrings:
            #The bucket-owner-* canned ACLs apply only to objects, not buckets 
            if acl == "bucket-owner-read" or acl == "bucket-owner-full-control":
                continue
            self.tester.info('Testing canned acl: ' + acl)
            try:
                acl_bucket.set_acl(acl)
                acl_check = acl_bucket.get_acl()
            except Exception as e:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail("Got exception trying to set acl to " + acl + ": " + str(e))
            
            self.tester.info( "Set canned-ACL: " + acl + " -- Got ACL from service: " + acl_check.acl.to_xml() )            
            expected_acl = self.tester.get_canned_acl(bucket_owner_id=owner_id,canned_acl=acl, bucket_owner_display_name=owner_display_name)
                        
            if expected_acl == None:
                self.tester.s3.delete_bucket(test_bucket)
                self.fail("Got None when trying to generate expected acl for canned acl string: " + acl)
                        
            if not self.tester.check_acl_equivalence(acl1=expected_acl, acl2=acl_check.acl):
                self.tester.s3.delete_bucket(test_bucket)
                self.fail("Invalid " + acl + " acl returned from Walrus:\n" + acl_check.acl.to_xml() + "\nExpected\n" + expected_acl.to_xml())
            else:
                self.tester.debug( "Got correct acl for: " + acl  )        
        
        try:
            acl_bucket.set_acl('invalid-acl')
            self.fail('Did not catch expected exception for invalid canned-acl')            
        except:
            self.tester.debug( "Caught expected exception from invalid canned-acl" )        
        
        
        self.tester.s3.delete_bucket(test_bucket)
        self.buckets_used.remove(test_bucket)
        self.tester.debug( "Bucket ACL: PASSED"  )    
        pass    
    
    def test_bucket_key_list_delim_prefix(self):
        """Tests the prefix/delimiter functionality of key listings and parsing"""
        test_bucket_name = self.bucket_prefix + "testbucketdelim"
        self.buckets_used.add(test_bucket_name)
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
        
        
    def test_bucket_location(self):        
        """Tests the ability to create a bucket in a specific region"""
        if self.args.endpoint:
            # If testing against any region besides us-east-1, the location
            # parameter of a create bucket request cannot be blank (us-east-1).
            self.tester.info('WARNING: The following AWS tests will correctly fail if we are testing against any region')
            self.tester.info('besides us-east-1 (endpoint s3.amazonaws.com), because the expected results are for us-east-1.')
        test_bucket = self.bucket_prefix + ".undefined-location-test"
        self.tester.debug('Starting test of bucket creation with no location defined, using bucket: ' + test_bucket)
        self.tester.s3.create_bucket(test_bucket)
        bucket = self.tester.s3.get_bucket(test_bucket)
        if bucket != None and (bucket.get_location() == Location.DEFAULT):
            self.tester.debug('Bucket location is correct: US East 1 (default)')
            self.tester.s3.delete_bucket(test_bucket)
        else:
            bucket.delete()
            self.fail("Bucket location test failed, could not get bucket or location is not US East 1 (default)")        
        
        test_bucket = self.bucket_prefix + ".us-east-location-test"
        self.tester.debug('Starting test of bucket creation defining US East (default) location, using bucket: ' + test_bucket)
        self.tester.s3.create_bucket(test_bucket,location=Location.DEFAULT)
        bucket = self.tester.s3.get_bucket(test_bucket)
        if bucket != None and (bucket.get_location() == Location.DEFAULT):
            self.tester.debug('Bucket location is correct: US East 1 (default)')
            self.tester.s3.delete_bucket(test_bucket)
        else:
            bucket.delete()
            self.fail("Bucket location test failed, could not get bucket or location is not US East 1 (default)")        
 
        if self.args.endpoint:
            # Skip the test for creating a bucket in a different region, 
            # if testing against AWS. In AWS, if we create a bucket in another
            # region, we can only delete it if we set up a new connection
            # to that region and then delete it. New connections are outside
            # the scope of these bucket tests.
            self.tester.info('Skipping AWS test of bucket creation in a non-default region (EU).')
        else:
            test_bucket = self.bucket_prefix + ".eu-location-test"
            self.tester.debug('Starting test of bucket creation defining EU location, using bucket: ' + test_bucket)
            bucket = self.tester.s3.create_bucket(test_bucket,location=Location.EU)
            self.buckets_used.add(test_bucket)
            if bucket == None:
                self.fail("Bucket creation at location EU failed")
            else:
                loc = bucket.get_location()
            
            if loc == Location.EU:
                self.tester.debug('Bucket location is correct: EU')
                bucket.delete()
            else:                        
                bucket.delete()
                self.fail("Bucket location incorrect, expected: EU, got: " + loc)
            self.buckets_used.remove(test_bucket)
        self.tester.debug( "Bucket location test: PASSED"  )    
        pass
        
    def test_bucket_logging(self):
        """This is not a valid test at the moment, logging requires at least an hour of time between logging enabled and file delivery of events to the dest bucket"""
        self.tester.info("\n\nStarting bucket logging test")
        test_bucket = self.bucket_prefix + "logging_test_bucket"
        log_dest_bucket = self.bucket_prefix + "logging_destination_test_bucket"
        self.buckets_used.add(test_bucket)
        self.buckets_used.add(log_dest_bucket)
        
        log_prefix = "log_prefix_test"

        try:
            bucket = self.tester.s3.create_bucket(test_bucket)
        except S3CreateError:
            self.tester.info("Bucket exists, trying to delete and re-create")
            try:
                self.tester.s3.delete_bucket(test_bucket)
                bucket = self.tester.s3.create_bucket(test_bucket)
            except:
                self.tester.info("Couldn't delete and create new bucket...failing")
                self.fail("Couldn't get clean bucket already existed and could not be deleted")
        
        try:        
            dest_bucket = self.tester.s3.create_bucket(log_dest_bucket)
        except S3CreateError:
            self.tester.info("Bucket exists, trying to delete and re-create")
            try:
                self.tester.s3.delete_bucket(log_dest_bucket)
                dest_bucket = self.tester.s3.create_bucket(log_dest_bucket)
            except:
                self.tester.info("Couldn't delete and create new bucket...failing")
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
        self.tester.info("Got content:\n\t " + result1)
        
        k = bucket.get_key('key2')
        result2 = k.get_contents_as_string()
        self.tester.info("Got content:\n\t " + result2)
        
        keylist = bucket.list()
        self.tester.info("Listing keys...")
        for k in keylist:
            if isinstance(k, boto.s3.prefix.Prefix):
                self.tester.info("Prefix found")
            else:
                self.tester.info('Key--' + k.name)
                
        #Allow some time for the op writes to be logged... this may need to be tweaked
        time.sleep(15)
        
        #Now check the log to be sure something was logged
        log_bucket = self.tester.s3.get_bucket(log_dest_bucket)
        for k in log_bucket.list(prefix=log_prefix):
            self.tester.info('Key -- ' + k.name)
            log_obj = log_bucket.get_key(k)
            self.tester.info("Log content:\n\t" + k.get_contents_as_string())
        
        log_data = log_obj.get_content_as_string()
        self.tester.info('Log data is: ' + log_data)

        self.tester.info('Deleting used bucket')
                
    def test_bucket_versioning(self):
        test_bucket = self.bucket_prefix + "versioning_test_bucket"
        self.tester.info('Testing bucket versioning using bucket:' + test_bucket)
        version_bucket = self.tester.s3.create_bucket(test_bucket)
        self.buckets_used.add(test_bucket)

        #Test the default setup after bucket creation. Should be disabled.
        version_status = version_bucket.get_versioning_status().get("Versioning")
        if version_status != None:
            version_bucket.delete()            
            self.fail("Expected versioning disabled (empty), found: " + str(version_status))
        elif version_status == None:
            self.tester.info("Null version status returned, may be correct since it should be disabled")
        
        #Turn on versioning, confirm that it is 'Enabled'
        version_bucket.configure_versioning(True)        
        #When testing against AWS, the versioning status seems to be eventually consistent.
        #Setting it and immediately getting it sometimes returns the wrong value.
        if self.args.endpoint:
            time.sleep(5)
        version_status = version_bucket.get_versioning_status().get("Versioning")
        if version_status == None or version_status != "Enabled":
            version_bucket.delete()
            self.fail("Expected versioning enabled, found: " + str(version_status))
        elif version_status == None:
            version_bucket.delete()
            self.fail("Null version status returned")    
        self.tester.info("Versioning of bucket is set to: " + version_status)
        
        #Turn off/suspend versioning, confirm.
        version_bucket.configure_versioning(False)
        if self.args.endpoint:
            time.sleep(5)
        version_status = version_bucket.get_versioning_status().get("Versioning")
        if version_status == None or version_status != "Suspended":
            version_bucket.delete()
            self.fail("Expected versioning suspended, found: " + str(version_status))
        elif version_status == None:
            version_bucket.delete()
            self.fail("Null version status returned")    
        
        self.tester.info("Versioning of bucket is set to: " + version_status)        
        
        #Turn on versioning again, confirm.
        version_bucket.configure_versioning(True)
        if self.args.endpoint:
            time.sleep(5)
        version_status = version_bucket.get_versioning_status().get("Versioning")
        if version_status == None or version_status != "Enabled":
            version_bucket.delete()
            self.fail("Expected versioning enabled, found: " + str(version_status))    
        elif version_status == None:
            version_bucket.delete()
            self.fail("Null version status returned")    
        
        self.tester.info("Versioning of bucket is set to: " + version_status)
        
        version_bucket.delete()
        self.buckets_used.remove(test_bucket)
        self.tester.info("Bucket Versioning: PASSED")
               
    def test_bucket_key_listing_paging(self):
        """Test paging of long results lists correctly and in alpha order"""        
        test_bucket_name = self.bucket_prefix + "pagetestbucket"
        self.buckets_used.add(test_bucket_name)
        self.tester.info('Testing bucket key listing pagination using bucket: ' + test_bucket_name)
        
        try:
            testbucket = self.tester.s3.create_bucket(bucket_name=test_bucket_name)
        except S3CreateError:
            self.tester.info("Bucket already exists, getting it")
            try:
                testbucket = self.tester.s3.get_bucket(bucket_name=test_bucket_name)
            except S3ResponseError as err:
                self.tester.info("Fatal error: could not get bucket or create it")
                for b in self.tester.s3.get_all_buckets():
                    self.tester.info('Bucket -- ' + b.name )                   
                self.fail("Could not get bucket, " + test_bucket_name + " to start test: " + err.error_message)                       
                        
        key_name_prefix = "testkey"
        
        for i in range(100):
            key_name = key_name_prefix + str(i)
            self.tester.info("creating object: " + key_name)
            testbucket.new_key(key_name).set_contents_from_string("testcontents123testtesttesttest")
            
        for i in range(100):
            key_name = key_name_prefix + "/key" + str(i)
            self.tester.info("creating object: " + key_name)
            testbucket.new_key(key_name).set_contents_from_string("testafadsoavlsdfoaifafdslafajfaofdjasfd")
                
        key_list = testbucket.get_all_keys(max_keys=50)        
        self.tester.info("Got " + str(len(key_list)) + " entries back")
        
        for k in key_list:
            assert isinstance(k, Key)
            self.tester.info('Found key -- ' + k.name)
        
        if len(key_list) != 50:
            self.fail("Expected 50 keys back, got " + str(len(key_list)))
            

        
        for i in range(100):
            key_name = key_name_prefix + str(i)
            self.tester.info("Deleting key: " + key_name)
            testbucket.delete_key(key_name)
            key_name = key_name_prefix + "/key" + str(i)
            self.tester.info("Deleting key: " + key_name)
            testbucket.delete_key(key_name)
                                
        self.tester.info("Cleaning up the bucket")
        
        key_list = testbucket.get_all_keys()
        
        for k in key_list:
            self.tester.info("Deleting key: " + k.name)
            testbucket.delete_key(k)

        self.tester.info("Deleting the bucket")
        self.tester.s3.delete_bucket(testbucket)
        self.buckets_used.add(test_bucket_name)
        
    def test_list_multipart_uploads(self):
        self.fail("Feature Not implemented")

    def test_bucket_lifecycle(self):
        lifecycle_id = 'eutester lifecycle test'
        lifecycle_prefix = 'eulifecycle'
        lifecycle_status = 'Enabled'
        lifecycle_expiration = 1
        bucket_name = self.bucket_prefix + "lifecycle-test0"
        self.buckets_used.add(bucket_name)
        bucket = self.tester.create_bucket(bucket_name)

        lifecycle = Lifecycle()
        lifecycle.add_rule(lifecycle_id, lifecycle_prefix, lifecycle_status, lifecycle_expiration)
        bucket.configure_lifecycle(lifecycle)
        responses = bucket.get_lifecycle_config()
        assert (len(responses) == 1), 'found not true'
        lifecycle_response = responses[0]
        assert (lifecycle_response.id == lifecycle_id), "Expected lifecycle Id to be: " + lifecycle_id + " found " + lifecycle_response.id
        assert (lifecycle_response.prefix == lifecycle_prefix), "Expected lifecycle prefix to be: " + lifecycle_prefix + " found " + lifecycle_response.prefix
        assert (lifecycle_response.status == lifecycle_status), "Expected lifecycle status to be: " + lifecycle_status + " found " + lifecycle_response.status
        assert (lifecycle_response.expiration.days == lifecycle_expiration), "Expected lifecycle expiration days to be: " + str(lifecycle_expiration) + " found " + str(lifecycle_response.expiration.days)

        bucket.delete_lifecycle_configuration()
        assert (len(responses) == 1), "Expected no configuration, found " + len(responses) + " configuration"

        # multiple rules
        bucket_name = self.bucket_prefix + "lifecycle-test1"
        bucket = self.tester.create_bucket(bucket_name)
        self.buckets_used.add(bucket_name)
        date = '2022-10-12T00:10:10.011Z'
        lifecycle = Lifecycle()
        lifecycle.add_rule("1", "1/", "Enabled", 1)
        lifecycle.add_rule("2", "2/", "Enabled", Expiration(days=2))
        lifecycle.add_rule("3", "3/", "Enabled", Expiration(date=date))
        lifecycle.add_rule("4", "4/", "Disabled", Expiration(date=date))
        bucket.configure_lifecycle(lifecycle)
        lifecycle_responses = bucket.get_lifecycle_config()
        if lifecycle_responses < 0:
            self.fail("no lifecycle found!")

        for response in lifecycle_responses:
            if response.id == "1":
                assert (response.prefix == "1/"), "Expected lifecycle prefix to be: " + "1/" + " found: " + response.prefix
                assert (response.status == "Enabled"), "Expected lifecycle status to be: " + "Enabled" + " found " + response.status
                assert (response.expiration.days == 1), "Expected lifecycle expiration days to be: " + str(1) + " found " + str(response.expiration.days)
            elif response.id == "2":
                assert (response.prefix == "2/"), "Expected lifecycle prefix to be: " + "2/" + " found: " + response.prefix
                assert (response.status == "Enabled"), "Expected lifecycle status to be: " + "Enabled" + " found: " + response.status
                assert (response.expiration.days == 2), "Expected lifecycle expiration days to be: " + str(2) + " found " + str(response.expiration.days)
            elif response.id == "3":
                assert (response.prefix == "3/"), "Expected lifecycle prefix to be: " + "3/" + " found: " + response.prefix
                assert (response.status == "Enabled"), "Expected lifecycle status to be: " + "Enabled" + " found " + response.status
                assert (response.expiration.date == date), "Expected lifecycle expiration days to be: " + date + " found " + str(response.expiration.date)
            elif response.id == "4":
                assert (response.prefix == "4/"), "Expected lifecycle prefix to be: " + "4/" + " found: " + response.prefix
                assert (response.status == "Disabled"), "Expected lifecycle status to be: " + "Disabled" + " found " + response.status
                assert (response.expiration.date == date), "Expected lifecycle expiration days to be: " + date + " found " + str(response.expiration.date)
            else:
                self.fail("no response found")

        self.debug("Cleaning up used buckets")
        for bucket in self.buckets_used:
            self.tester.clear_bucket(bucket)

    def test_bucket_policy(self):
        self.fail("Feature Not implemented")
        
    def test_bucket_website(self):
        self.fail("FeatureNot implemented")
    
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
    testcase = BucketTestSuite()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or [ 'test_bucket_get_put_delete', \
                                   'test_bucket_acl', \
                                   'test_bucket_key_list_delim_prefix', \
                                   'test_bucket_key_listing_paging', \
                                   'test_bucket_location', \
                                   'test_bucket_versioning']
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )
    ### Run the EutesterUnitTest objects

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
