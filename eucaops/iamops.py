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

class IAMops(Eutester):
    
    def create_account(self,account_name):
        '''Create an account with the given name'''
        self.debug("Creating account: " + account_name)
        params = {'AccountName': account_name}
        self.euare.get_response('CreateAccount', params)
    
    def delete_account(self,account_name):
        '''Delete an account with the given name'''
        self.debug("Deleting account: " + account_name)
        params = {'AccountName': account_name}
        self.euare.get_response('DelegateAccount', params)
    
    def create_user(self, user_name,path="/", delegate_account=None):
        self.debug("Attempting to create user: " + user_name)
        params = {'UserName': user_name,
                  'Path': path }
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('CreateUser',params)
    
    def delete_user(self, user_name, delegate_account=None):
        self.debug("Deleting user " + user_name)
        params = {'UserName': user_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('DeleteUser', params)
    
    def attach_policy_user(self, user_name, policy_name, policy_json, delegate_account=None):
        self.debug("Attaching the following policy to " + user_name + ":" + policy_json)
        params = {'UserName': user_name,
                  'PolicyName': policy_name,
                  'PolicyDocument': policy_json}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('PutUserPolicy', params, verb='POST')
    
    def detach_policy_user(self, user_name, policy_name, delegate_account=None):
        self.debug("Detaching the following policy from " + user_name + ":" + policy_name)
        params = {'UserName': user_name,
                  'PolicyName': policy_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('DeleteUserPolicy', params, verb='POST')
    
    def create_group(self, group_name,path="/", delegate_account=None):
        self.debug("Attempting to create group: " + group_name)
        params = {'GroupName': group_name,
                  'Path': path}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('CreateGroup', params)
    
    def delete_group(self, group_name, delegate_account=None):
        self.debug("Deleting group " + group_name)
        params = {'GroupName': group_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('DeleteGroup', params)
    
    def add_user_to_group(self, group_name, user_name, delegate_account=None):
        self.debug("Adding user "  +  user_name + " to group " + group_name)
        params = {'GroupName': group_name,
                  'UserName': user_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('AddUserToGroup', params)
    
    def remove_user_from_group(self, group_name, user_name, delegate_account=None):
        self.debug("Removing user "  +  user_name + " to group " + group_name)
        params = {'GroupName': group_name,
                  'UserName': user_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('RemoveUserFromGroup', params)
    
    def attach_policy_group(self, group_name, policy_name, policy_json, delegate_account=None):
        self.debug("Attaching the following policy to " + group_name + ":" + policy_json)
        params = {'GroupName': group_name,
                  'PolicyName': policy_name,
                  'PolicyDocument': policy_json}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('PutGroupPolicy', params, verb='POST')
    
    def detach_policy_group(self, group_name, policy_name, delegate_account=None):
        self.debug("Detaching the following policy from " + group_name + ":" + policy_name)
        params = {'GroupName': group_name,
                  'PolicyName': policy_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('DeleteGroupPolicy', params, verb='POST')
    
    def create_access_key(self, user_name=None, delegate_account=None):
        self.debug("Creating access key for " + user_name )
        params = {'UserName': user_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        response = self.euare.get_response('CreateAccessKey', params)
        access_tuple = {}
        access_tuple['access_key_id'] = response['create_access_key_response']['create_access_key_result']['access_key']['access_key_id']
        access_tuple['secret_access_key'] = response['create_access_key_response']['create_access_key_result']['access_key']['secret_access_key']
        return access_tuple
    
        
    