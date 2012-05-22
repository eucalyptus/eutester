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
class Eucaops_api(object):
    def create_bucket(self,bucket_name):
        raise NotImplementedError("Function not yet implemented")
    def upload_object_file(self, bucket_name, key_name, path_to_file):
        raise NotImplementedError("Function not yet implemented")
    def add_keypair(self,key_name=None ):
        raise NotImplementedError("Function not yet implemented")
    def add_group(self, group_name=None ):
        raise NotImplementedError("Function not yet implemented")
    def authorize_group(self,group_name="default", port=22, protocol="tcp", cidr_ip="0.0.0.0/0"):
        raise NotImplementedError("Function not yet implemented")
    def wait_for_instance(self,instance):
        raise NotImplementedError("Function not yet implemented")
    def create_volume(self, azone, size=1, snapshot=None):
        raise NotImplementedError("Function not yet implemented")
    def delete_keypair(self):
        raise NotImplementedError("Function not yet implemented")
    def get_keypair(self):
        raise NotImplementedError("Function not yet implemented") 
    def delete_group(self):
        raise NotImplementedError("Function not yet implemented") 
    def allocate_address(self):
        raise NotImplementedError("Function not yet implemented") 
    def release_address(self):
        raise NotImplementedError("Function not yet implemented") 
    def get_emi(self):
        raise NotImplementedError("Function not yet implemented")  
    def download_euca_image(self):
        raise NotImplementedError("Function not yet implemented")
    def upload_euca_image(self):
        raise NotImplementedError("Function not yet implemented") 
    def register_image( self, snap_id, rdn=None, description=None, image_location=None, windows=False, bdmdev=None, name=None, ramdisk=None, kernel=None ):
        raise NotImplementedError("Function not yet implemented")
    def deregister_image(self):
        raise NotImplementedError("Function not yet implemented") 
    def delete_bucket(self):
        raise NotImplementedError("Function not yet implemented")
    def run_instance(self, image, keypair=None, group=None, type=None, zone=None):
        raise NotImplementedError("Function not yet implemented")
    def terminate_instances(self):
        raise NotImplementedError("Function not yet implemented") 
    def reboot_instance(self):
        raise NotImplementedError("Function not yet implemented")  
    def delete_volume(self):
        raise NotImplementedError("Function not yet implemented") 
    def attach_volume(self):
        raise NotImplementedError("Function not yet implemented") 
    def detach_volume(self):
        raise NotImplementedError("Function not yet implemented") 
    def create_snapshot(self, volume_id, description="", waitOnProgress=0, poll_interval=10, timeout=0):
        raise NotImplementedError("Function not yet implemented") 
    def delete_snapshot(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_create_account(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_delete_account(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_create_user(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_delete_user(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_change_username(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_clean_accounts(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_add_userinfo(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_create_loginprofile(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_delete_loginprofile(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_add_userkey(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_deactivate_key(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_delete_key(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_create_cert(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_deactviate_cert(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_delete_cert(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_add_certfromfile(self):
        raise NotImplementedError("Function not yet implemented") 
    def get_currentaccount(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_create_group(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_group_add_user(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_attach_policy_user(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_detach_policy_user(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_detach_policy_account(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_attach_policy_group(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_attach_policy_account(self):
        raise NotImplementedError("Function not yet implemented") 
    def euare_parse_arn(self):
        raise NotImplementedError("Function not yet implemented") 
    def modify_property(self, property, value):
        raise NotImplementedError("Function not yet implemented") 
    def euare_modattr(self):
        raise NotImplementedError("Function not yet implemented") 
    def register_snapshot( self, snap_id, rdn="/dev/sda1", description="bfebs", windows=False, bdmdev=None, name=None, ramdisk=None, kernel=None, dot=True ):
        raise NotImplementedError("Function not yet implemented") 
    def get_volume(self, volume_id="vol-", status=None, attached_instance=None, attached_dev=None, snapid=None, zone=None, minsize=1, maxsize=None):
        raise NotImplementedError("Function not yet implemented")
    
        