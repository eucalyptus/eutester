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

import test_utils
from test_utils import print_header
from test_utils import get_config
from test_utils import clean_bucket
from test_utils import check_hashes
import unittest
import sys, argparse, string
import time, random, array
import hashlib
import boto
from test_utils import print_header
from boto.s3.connection import OrdinaryCallingFormat
from boto.s3.connection import S3Connection
from boto.s3.bucket import Bucket
from boto.s3.key import Key
from boto.s3.acl import ACL
from boto.s3.acl import Policy
from boto.s3.acl import Grant
from boto.s3.prefix import Prefix
from boto.exception import S3ResponseError
from boto.exception import S3CreateError
from boto.s3.connection import Location

#Note: test objects with url-encoded chars at start, middle, and end of obj key.
class ObjectTest(unittest.TestCase):
    conn = None
    config = None
    test_bucket_name = ""
    test_bucket = None
    test_user_id="123456"
    bucket_prefix = "object_test"
    test_object_data = None
    data_size = 1000
    
    @classmethod
    def setUpClass(cls):
        print_header("Setting up Bucket Test")
        random.seed(time.time())
        host = config.endpoint
        path = config.path
        port = config.port
        access_key = config.access_key
        secret_key = config.secret_key
        
        print "Config = (" + host + ":" + str(port) + path + "--" + access_key + "--" + secret_key + ")"                
        cls.walrus = S3Connection(host=host,path=path,port=port,aws_access_key_id=access_key,aws_secret_access_key=secret_key,is_secure=False,calling_format=OrdinaryCallingFormat(), debug=2)
        
        #Create some test data for the objects
        cls.test_object_data = ""
        for i in range(0, cls.data_size):
            cls.test_object_data += chr(random.randint(32,126))
            
        print "Generated data for objects: " + cls.test_object_data
        
        #TODO: delete all versions and delete markers so that a versioned bucket can be deleted
        #Clean up existing buckets etc to make sure the test is clear.
        print "Cleaning existing buckets with " + ObjectTest.bucket_prefix + " prefix from previous tests"
        try :
            listing = ObjectTest.walrus.get_all_buckets()        
            for bucket in listing:
                if bucket.name.startswith(ObjectTest.bucket_prefix):
                    clean_bucket(bucket)
                else:
                    print "skipping bucket: " + bucket.name
        except S3ResponseError as e:
            print "Exception caught doing bucket cleanup."
                        
        print "Done with test setup\n\n"

    def setUp(self):
        """Initialize the env for a test with a new, randomly named bucket"""
        print_header("Generating bucket for test")
        self.test_bucket_name = ObjectTest.bucket_prefix + str(random.randint(0,100))
        self.test_bucket = self.walrus.create_bucket(self.test_bucket_name)
        print "Random bucket: " + self.test_bucket_name
    
    def print_key_info(self, keys=None):
        for key in keys:
            print "Key=" + key.key + " -- version= " + key.version_id + " -- eTag= " + key.etag + " -- ACL= " + key.get_xml_acl() 
    
    def put_object(self, bucket=None, object_key=None, object_data=None):
        """Puts an object with the specified name and data in the specified bucket"""
        if bucket == None:
            raise Exception("Cannot put object without proper bucket reference")
        
        try :
            key = Key(bucket=bucket,name=object_key)
            key.set_contents_from_string(object_data)                        
            return key.etag
        except Exception as e:
            print "Exception occured during 'PUT' of object " + object_key + " into bucket " + bucket.name + ": " + e.message
            return None
        
     
    def enable_versioning(self, bucket):
        """Enable versioning on the bucket, checking that it is not already enabled and that the operation succeeds."""
        vstatus = bucket.get_versioning_status()
        if vstatus != None and len(vstatus.keys()) > 0 and vstatus['Versioning'] != None and vstatus['Versioning'] != 'Disabled':
            print "Versioning status should be null/Disabled, found: " + vstatus['Versioning']
            return False
        else:
            print "Bucket versioning is Disabled"
        
        #Enable versioning
        bucket.configure_versioning(True)
        if bucket.get_versioning_status()['Versioning'] == 'Enabled':
            print "Versioning status correctly set to enabled"
            return True
        else:
            print "Versioning status not enabled, should be."
            return False
        return False
    
    def suspend_versioning(self, bucket):
        """Suspend versioning on the bucket, checking that it is previously enabled and that the operation succeeds."""
        if bucket.get_versioning_status()['Versioning'] == 'Enabled':
            print "Versioning status correctly set to enabled"
        else:
            print "Versioning status not enabled, should be. Can't suspend if not enabled...."
            return False
    
        #Enable versioning
        bucket.configure_versioning(False)
        if bucket.get_versioning_status()['Versioning'] == 'Suspended':
            print "Versioning status correctly set to suspended"
            return True
        else:
            print "Versioning status not suspended."
            return False
        return False 
             
    def check_version_listing(self, version_list, total_expected_length):
        """Checks a version listing for both completeness and ordering as well as pagination if required"""
        
        print "Checking bucket version listing. Listing is " + str(len(version_list)) + " entries long"
        if total_expected_length >= 1000:
            assert(len(version_list) == 999)
        else:
            assert(len(version_list) == total_expected_length)
        
        prev_obj = None
        should_fail = None
        for obj in version_list:
            if isinstance(obj,Key):
                print "Key: " + obj.name + " -- " + obj.version_id + "--" + obj.last_modified                
                if prev_obj != None:
                    if self.compare_versions(prev_obj, obj) > 0:
                        should_fail = obj
                prev_obj = obj 
            else:
                print "Not a key, skipping: " + str(obj)
            
        return should_fail
        
        
    def compare_versions(self, key1, key2):
        """
        Returns -1 if key1 < key2, 0 if equal, and 1 if key1 > key2. 
        Compares names lexicographically, if equal, compares date_modified if versions are different. 
        If version_id and name are equal then key1 = key2
        If an error occurs or something is wrong, returns None
        """
        if key1.name > key2.name:
            return 1
        elif key1.name < key2.name:
            return -1
        else:
            if key1.version_id == key2.version_id:
                return 0
            else:
                if key1.last_modified > key2.last_modified:
                    return 1
                elif key1.last_modified < key2.last_modified:
                    return -1
        return None
    
    def test_object_basic_ops(self):
        """Tests basic object get/put/delete/head on a normal bucket"""
        print_header("Basic Object Operations Test (GET/PUT/HEAD)")
        if self.test_bucket == None:
            self.fail("Error: test_bucket not set, cannot run test")
            
        #Test PUT & GET
        testkey="testkey1"
        self.put_object(bucket=self.test_bucket, object_key=testkey, object_data=self.test_object_data)
        
        ret_key = self.test_bucket.get_key(testkey)
        ret_content = ret_key.get_contents_as_string()
        
        if ret_content == ObjectTest.test_object_data:
            print "Set content = get content, put passed"
        else:
            if ret_content != None:
                print "Got content: " + ret_content
            else:
                print "No content returned"
            print "Expected content: " + ObjectTest.test_object_data
            self.fail("Put content not the same as what was returned")
        
        #Test HEAD
        key_meta = self.test_bucket.get_key(testkey)
        if key_meta != ret_key:
            print "Something is wrong, the HEAD operation returned different metadata than the GET operation"
        else:
            print "HEAD meta = GET meta, all is good"
        
        #Test copy operation (GET w/source headers)
        new_key = "testkey2"
        self.test_bucket.copy_key(new_key, self.test_bucket_name,testkey)
        keylist = self.test_bucket.list()
        counter = 0
        for k in keylist:
            if isinstance(k, Prefix):
                print "Prefix: " + "NULL" if k == None else k.name
            else:
                print "Key: " + k.name + " Etag: " + k.etag
                counter += 1
        if counter != 2:
            self.fail("Expected 2 keys after copy operation, found only: " + len(keylist))
        try:
            ret_key = self.test_bucket.get_key(new_key)
        except:
            self.fail("Could not get object copy")
        if ret_key == None:
            self.fail("Could not get object copy")
            
        if self.test_bucket.get_key(testkey).get_contents_as_string() != ret_key.get_contents_as_string():
            self.fail("Contents of original key and copy don't match")
        else:
            print "Copy key contents match original!"
        
        #Test DELETE
        self.test_bucket.delete_key(testkey)
        ret_key = None
        try:
            ret_key = self.test_bucket.get_key(testkey)
            print "Erroneously got: " + ret_key.name
            self.fail("Should have thrown exception for getting a non-existent object")
        except S3ResponseError as e:
            if e.status == 404:
                print "Correctly could not get the deleted object"
            else:
                self.fail("Couldn't get deleted object, but got error other than 404: " + str(e.status))        
        
        
        print "Finishing basic ops test"
               
    def test_object_byte_offset_read(self):
        """Tests fetching specific byte offsets of the object"""
        print_header("Byte-range Offset GET Test")
        testkey = "rangetestkey"
        source_bytes = bytearray(self.test_object_data)
        
        #Put the object initially
        self.put_object(bucket=self.test_bucket, object_key=testkey, object_data=self.test_object_data)
        
        #Test range for first 100 bytes of object
        print "Trying start-range object get"
        try:
            data_str = Key(bucket=self.test_bucket,name=testkey).get_contents_as_string(headers={"Range":"bytes=0-99"})
        except:
            self.fail("Failed range object get first 100 bytes")
        
        startrangedata = bytearray(data_str)        
        print "Got: " + startrangedata
        print "Expected: " + str(source_bytes[:100])        
        for i in range(0,100):
            if startrangedata[i] != source_bytes[i]:
                print "Byte: " + startrangedata[i] + " differs!"
                self.fail("Start-range Ranged-get failed")
            
        print "Trying mid-object range"   
        try: 
            data_str = Key(bucket=self.test_bucket,name=testkey).get_contents_as_string(headers={"Range":"bytes=500-599"})
        except:
            self.fail("Failed range object get for middle 100 bytes")     
        midrangedata = bytearray(data_str)        
        for i in range(500,600):
            if midrangedata[i] != source_bytes[i]:
                print "Byte: " + midrangedata[i] + "differs!"
                self.fail("Mid-range Ranged-get failed")
        
        print "Trying end-range object get"
        #Test range for last 100 bytes of object
        try:
            data_str = Key(bucket=self.test_bucket,name=testkey).get_contents_as_string(headers={"Range":"bytes=800-899"})
        except:
            self.fail("Failed range object get for last 100 bytes")
            
        endrangedata = bytearray(data_str)
        print "Got: " + str(endrangedata)
        try:
            for i in range(800,900):
                if endrangedata[i] != source_bytes[i]:
                    print "Byte: " + endrangedata[i] + "differs!"
                    self.fail("End-range Ranged-get failed")
        except Exception as e:
            print "Exception! Received: " + e
        
        print "Range test complete"
        
    def test_object_post(self):
        """Test the POST method for putting objects, requires a pre-signed upload policy and url"""
        self.fail("Test not implemented")
        post_content_file = "test_data/post_test/post_test.html"
        
        post_key = Key("postkeytest")
        
        self.test_bucket.post(post_key)
        
                
    def test_object_large_objects(self):
        """Test operations on large objects (>1MB), but not so large that we must use the multi-part upload interface"""
        print_header("Testing large-ish objects over 1MB in size")
        
        test_data = ""
        large_obj_size_bytes = 25 * 1024 * 1024 #25MB
        #Create some test data        
        for i in range(0, large_obj_size_bytes):
            test_data += chr(random.randint(32,126))
        
        keyname = "largeobj"
        key = self.test_bucket.new_key(keyname)
        key.set_contents_as_string(test_data)
        
        ret_key = self.test_bucket.get_key(keyname)
        ret_data = ret_key.get_contents_as_string()
        
        if ret_data != test_data:
            self.fail("Fetched data and generated data don't match")
        else:
            print "Data matches!"
            
    def test_object_multipart(self):
        """Test the multipart upload interface"""
        self.fail("Feature not implemented")
        
    def test_object_versioning_enabled(self):
        """Tests object versioning for get/put/delete on a versioned bucket"""
        print_header("Testing bucket Versioning-Enabled")
        
        if not self.enable_versioning(self.test_bucket):
            self.fail("Could not properly enable versioning")
             
        #Create some keys
        keyname = "versionkey"
        
        #Multiple versions of the data
        v1data = self.test_object_data + "--version1"
        v2data = self.test_object_data + "--version2"
        v3data = self.test_object_data + "--version3"
        
        #Test sequence: put v1, get v1, put v2, put v3, get v3, delete v3, restore with v1 (copy), put v3 again, delete v2 explicitly
        self.put_object(bucket=self.test_bucket, object_key=keyname, object_data=v1data)
                
        #Get v1
        obj_v1 = self.test_bucket.get_key(keyname)
        assert(check_hashes(eTag=obj_v1.etag,data=v1data))
        
        print "Initial bucket state after object uploads without versioning:"
        self.print_key_info(keys=[obj_v1])
                
        #Put v2 (and get/head to confirm success)
        self.put_object(bucket=self.test_bucket, object_key=keyname,object_data=v2data)
        obj_v2 = self.test_bucket.get_key(keyname)
        assert(check_hashes(eTag=obj_v2.etag,data=v2data))
        self.print_key_info(keys=[obj_v1, obj_v2])
        
        #Put v3 (and get/head to confirm success)
        self.put_object(bucket=self.test_bucket, object_key=keyname,object_data=v3data)
        obj_v3 = self.test_bucket.get_key(keyname)
        assert(check_hashes(eTag=obj_v3.etag,data=v3data))
        self.print_key_info(keys=[obj_v1, obj_v2, obj_v3])
        
        #Get a specific version, v1
        v1_return = self.test_bucket.get_key(key_name=keyname,version_id=obj_v1.version_id)
        self.print_key_info(keys=[v1_return])
        
        #Delete current latest version (v3)
        self.test_bucket.delete_key(keyname)
        try:
            del_obj = self.test_bucket.get_key(keyname)
            self.fail("Should have gotten 404 not-found error, but got: " + del_obj.key + " instead")
        except S3ResponseError as e:
            print "Correctly got " + str(e.status) + " in response to GET of a deleted key"
        
        #Restore v1 using copy
        try:
            self.test_bucket.copy_key(new_key_name=obj_v1.key,src_bucket_name=self.test_bucket_name,src_key_name=keyname,src_version_id=obj_v1.version_id)
        except S3ResponseError as e:
            self.fail("Failed to restore key from previous version using copy got error: " + str(e.status))
            
        restored_obj = self.test_bucket.get_key(keyname)
        assert(check_hashes(eTag=restored_obj.etag,data=v1data))
        self.print_key_info(keys=[restored_obj])
        
        #Put v3 again
        self.put_object(bucket=self.test_bucket, object_key=keyname,object_data=v3data)
        assert(check_hashes(eTag=obj_v3.etag,data=v3data))
        self.print_key_info([self.test_bucket.get_key(keyname)])

        #Delete v2 explicitly
        self.test_bucket.delete_key(key_name=obj_v2.key,version_id=obj_v2.version_id)
        try:
            del_obj = None
            del_obj = self.test_bucket.get_key(keyname,version_id=obj_v2.version_id)
            self.fail("Should have gotten 404 not-found error, but got: " + del_obj.key + " instead")
        except S3ResponseError as e:
            print "Correctly got " + str(e.status) + " in response to GET of a deleted key"
                    
        #Show what's on top
        top_obj = self.test_bucket.get_key(keyname)
        self.print_key_info([top_obj])
        assert(check_hashes(eTag=top_obj.etag,data=v3data))        
        
        print "Finished the versioning enabled test. Success!!"
    
    def test_object_versionlisting(self):
        """Tests object version listing from a bucket"""        
        version_max = 3
        keyrange = 100
        print_header("Testing listing versions in a bucket and pagination using " + str(keyrange) + " keys with " + str(version_max) + " versions per key")
        
        if not self.enable_versioning(self.test_bucket):
            self.fail("Could not enable versioning properly. Failing")
        
        key = "testkey"
        keys = [ key + str(k) for k in range(0,keyrange)]        
        contents = [ ObjectTest.test_object_data + "--v" + str(v) for v in range(0,version_max)]        

        try:
            for keyname in keys:
                #Put 3 versions of each key
                for v in range(0,version_max):
                    self.test_bucket.new_key(keyname).set_contents_from_string(contents[v])
        except S3ResponseError as e:
            self.fail("Failed putting object versions for test: " + str(e.status))

        listing = self.test_bucket.get_all_versions()
        print "Bucket version listing is " + str(len(listing)) + " entries long"
        if keyrange * version_max >= 1000:
            assert(len(listing) == 999)
        else:
            assert(len(listing) == keyrange * version_max)
        
        prev_obj = None
        should_fail = None
        for obj in listing:
            if isinstance(obj,Key):
                print "Key: " + obj.name + " -- " + obj.version_id + "--" + obj.last_modified                
                if prev_obj != None:
                    if self.compare_versions(prev_obj, obj) > 0:
                        should_fail = obj
                prev_obj = obj 
            else:
                print "Not a key, skipping: " + str(obj)
            
        if should_fail != None:
            self.fail("Version listing not sorted correctly, offending key: " + should_fail.name + " version: " + should_fail.version_id + " date: " + should_fail.last_modified)
        
        #Now try with a known-smaller max-keys to ensure that the pagination works.j
        page_listing = self.test_bucket.get_all_versions(max_keys=(keyrange/2))
    
    def test_object_versioning_suspended(self):
        """Tests object versioning on a suspended bucket, a more complicated test than the Enabled test"""
        print_header("Testing bucket Versioning-Suspended")
    
        #Create some keys
        keyname1 = "versionkey1"
        keyname2 = "versionkey2"
        keyname3 = "versionkey3"
        keyname4 = "versionkey4"
        keyname5 = "versionkey5"
        v1data = self.test_object_data + "--version1"
        v2data = self.test_object_data + "--version2"
        v3data = self.test_object_data + "--version3"
        
        vstatus = self.test_bucket.get_versioning_status()
        if vstatus != None:
            self.fail("Versioning status should be null/Disabled")
        else:
            print "Bucket versioning is Disabled"
        
        self.put_object(bucket=self.test_bucket, object_key=keyname1, object_data=v1data)
        self.put_object(bucket=self.test_bucket, object_key=keyname2, object_data=v1data)
        self.put_object(bucket=self.test_bucket, object_key=keyname3, object_data=v1data)
        self.put_object(bucket=self.test_bucket, object_key=keyname4, object_data=v1data)
        self.put_object(bucket=self.test_bucket, object_key=keyname5, object_data=v1data)
                    
        key1 = self.test_bucket.get_key(keyname1)        
        key2 = self.test_bucket.get_key(keyname2)        
        key3 = self.test_bucket.get_key(keyname3)        
        key4 = self.test_bucket.get_key(keyname4)        
        key5 = self.test_bucket.get_key(keyname5)

        print "Initial bucket state after object uploads without versioning:"
        self.print_key_info(keys=[key1,key2,key3,key4,key5])
        
        
        
        #Enable versioning
        self.test_bucket.configure_versioning(True)
        if self.test_bucket.get_versioning_status():
            print "Versioning status correctly set to enabled"
        else:
            print "Versionign status not enabled, should be."            
        
        #Update a subset of the keys
        key1_etag2=self.put_object(bucket=self.test_bucket, object_key=keyname1,object_data=v2data)
        key2_etag2=self.put_object(bucket=self.test_bucket, object_key=keyname2,object_data=v2data)
        
        key3_etag2=self.put_object(bucket=self.test_bucket, object_key=keyname3,object_data=v2data)
        key3_etag3=self.put_object(bucket=self.test_bucket, object_key=keyname3,object_data=v3data)
        
        #Delete a key
        self.test_bucket.delete_key(keyname5)

        #Suspend versioning
        self.test_bucket.configure_versioning(False)
        
        #Get latest of each key
        key1=self.test_bucket.get_key(keyname1)
        key2=self.test_bucket.get_key(keyname2)
        key3=self.test_bucket.get_key(keyname3)
        key4=self.test_bucket.get_key(keyname4)
        key5=self.test_bucket.get_key(keyname5)
        
        #Delete a key
        
        #Add a key
        
        #Add same key again
        
        #Fetch each key
    
    def test_object_acl(self):
        """Tests object acl get/set and manipulation"""
        self.fail("Test not implemented")
        
        #TODO: test custom and canned acls that are both valid an invalid
        
    def test_object_torrent(self):
        """Tests object torrents"""
        self.fail("Feature not implemented yet")

    def tearDown(self):
        """Tearing down the env after a test"""
        print_header("Cleaning up the test bucket: " + self.test_bucket_name)
        clean_bucket(self.test_bucket)
        self.test_bucket = None

    def testName(self):
        pass
    
def suite():
    #tests = ['test_object_basic_ops','test_object_versioning_enabled', 'test_object_versioning_suspended', 'test_object_acl', 'test_object_torrent']  
    tests = ['test_object_basic_ops', 'test_object_versioning_enabled', 'test_object_versionlisting']
    return unittest.TestSuite(map(ObjectTest, tests))

if __name__ == "__main__":
    config = get_config()
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)  
    #unittest.main()
    
    