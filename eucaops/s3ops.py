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
                self.debug( 'Bucket (%s) is owned by another user' % bucket_name )
                return None
            if not self.get_bucket_by_name(bucket.name):
                self.fail("Bucket could not be found after creation")
                return None
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
                self.debug( 'Bucket (%s) is owned by another user' % bucket_name )
                return None
            
        ### Check if the bucket still exists
        if self.get_bucket_by_name(bucket_name):
            self.fail("Bucket still exists after delete operation")
        
    
    def get_bucket_by_name(self, bucket_name):
        """
        Lookup a bucket by name, if it does not exist return false
        """
        bucket = self.s3.lookup(bucket_name)
        if bucket:
            return bucket
        else:
            return False
    
    def upload_object(self, bucket_name, key_name, path_to_file=None, contents=None):
        """
        Write the contents of a local file to walrus
        bucket_name   The name of the walrus Bucket.
        key_name      The name of the object containing the data in walrus.
        path_to_file  Fully qualified path to local file.
        """
        bucket = self.get_bucket_by_name(bucket_name)
        if bucket == None:
            self.fail("Could not find bucket " + bucket_name + " to upload file")
            return
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
            self.fail("Walrus bucket still exists after delete")
        except Exception, e:
            return