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
import re




class IAMops(Eutester):
    
    def create_account(self,account_name):
        '''Create an account with the given name'''
        self.debug("Creating account: " + account_name)
        params = {'AccountName': account_name}
        self.euare.get_response('CreateAccount', params)
    
    def delete_account(self,account_name,recursive=False):
        '''Delete an account with the given name'''
        self.debug("Deleting account: " + account_name)
        params = {
            'AccountName': account_name,
            'Recursive': recursive
        }
        self.euare.get_response('DeleteAccount', params)
    
        
    def get_all_accounts(self, account_id=None, account_name=None, search=False):
        '''
        Request all accounts, return account dicts that match given criteria
        Options:
            account_name - regex - to use for account_name
            account_id - regex - to use for 
            search - boolean - specify whether to use match or search when filtering the returned list
        '''
        if search:
            re_meth = re.search
        else:
            re_meth = re.match
        self.debug('Attempting to fetch all accounts matching- account_id:'+str(account_id)+' account_name:'+str(account_name))
        response = self.euare.get_response('ListAccounts',{}, list_marker='Accounts')
        retlist = []
        for account in response['list_accounts_response']['list_accounts_result']['accounts']:
            if account_name is not None and not re_meth( account_name, account['account_name']):
                continue
            if account_id is not None and not re_meth(account_id, account['account_id']):
                continue
            retlist.append(account)
        return retlist
             
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
    
    
        
    def get_users_from_account(self, path=None, user_name=None, user_id=None, delegate_account=None, search=False):
        '''
        Returns users that match given criteria. By default will return current account. 
        Options:
            path - regex - to match for path
            user_name - regex - to match for user_name
            user_id - regex - to match for user_id
            delegate_account - string - to use for delegating account lookup
            search - boolean - specify whether to use match or search when filtering the returned list
        '''
        self.debug('Attempting to fetch all users matching- user_id:'+str(user_id)+' user_name:'+str(user_name)+" acct_name:"+str(delegate_account))
        retlist = []
        params = {}
        if search:
            re_meth = re.search
        else:
            re_meth = re.match
        if delegate_account:
            params['DelegateAccount'] = delegate_account         
        response = self.euare.get_response('ListUsers', params, list_marker='Users')
        for user in response['list_users_response']['list_users_result']['users']:
            if path is not None and not re_meth(path, user['path']):
                continue
            if user_name is not None and not re_meth(user_name, user['user_name']):
                continue
            if user_id is not None and not re_meth(user_id, user['user_id']):
                continue
            retlist.append(user)
        return retlist
    
    def show_all_accounts(self,
                          account_name=None, 
                          account_id=None,  
                          search=False ):
        '''
        Debug Method to print an account list based on given filter criteria
        Options:
            account_name - regex - to use for account_name
            account_id - regex - to use for 
            search - boolean - specify whether to use match or search when filtering the returned list
        ''' 
        list = self.get_all_accounts(account_name=account_name, account_id=account_id, search=search)
        self.debug('-----------------------------------------------------------------------')
        self.debug(str('ACCOUNT_NAME:').ljust(25) + str('ACCT_ID:'))
        self.debug('-----------------------------------------------------------------------')
        for account in list:
            self.debug(str(account['account_name']).ljust(25)+str(account['account_id']))
            
    
    def show_all_groups(self,
                        account_name=None, 
                        account_id=None, 
                        path=None,
                        group_name=None, 
                        group_id=None, 
                        search=False):
        '''
        Debug Method to print a group list based on given filter criteria
        Options:
            path - regex - to match for path
            group_name - regex - to match for user_name
            group_id - regex - to match for user_id
            acount_name - regex - to use for account_name
            account_id - regex - to use for 
            search - boolean - specify whether to use match or search when filtering the returned list
        ''' 
        list = self.get_all_groups(account_name=account_name, account_id=account_id, path=path, group_name=group_name, group_id=group_id, search=search)
        self.debug('-----------------------------------------------------------------------')
        self.debug(str('ACCOUNT:').ljust(25) + str('GROUPNAME:').ljust(15) + str('GROUP_ID:').ljust(25)  )
        self.debug('-----------------------------------------------------------------------')
        for group in list:
            self.debug(str(group['account_name']).ljust(25)+str(group['group_name']).ljust(15)+str(group['group_id']))
            
       
    
    
    
    
    def show_all_users(self,
                       account_name=None, 
                       account_id=None, 
                       path=None,
                       user_name=None, 
                       user_id=None, 
                       search=False ):
        '''
        Debug Method to print a user list based on given filter criteria
        Options:
            path - regex - to match for path
            user_name - regex - to match for user_name
            user_id - regex - to match for user_id
            account_name - regex - to use for account_name
            account_id - regex - to use for 
            search - boolean - specify whether to use match or search when filtering the returned list
        ''' 
        list = self.get_all_users(account_name=account_name, account_id=account_id, path=path, user_name=user_name, user_id=user_id, search=search)
        self.debug('-----------------------------------------------------------------------')
        self.debug(str('ACCOUNT:').ljust(25) + str('USERNAME:').ljust(15) + str('USER_ID').ljust(25) + str('ACCT_ID') )
        self.debug('-----------------------------------------------------------------------')
        for user in list:
            self.debug(str(user['account_name']).ljust(25)+str(user['user_name']).ljust(15)+str(user['user_id']).ljust(25)+str(user['account_id']))
            
    def get_euare_username(self):
        return self.get_all_users(account_id=str(self.get_account_id()))[0]['user_name']
    
    def get_euare_accountname(self):
        return self.get_all_users(account_id=str(self.get_account_id()))[0]['account_name']
            
    def get_all_users(self, 
                      account_name=None, 
                      account_id=None, 
                      path=None,
                      user_name=None, 
                      user_id=None, 
                      search=False ):
        '''
        Queries all accounts matching given account criteria, returns all users found within these accounts which then match the given user criteria. 
        Account info is added to the user dicts
        Options:
            path - regex - to match for path
            user_name - regex - to match for user_name
            user_id - regex - to match for user_id
            account_name - regex - to use for account_name
            account_id - regex - to use for 
            search - boolean - specify whether to use match or search when filtering the returned list
        ''' 
        userlist=[]
        accounts = self.get_all_accounts(account_id=account_id, account_name=account_name, search=search)
        for account in accounts:
            users = self.get_users_from_account(path=path, user_name=user_name, user_id=user_id, delegate_account=account['account_name'], search=search)
            for user in users:
                user['account_name']=account['account_name']
                user['account_id']=account['account_id']
                userlist.append(user)
        return userlist
    
    def get_user_policy_names(self, user_name, policy_name=None,delegate_account=None, search=False):
        '''
        Returns list of policy names associated with a given user, and match given criteria. 
        Options:
            username - string - user to get policies for. 
            policy_name - regex - to match/filter returned policies
            delegate_account - string - used for user lookup
            search - boolean - specify whether to use match or search when filtering the returned list
        '''
        retlist = []
        params = {}
        if search:
            re_meth = re.search
        else:
            re_meth = re.match
        params = {'UserName': user_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        response = self.euare.get_response('ListUserPolicies',params, list_marker='PolicyNames')
        for name in response['list_user_policies_response']['list_user_policies_result']['policy_names']:
            if policy_name is not None and not re_meth(policy_name, name):
                continue
            retlist.append(name)
        return retlist
    
    
    def get_user_policies(self, user_name, policy_name=None,delegate_account=None, doc=None, search=False):
        '''
        Returns list of policy dicts associated with a given user, and match given criteria. 
        Options:
            username - string - user to get policies for. 
            policy_name - regex - to match/filter returned policies
            delegate_account - string - used for user lookup
            search - boolean - specify whether to use match or search when filtering the returned list
        '''
        retlist = []
        params = {}
        if search:
            re_meth = re.search
        else:
            re_meth = re.match
        names = self.get_user_policy_names(user_name, policy_name=policy_name, delegate_account=delegate_account, search=search)
        
        for p_name in names:
            params = {'UserName': user_name,
                      'PolicyName': p_name}
            if delegate_account:
                params['DelegateAccount'] = delegate_account
            policy = self.euare.get_response('GetUserPolicy', params, verb='POST')['get_user_policy_response']['get_user_policy_result']
            if doc is not None and not re_meth(doc, policy['policy_document']):
                continue
            retlist.append(policy)
        return retlist
        
    def show_user_policy_summary(self,user_name,policy_name=None,delegate_account=None, doc=None, search=False):
        '''
        Debug method to display policy summary applied to a given user
        '''
        policies = self.get_user_policies(user_name, policy_name=policy_name, delegate_account=delegate_account, doc=doc, search=search)
        for policy in policies:
            self.debug('-------------------------------------')
            self.debug("\tPOLICY NAME: "+str(policy['policy_name'])  )   
            self.debug('-------------------------------------')
            for line in str(policy['policy_document']).splitlines():
                self.debug(" "+line)
    
    def show_user_summary(self,user_name, delegate_account=None, account_id=None):
        '''
        Debug method for to display euare/iam info for a specific user.
        '''
        user_name = user_name
        if delegate_account is None:
            account_id=self.get_account_id()
            delegate_account= self.get_all_accounts(account_id=account_id)[0]['account_name']
        self.debug('Fetching user summary for: user_name:'+str(user_name)+" account:"+str(delegate_account)+" account_id:"+str(account_id))
        self.show_all_users(account_name=delegate_account, account_id=account_id, user_name=user_name)
        self.show_user_policy_summary(user_name, delegate_account=delegate_account)
        
        
    def show_euare_whoami(self):
        '''
        Debug method used to display the who am I info related to iam/euare.
        ''' 
        user= self.euare.get_user()['get_user_response']['get_user_result']['user']
        user_id = user['user_id']
        user_name = user['user_name']
        account_id = self.get_account_id()
        self.show_all_users(account_id=account_id, user_id=user_id)
        self.show_user_policy_summary(user_name)
        
    
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
        
    def get_all_groups(self, 
                      account_name=None, 
                      account_id=None, 
                      path=None,
                      group_name=None, 
                      group_id=None, 
                      search=False ):
        '''
        Queries all accounts matching given account criteria, returns all groups found within these accounts which then match the given user criteria. 
        Account info is added to the group dicts
        Options:
            path - regex - to match for path
            group_name - regex - to match for group_name
            group_id - regex - to match for group_id
            account_name - regex - to use for account_name
            account_id - regex - to use for 
            search - boolean - specify whether to use match or search when filtering the returned list
        ''' 
        grouplist=[]
        accounts = self.get_all_accounts(account_id=account_id, account_name=account_name, search=search)
        for account in accounts:
            groups = self.get_groups_from_account(path=path, group_name=group_name, group_id=group_id, delegate_account=account['account_name'], search=search)
            for group in groups:
                group['account_name']=account['account_name']
                group['account_id']=account['account_id']
                grouplist.append(group)
        return grouplist
        
    
    def get_groups_from_account(self, path=None, group_name=None, group_id=None, delegate_account=None, search=False):
        '''
        Returns groups that match given criteria. By default will return groups from current account. 
        Options:
            path - regex - to match for path
            group_name - regex - to match for group_name
            group_id - regex - to match for group_id
            delegate_account - string - to use for delegating account lookup
            search - boolean - specify whether to use match or search when filtering the returned list
        '''
        self.debug('Attempting to fetch all groups matching- group_id:'+str(group_id)+' group_name:'+str(group_name)+" acct_name:"+str(delegate_account))
        retlist = []
        params = {}
        if search:
            re_meth = re.search
        else:
            re_meth = re.match
        if delegate_account:
            params['DelegateAccount'] = delegate_account         
        response = self.euare.get_response('ListGroups', params, list_marker='Groups')
        for group in response['list_groups_response']['list_groups_result']['groups']:
            if path is not None and not re_meth(path, group['path']):
                continue
            if group_name is not None and not re_meth(user_name, group['group_name']):
                continue
            if group_id is not None and not re_meth(user_id, group['group_id']):
                continue
            retlist.append(group)
        return retlist
        
    
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
    
        
    