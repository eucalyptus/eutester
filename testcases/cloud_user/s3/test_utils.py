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
Created on Apr 24, 2012

@author: zhill
'''

import sys, argparse, string, hashlib
import boto
from boto.s3.connection import OrdinaryCallingFormat
from boto.s3.connection import S3Connection
from boto.s3.bucket import Bucket
from boto.s3.key import Key
from boto.s3.deletemarker import DeleteMarker
from boto.s3.acl import ACL
from boto.s3.acl import Policy
from boto.s3.acl import Grant
import boto.s3.prefix
from boto.exception import S3ResponseError
from boto.exception import S3CreateError
from boto.s3.connection import Location

printheader='**********************'

def print_header(message):
    print "\n" + printheader + "--" + message + "--" + printheader + "\n"

def get_config():
    parser = argparse.ArgumentParser()        
    parser.add_argument('--endpoint')
    parser.add_argument('--port', type=int, default=8773)
    parser.add_argument('--path',default='/services/Walrus')
    parser.add_argument('--access_key')
    parser.add_argument('--secret_key')
    parser.add_argument('unittest_args', nargs='*')    
    testconfig = parser.parse_args()
    
    sys.argv[1:] = testconfig.unittest_args
    return testconfig

def check_hashes(eTag=None, data=None):
        hasher = hashlib.md5()
        hasher.update(data)
        data_hash = hasher.hexdigest()
        if data_hash != eTag:
            print "Hash/eTag mismatch: \nhash = " + data_hash + "\neTag= " + eTag
            return False
        return True
    
def clean_bucket(bucket):
    """Deletes the contents of the bucket specified and the bucket itself"""
    try :
        print "Getting bucket listing for " + bucket.name        
        print "Iterating throught the bucket"
        key_list = bucket.list()        
        print "Starting loop"
        for k in key_list:
            if isinstance(k, boto.s3.prefix.Prefix):
                print "Skipping prefix"
                continue
            print "Deleting key: " + k.name
            bucket.delete_key(k)
        bucket.delete()
    except S3ResponseError as e:
        print "Exception caught doing bucket cleanup."
        if e.status == 409:
            #Do version cleanup
            print "Cleaning up versioning artifacts"
            try:
                keys = bucket.get_all_versions()
                for k in keys:
                    if isinstance(k, Key):
                        print "Got version: " + k.name + "--" + k.version_id + "-- Delete marker? " + str(k.delete_marker)
                        print "Deleting key: " + k.name
                        bucket.delete_key(key_name=k.name,version_id=k.version_id)
                    elif isinstance(k, DeleteMarker):
                        print "Got marker: " + k.name + "--" + k.version_id + "--" + str(k.is_latest)
                        print "Deleting delete marker"
                        bucket.delete_key(key_name=k.name,version_id=k.version_id)
                print "Deleting bucket " + bucket.name
                bucket.delete()
            except Exception as e:
                print "Exception deleting versioning artifacts: " + e.message

s3_groups = {
             "all_users":"http://acs.amazonaws.com/groups/global/AllUsers",
             "authenticated_users":"http://acs.amazonaws.com/groups/global/AuthenticatedUsers",
             "log_delivery":"http://acs.amazonaws.com/groups/s3/LogDelivery"
             }
        

def get_canned_acl(owner_id=None,canned_acl=None,bucket_owner_id=None):
    if owner_id == None or canned_acl == None:
        return None
    
    owner_fc_grant = Grant(permission="FULL_CONTROL",user_id=owner_id)
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
        built_acl.add_grant(Grant(permission="READ",user_id=bucket_owner_id))        
    elif canned_acl == "bucket-owner-full-control":
        built_acl.add_grant(Grant(permission="FULL_CONTROL",user_id=bucket_owner_id))        
    else:
        #No canned-acl value found
        return None
    return built_acl  

