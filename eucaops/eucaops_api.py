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
    def deregister_image(self):
        raise NotImplementedError("Function not yet implemented") 
    def delete_bucket(self):
        raise NotImplementedError("Function not yet implemented")
    def run_instance(self, image, keypair=None, group=None, type=None, zone=None):
        raise NotImplementedError("Function not yet implemented")
    def terminate_instance(self):
        raise NotImplementedError("Function not yet implemented") 
    def reboot_instance(self):
        raise NotImplementedError("Function not yet implemented") 
    def create_volume(self):
        raise NotImplementedError("Function not yet implemented") 
    def delete_volume(self):
        raise NotImplementedError("Function not yet implemented") 
    def attach_volume(self):
        raise NotImplementedError("Function not yet implemented") 
    def detach_volume(self):
        raise NotImplementedError("Function not yet implemented") 
    def create_snapshot(self):
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
