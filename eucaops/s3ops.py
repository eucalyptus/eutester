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
# Author: vic.iglesias@eucalyptus.com

from eutester import Eutester

import os
import hashlib


from boto.s3.connection import OrdinaryCallingFormat
from boto.s3.connection import S3Connection
from boto.s3.bucket import Bucket
from boto.s3.key import Key
from boto.s3.acl import ACL, Policy, Grant
from boto.exception import S3ResponseError
from boto.exception import S3CreateError
from boto.s3.connection import Location
import boto.s3

class S3opsException(Exception):
    """Exception raised for errors that occur when running S3 operations.

    Attributes:
        msg  -- explanation of the error
    """
    def __init__(self, msg):
        self.msg = msg
    
    def __str__(self):
        print self.msg

class S3ops(Eutester):
    def __init__(self, config_file=None, password=None, keypath=None, credpath=None, aws_access_key_id=None, aws_secret_access_key = None,account="eucalyptus",user="admin", username="root",region=None, clc_ip=None, boto_debug=0):
        super(S3ops, self).__init__(config_file=config_file,password=password, keypath=keypath, credpath=credpath, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key,account=account, user=user, region=region,clc_ip=clc_ip, boto_debug=boto_debug)
        self.test_resources = {}
        self.setup_s3_resource_trackers()
        
    def setup_s3_resource_trackers(self):
        """
        Setup keys in the test_resources hash in order to track artifacts created
        """
        self.test_resources["keys"] = []
        self.test_resources["buckets"] = []
        
    def create_bucket(self,bucket_name):
        """
        Create a bucket.  If the bucket already exists and you have
        access to it, no error will be returned by AWS.
        Note that bucket names are global to S3
        so you need to choose a unique name.
        """
        # First let's see if we already have a bucket of this name.
        # The lookup method will return a Bucket object if the
        # bucket exists and we have access to it or None.
        bucket = self.get_bucket_by_name(bucket_name)
        if bucket:
            self.debug( 'Bucket (%s) already exists' % bucket_name )
        else:
                # Let's try to create the bucket.  This will fail if
                # the bucket has already been created by someone else.
            try:
                bucket = self.s3.create_bucket(bucket_name)
            except self.s3.provider.storage_create_error, e:
                raise S3opsException( 'Bucket (%s) is owned by another user' % bucket_name )
            if not self.get_bucket_by_name(bucket.name):
                raise S3opsException("Bucket could not be found after creation")
        self.test_resources["buckets"].append(bucket)
        self.debug("Created bucket: " + bucket_name)
        return bucket
    
    def delete_bucket(self, bucket):
        """
        Delete a bucket.
        bucket_name  The name of the Walrus Bucket
        """
        # First let's see if we already have a bucket of this name.
        # The lookup method will return a Bucket object if the
        # bucket exists and we have access to it or None.
        bucket_name = bucket.name
        try:
            bucket.delete()
        except self.s3.provider.storage_create_error, e:
                raise S3opsException( 'Bucket (%s) is owned by another user' % bucket_name )
        ### Check if the bucket still exists
        if self.get_bucket_by_name(bucket_name):
            raise S3opsException('Bucket (%s) still exists after delete operation'  % bucket_name )
    
    def get_bucket_by_name(self, bucket_name):
        """
        Lookup a bucket by name, if it does not exist raise an exception
        """
        bucket = self.s3.lookup(bucket_name)
        if bucket:
            return bucket
        else:
            return None
    
    def upload_object(self, bucket_name, key_name, path_to_file=None, contents=None):
        """
        Write the contents of a local file to walrus
        bucket_name   The name of the walrus Bucket.
        key_name      The name of the object containing the data in walrus.
        path_to_file  Fully qualified path to local file.
        """
        bucket = self.get_bucket_by_name(bucket_name)
        if bucket == None:
            raise S3opsException("Could not find bucket " + bucket_name + " to upload file")
        # Get a new, blank Key object from the bucket.  This Key object only
        # exists locally until we actually store data in it.
        key = bucket.new_key(key_name)
        if key == None:
            self.fail( "Unable to create key " + key_name  )
        if path_to_file is None:
            if contents is None:
                contents = os.urandom(1024)
            key.set_contents_from_string(contents)
        else:
            key.set_contents_from_filename(path_to_file)
        self.debug("Uploaded key: " + str(key_name) + " to bucket:" + str(bucket_name))    
        self.test_resources["keys"].append(key)
        return key
    
    def get_objects_by_prefix(self, bucket_name, prefix):
        """
        Get keys in the specified bucket that match the prefix if no prefix is passed all objects are returned
        as a result set.
        If only 1 key matches it will be returned as a Key object. 
        """
        bucket = self.get_bucket_by_name(bucket_name)
        keys = bucket.get_all_keys(prefix=prefix)
        if len(keys) <= 1:
            self.fail("Unable to find any keys with prefix " + prefix + " in " + bucket )
        if len(keys) == 2:
            return keys[0]
        return keys
        
    def delete_object(self, object):
        bucket = object.bucket
        name = object.name
        object.delete()
        try:
            self.s3.get_bucket(bucket).get_key(name)
            raise S3opsException("Walrus object " + name + " in bucket "  +  bucket.name  + " still exists after delete")
        except Exception, e:
            return
        
    def clear_bucket(bucket):
        """Deletes the contents of the bucket specified and the bucket itself
           bucket       boto.bucket to delete recursively
        """
        try :
            self.debug( "Getting bucket listing for " + bucket.name )     
            self.debug(  "Iterating throught the bucket" )
            key_list = bucket.list()        
            self.debug(  "Starting loop" )
            for k in key_list:
                if isinstance(k, boto.s3.prefix.Prefix):
                    self.debug(  "Skipping prefix" )
                    continue
                self.debug(  "Deleting key: " + k.name )
                bucket.delete_key(k)
            bucket.delete()
        except S3ResponseError as e:
            self.debug(  "Exception caught doing bucket cleanup." )
            if e.status == 409:
                #Do version cleanup
                self.debug(  "Cleaning up versioning artifacts" )
                try:
                    keys = bucket.get_all_versions()
                    for k in keys:
                        if isinstance(k, Key):
                            self.debug(  "Got version: " + k.name + "--" + k.version_id + "-- Delete marker? " + str(k.delete_marker) )
                            self.debug(  "Deleting key: " + k.name )
                            bucket.delete_key(key_name=k.name,version_id=k.version_id)
                        elif isinstance(k, DeleteMarker):
                            self.debug(  "Got marker: " + k.name + "--" + k.version_id + "--" + str(k.is_latest) )
                            self.debug(  "Deleting delete marker" )
                            bucket.delete_key(key_name=k.name,version_id=k.version_id)
                    self.debug(  "Deleting bucket " + bucket.name )
                    bucket.delete()
                except Exception as e:
                    self.debug(  "Exception deleting versioning artifacts: " + e.message )
                    
    def clear_keys_with_prefix(self, bucket, prefix):
        try :
            listing = BucketTest.walrus.get_all_buckets()        
            for bucket in listing:
                if bucket.name.startswith(BucketTest.bucket_prefix):
                    self.debug( "Getting bucket listing for " + bucket.name)
                    key_list = bucket.list()
                    for k in key_list:
                        if isinstance(k, boto.s3.prefix.Prefix):
                            self.debug( "Skipping prefix" )
                            continue
                        self.debug( "Deleting key: " + k.name )
                        bucket.delete_key(k)
                    bucket.delete()
                else:
                    self.debug( "skipping bucket: " + bucket.name )
        except S3ResponseError as e:
            raise S3opsException( "Exception caught doing bucket cleanup." )
                    
    
    def get_canned_acl(owner_id=None,canned_acl=None,bucket_owner_id=None):
        '''
        Returns an acl object that can be applied to a bucket or key
        owner_id         Account id of the owner of the bucket. Required
        canned_acl       Canned acl to implement. Required. 
                         Options: ['public-read', 'public-read-write', 'authenticated-read',  'log-delivery-write', 'bucket-owner-full-control', 'bucket-owner-full-control']
        bucket_owner_id  Required for bucket-owner-full-control and bucket-owner-full-control acls to be created
        '''
        if owner_id == None or canned_acl == None:
            raise S3opsException( "No owner_id or canned_acl passed to get_canned_acl()" )
        
        owner_fc_grant = Grant(permission="FULL_CONTROL", id=owner_id)
        built_acl = ACL()
        built_acl.add_grant(owner_fc_grant)
            
        if canned_acl == "public-read":
            built_acl.add_grant(Grant(permission="READ",uri=s3_groups["all_users"]))        
        elif canned_acl == "public-read-write":
            built_acl.add_grant(Grant(permission="READ",uri=s3_groups["all_users"]))
            built_acl.add_grant(Grant(permission="WRITE",uri=s3_groups["all_users"]))                
        elif canned_acl == "authenticated-read":
            built_acl.add_grant(Grant(permission="READ",uri=s3_groups["authenticated_users"]))        
        elif canned_acl == "log-delivery-write":
            built_acl.add_grant(Grant(permission="WRITE",uri=s3_groups["log_delivery"]))        
        elif canned_acl == "bucket-owner-read":
            if bucket_owner_id is None:
                raise Exception("No bucket_owner_id passed when trying to create bucket-owner-read canned acl ")
            built_acl.add_grant(Grant(permission="READ",user_id=bucket_owner_id))        
        elif canned_acl == "bucket-owner-full-control":
            if bucket_owner_id is None:
                raise Exception("No bucket_owner_id passed when trying to create bucket-owner-full-control canned acl ")
            built_acl.add_grant(Grant(permission="FULL_CONTROL",user_id=bucket_owner_id))        
        return built_acl

    def check_md5(eTag=None, data=None):
        hasher = hashlib.md5()
        hasher.update(data)
        data_hash = hasher.hexdigest()
        if data_hash != eTag:
            raise Exception( "Hash/eTag mismatch: \nhash = " + data_hash + "\neTag= " + eTag )
            
                