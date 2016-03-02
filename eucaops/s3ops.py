# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2014, Eucalyptus Systems, Inc.
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


from prettytable import PrettyTable, ALL
from boto.s3.connection import OrdinaryCallingFormat
from boto.s3.key import Key
from boto.s3.acl import ACL, Grant
from boto.exception import S3ResponseError
from boto.s3.deletemarker import DeleteMarker
from boto.s3.bucket import Bucket, Key, DeleteMarker
import boto.s3
from eutester import Eutester
import hashlib
import os
import time




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
    s3_groups = {
             "all_users":"http://acs.amazonaws.com/groups/global/AllUsers",
             "authenticated_users":"http://acs.amazonaws.com/groups/global/AuthenticatedUsers",
             "log_delivery":"http://acs.amazonaws.com/groups/s3/LogDelivery"
             }

    def __init__(self, endpoint=None, credpath=None, aws_access_key_id=None, aws_secret_access_key = None, is_secure=False, path="/", port=80, boto_debug=0):
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.user_id = None
        self.account_id = None
        super(S3ops, self).__init__(credpath=credpath)
        self.setup_s3_connection(endpoint=endpoint, aws_access_key_id=self.aws_access_key_id ,aws_secret_access_key=self.aws_secret_access_key, is_secure=is_secure, path=path, port=port, boto_debug=boto_debug)
        self.test_resources = {}
        self.setup_s3_resource_trackers()

    def setup_s3_connection(self, endpoint=None, aws_access_key_id=None, aws_secret_access_key=None, is_secure=False, path="/", port=80, boto_debug=0):
        try:
            if not endpoint:
                endpoint = self.get_s3_ip()
            s3_connection_args = { 'aws_access_key_id' :aws_access_key_id,
                                   'aws_secret_access_key': aws_secret_access_key,
                                   'is_secure': is_secure,
                                   'host' : endpoint,
                                   'path'  : path,
                                   'port' : port,
                                   'debug':boto_debug,
                                   'calling_format':OrdinaryCallingFormat(),
                                   }
            self.debug("Attempting to create S3 connection to " + endpoint + ':' + str(port) + path)
            self.s3 = boto.connect_s3(**s3_connection_args)
        except Exception, e:
            raise Exception("Was unable to create S3 connection because of exception: " + str(e))

    def setup_s3_resource_trackers(self):
        """
        Setup keys in the test_resources hash in order to track artifacts created
        """
        self.test_resources["keys"] = []
        self.test_resources["buckets"] = []

    def get_s3_ip(self):
        """Parse the eucarc for the S3_URL"""
        s3_url = self.parse_eucarc("S3_URL")
        return s3_url.split("/")[2].split(":")[0]

    def get_s3_path(self):
        """Parse the eucarc for the S3_URL"""
        s3_url = self.parse_eucarc("S3_URL")
        s3_path = "/".join(s3_url.split("/")[3:])
        return s3_path

    def create_bucket(self, bucket_name):
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
            self.debug('Bucket (%s) already exists' % bucket_name)
        else:
                # Let's try to create the bucket.  This will fail if
                # the bucket has already been created by someone else.
            try:
                bucket = self.s3.create_bucket(bucket_name)
            except self.s3.provider.storage_create_error, e:
                raise S3opsException('Bucket (%s) is owned by another user' % bucket_name)

            def does_bucket_exist():
                try:
                    self.s3.get_bucket(bucket_name)
                    return True
                except S3ResponseError:
                    return False
            self.wait_for_result(does_bucket_exist, True, timeout=120, poll_wait=5)
            self.debug("Created bucket: " + bucket_name)
        self.test_resources["buckets"].append(bucket)
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

        def does_bucket_exist():
            try:
                self.s3.get_bucket(bucket_name)
                return True
            except S3ResponseError:
                return False
        self.wait_for_result(does_bucket_exist, False, timeout=120, poll_wait=5)
    
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
        if len(keys) < 1:
            self.fail("Unable to find any keys with prefix " + prefix + " in " + str(bucket) )
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
        
    def clear_bucket(self, bucket_name=None):
        """Deletes the contents of the bucket specified and the bucket itself
            THIS WILL DELETE EVERYTHING!
           bucket       bucket name to clear
        """
        try :
            bucket = self.s3.get_bucket(bucket_name=bucket_name)      
        except S3ResponseError as e:
            self.debug('No bucket' + bucket_name + ' found: ' + e.message)
            raise Exception('Not found')
        
        try:
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
            self.debug(  "Exception caught doing bucket cleanup." + e.message )
            #Todo: need to make this work with Walrus's non-S3-compliant error codes
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
            else:
                self.debug('Got ' + e.message + ' and status ' + str(e.status))
                    
    def clear_keys_with_prefix(self, bucket, prefix):
        try :
            listing = self.walrus.get_all_buckets()        
            for bucket in listing:
                if bucket.name.startswith(prefix):
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
                    
    
    def get_canned_acl(self, canned_acl=None, bucket_owner_id=None, bucket_owner_display_name=None):
        '''
        Returns an acl object that can be applied to a bucket or key. It is intended to be used to verify
        results that the service returns. To set a canned-acl you can simply set it on the bucket directly without
        this method.
        
        bucket_owner_id         Account id of the owner of the bucket. Required
        canned_acl       Canned acl to implement. Required. 
                         Options: ['private','public-read', 'public-read-write', 'authenticated-read',  'log-delivery-write', 'bucket-owner-full-control', 'bucket-owner-full-control']
        bucket_owner_display_name  Required. The account display name for the bucket owner, so that the correct permission can be generated fully
        '''
        if bucket_owner_id == None or canned_acl == None or bucket_owner_display_name == None :
            raise S3opsException( "No user_id or canned_acl passed to get_canned_acl()" )
        
        built_acl = ACL()
        built_acl.add_user_grant(permission='FULL_CONTROL',user_id=bucket_owner_id, display_name=bucket_owner_display_name)
        
        if canned_acl == "public-read":
            built_acl.add_grant(Grant(permission="READ",type='Group',uri=self.s3_groups["all_users"]))        
        elif canned_acl == "public-read-write":
            built_acl.add_grant(Grant(permission="READ",type='Group',uri=self.s3_groups["all_users"]))
            built_acl.add_grant(Grant(permission="WRITE",type='Group',uri=self.s3_groups["all_users"]))                
        elif canned_acl == "authenticated-read":
            built_acl.add_grant(Grant(permission="READ",type='Group',uri=self.s3_groups["authenticated_users"]))        
        elif canned_acl == "log-delivery-write":
            built_acl.add_grant(Grant(permission="WRITE",type='Group',uri=self.s3_groups["log_delivery"]))        
            built_acl.add_grant(Grant(permission="READ_ACP",type='Group',uri=self.s3_groups["log_delivery"]))        
        elif canned_acl == "bucket-owner-read":
            if bucket_owner_id is None:
                raise Exception("No bucket_owner_id passed when trying to create bucket-owner-read canned acl ")
            built_acl.add_grant(Grant(permission="READ",id=bucket_owner_id))
        elif canned_acl == "bucket-owner-full-control":
            if bucket_owner_id is None:
                raise Exception("No bucket_owner_id passed when trying to create bucket-owner-full-control canned acl ")
            built_acl.add_grant(Grant(permission="FULL_CONTROL",id=bucket_owner_id))
        return built_acl
    
    def check_acl_equivalence(self, acl1=None, acl2=None):
        '''
        Checks if acl1 = acl2 based on comparison of the set of grants irrespective of order.
        One limitation is that each grant's xml string deserialization must be the same to be
        considered equivalent. This has implications for the grant displayname in particular.
        For example, an ACL with an unknown account specified will not generally have a
        display-name associated with the account id, so the comparison may fail in that case even
        though the ids and permissions are identical.
        
        Returns None if there is an input problem such as one or more inputs are None
        
        acl1    An ACL object from boto.s3.acl
        acl2    An ACL object from boto.s3.acl
        '''
        if acl1 == None or acl2 == None:
            return None
        
        acl1grants = set()
        acl2grants = set()
        
        #calculate the symmetric-difference of the two sets of grants
        for val in acl1.grants:
            acl1grants.add(val.to_xml())
        
        for val in acl2.grants:
            acl2grants.add(val.to_xml())        
            
        return not len(acl1grants.symmetric_difference(acl2grants)) > 0

    def check_md5(self, eTag=None, data=None):
        hasher = hashlib.md5()
        hasher.update(data)
        data_hash = "\"" + hasher.hexdigest() + "\""
        if data_hash != eTag:
            raise Exception( "Hash/eTag mismatch: \nhash = " + data_hash + "\neTag= " + eTag)
            
    def show_bucket_summary(self, bucket, showkeys=True, format_size=True,
                            force_refresh=False, printme=True):
        if isinstance(bucket, str):
            bucket = self.get_bucket_by_name(bucket)
            if not bucket:
                raise ValueError('Bucket "{0}" not found for show_bucket'.format(bucket))
        if not isinstance(bucket, Bucket):
            raise ValueError('show_bucket expected type Bucket obj, got:{0}:{1}'
                             .format(bucket, type(bucket)))
        ret_table = None
        kb = 1000
        mb = 1000000
        gb = 1000000000
        DELETED = self.markup("<DELETE MRK>", [1,91])
        # Util method to format size of bucket and keys for tables (human readability, etc)...
        def get_size_string(bytes):
            if not format_size or bytes == DELETED:
                return str(bytes)
            if bytes < kb:
                ret_bytes = "{0:.2f}B ".format(bytes)
            elif bytes < mb:
                ret_bytes = "{0:.2f}KB".format(round(float(bytes/float(kb)), 2))
            elif bytes < gb:
                ret_bytes = "{0:.2f}MB".format(round(float(bytes/float(mb)), 2))
            else:
                ret_bytes = "{0:.2f}GB".format(round(float(bytes/float(gb)), 2))
            return  ret_bytes
        # Define bucket table, header names, sizes and alignments
        bk_name_col = ('BUCKET NAME:', 64)
        bk_ver_col = ('VERSIONED', 10)
        bk_keys_col = ('# OF KEYS', 10)
        bk_size_col = ('TOTAL SIZE', 16)
        # Define key table, header names, sizes and alignments
        key_name_col = ('KEY NAMES:', 60)
        key_size_col = ('SIZE/DELMRK', 12)
        key_ver_col = ('VERSION IDS', 33)
        key_mod_col = ('LAST MODIFIED', 25)
        # Create a bucket summary table using size and header alignments defined above.
        bucket_pt = PrettyTable([self.markup(bk_name_col[0], [1,4]), self.markup(bk_ver_col[0]),
                                 self.markup(bk_keys_col[0]), self.markup(bk_size_col[0])])
        bucket_pt.max_width[bk_name_col[0]] = bk_name_col[1]
        bucket_pt.max_width[bk_ver_col[0]] = bk_ver_col[1]
        bucket_pt.max_width[bk_keys_col[0]] = bk_keys_col[1]
        bucket_pt.max_width[bk_size_col[0]] = bk_size_col[1]
        if showkeys:
            bucket_pt.align[bk_name_col[0]] = 'c'
        else:
            bucket_pt.align[bk_name_col[0]] = 'l'
        bucket_pt.align[bk_size_col[0]] = 'r'
        bucket_pt.align[bk_keys_col[0]] = 'l'
        bucket_pt.align[bk_ver_col[0]] = 'l'
        bucket_pt.right_padding_width = 0
        bucket_pt.left_padding_width = 1

        # Now calc bucket keys information...
        if showkeys:
            # If showkeys is True, create a subtable to show key summary information using
            # the size and header alignments defined above...
            key_pt = PrettyTable([self.markup(key_name_col[0], [1,4]), self.markup(key_size_col[0]),
                                  self.markup(key_ver_col[0]), self.markup(key_mod_col[0])])
            key_pt.max_width[key_ver_col[0]] = key_ver_col[1]
            key_pt.max_width[key_name_col[0]] = key_name_col[1]
            key_pt.max_width[key_size_col[0]] = key_size_col[1]
            key_pt.max_width[key_mod_col[0]] = key_mod_col[1]
            key_pt.hrules = ALL
            key_pt.align[key_ver_col[0]] = 'l'
            key_pt.align[key_name_col[0]] = 'l'
            key_pt.align[key_size_col[0]] = 'r'
            key_pt.align[key_mod_col[0]] = 'c'
            key_pt.right_padding_width = 0
            key_pt.left_padding_width = 1
        else:
            key_pt = None
        total_size = 0
        total_keys = 0
        last_key = None
        last_key_sizes = []
        last_key_versions = []
        last_key_mods = []
        last_key_del_marker = None
        last_written = None
        # Util method to add key info into formatted table rows/columns
        def add_last_key_info_to_table():
            if last_key_del_marker:
                # If theres a delete marker, put the delete marker at the top of the
                # versions list and highlight it red...
                last_key_versions.insert(0,self.markup(last_key_del_marker.version_id,
                                                       [1,91]))
                last_key_sizes.insert(0, DELETED)
                last_key_mods.insert(0, self.markup(last_key_del_marker.last_modified,
                                                    [1,91]))
                keyname = str(self.markup('KEY:' + last_key.name, [1,91])).\
                    ljust(key_name_col[1])
            else:
                keyname = str(self.markup('KEY:' + last_key.name)).ljust(key_name_col[1])

            # Create a string that will get wrapped for the vesions column
            ver_string = ("\n".join('{0}'.format(x).ljust(key_ver_col[1]) for x in
                              last_key_versions))
            # Create a string that will get wrapped for the sizes of each version
            size_string = ("\n".join('{0}'.format(get_size_string(x)).rjust(key_size_col[1])
                                 for x in last_key_sizes))
            # Create string that will get wrapped for the last modified times of each ver
            mod_string = ("\n".join('{0}'.format(x).center(key_mod_col[1])
                                 for x in last_key_mods))
            # Add the key to the key table...
            key_pt.add_row([
                keyname,
                str(size_string).ljust(key_size_col[1]),
                ver_string,
                mod_string])
        # Iterate through keys to gather total size, total number of keys, and create a keys
        # subtable if show_keys was true...
        for key in bucket.list_versions():
            if isinstance(key, DeleteMarker):
                current_ver = None
                current_size = None
                current_name = key.name
                current_del_marker = key
            else:
                current_ver = key.version_id
                current_size = key.size
                current_name = key.name
                current_del_marker = None
                total_size += current_size
                total_keys += 1

            if last_key and last_key.name != current_name:
                # This is a new key...
                if key_pt:
                    # add the key information collected prior to this key to the table...
                    add_last_key_info_to_table()
                last_written = last_key
                last_key = key
                if current_size is None:
                    last_key_sizes = []
                else:
                    last_key_sizes = [current_size]
                if current_ver:
                    last_key_versions = [current_ver]
                else:
                    last_key_versions = []
                if not isinstance(key, DeleteMarker):
                    last_key_mods = [key.last_modified]
                else:
                    last_key_mods = []
                last_key_del_marker = current_del_marker
            else:
                if current_size is not None:
                    last_key_sizes.append(current_size)
                if current_ver:
                    last_key_versions.append(current_ver)
                last_key = key
                last_key_del_marker = last_key_del_marker or current_del_marker
                if not isinstance(key, DeleteMarker):
                    last_key_mods.append(key.last_modified)
        if last_key != last_written:
            if key_pt:
                # add the key information collected prior to this key to the table...
                add_last_key_info_to_table()
        # Populate the bucket summary table with calc'd data...
        version_enabled = bool('Enabled' == bucket.get_versioning_status().get('Versioning'))
        if showkeys:
            bucket_name = str(self.markup(bucket.name, [1,4,94])).center(bk_name_col[1])
        else:
            bucket_name = str(self.markup(bucket.name, [1,4,94])).ljust(bk_name_col[1])
        bucket_pt.add_row([bucket_name,
                           str(version_enabled).ljust(bk_ver_col[1]),
                           str(total_keys).ljust(bk_keys_col[1]),
                           str(get_size_string(total_size)).rjust(bk_size_col[1])])
        if not showkeys:
            ret_table = bucket_pt
        else:
            main_pt = PrettyTable(["BUCKET SUMMARY:"])
            main_pt.header = False
            main_pt.align = 'l'
            main_pt.add_row([str(bucket_pt)])
            main_pt.add_row([str(key_pt)])
            ret_table = main_pt
        if printme:
            self.debug("\n{0}\n".format(ret_table))
        else:
            return ret_table



    def show_buckets(self, buckets=None, format_size=True, printme=True):
        if not buckets:
            buckets = self.s3.get_all_buckets()
        elif isinstance(buckets, str) or isinstance(buckets, unicode):
            buckets = self.get_bucket_by_name(str(buckets))
        if isinstance(buckets, Bucket):
            buckets = [buckets]
        if not isinstance(buckets, list):
            raise ValueError('Error with type for "buckets", expected list of type boto.Bucket, '
                             'got:"{0}:{1}"'.format(buckets, type(buckets)))
        first = buckets.pop(0)
        main_table = self.show_bucket_summary(bucket=first, showkeys=False,
                                              format_size=format_size, printme=False)
        main_table.hrules = ALL
        main_table.vrules = ALL
        for field in main_table.field_names:
            main_table.align[field] = 'l'
        for bucket in buckets:
            bucket_table = self.show_bucket_summary(bucket=bucket, showkeys=False,
                                                    format_size=format_size, printme=False)
            if hasattr(bucket_table, '_rows') and bucket_table._rows:
                main_table.add_row(bucket_table._rows[0])
        if printme:
            self.debug("\n{0}\n".format(str(main_table)))
        else:
            return main_table
