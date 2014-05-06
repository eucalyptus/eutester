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
from eutester import Eutester
import re
import boto

class IAMops(Eutester):

    def __init__(self,credpath=None, endpoint="iam.amazonaws.com", aws_access_key_id=None, aws_secret_access_key=None,
                 is_secure=True, port=443, path='/', boto_debug=0 ):
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.user_id = None
        self.account_id = None
        super(IAMops, self).__init__(credpath=credpath)
        self.setup_iam_connection(endpoint=endpoint, aws_access_key_id=self.aws_access_key_id ,
                                  aws_secret_access_key=self.aws_secret_access_key, is_secure=is_secure, port=port,
                                  path=path, boto_debug=boto_debug )

    def setup_iam_connection(self, endpoint="iam.amazonaws.com", aws_access_key_id=None,aws_secret_access_key=None,
                             is_secure=True, port=443, path='/', boto_debug=0 ):
        try:
            euare_connection_args = { 'aws_access_key_id' : aws_access_key_id,
                                      'aws_secret_access_key': aws_secret_access_key,
                                      'is_secure': is_secure,
                                      'debug':boto_debug,
                                      'port' : port,
                                      'path' : path,
                                      'host' : endpoint}
            self.debug("Attempting to create IAM connection to " + endpoint + ':' + str(port) + path)
            self.euare = boto.connect_iam(**euare_connection_args)
        except Exception, e:
            self.critical("Was unable to create IAM connection because of exception: " + str(e))

    def get_iam_ip(self):
        """Parse the eucarc for the EUARE_URL"""
        iam_url = self.parse_eucarc("EUARE_URL")
        return iam_url.split("/")[2].split(":")[0]

    def get_iam_path(self):
        """Parse the eucarc for the EUARE_URL"""
        iam_url = self.parse_eucarc("EUARE_URL")
        iam_path = "/".join(iam_url.split("/")[3:])
        return iam_path

    def create_account(self,account_name):
        """
        Create an account with the given name

        :param account_name: str name of account to create
        """
        self.debug("Creating account: " + account_name)
        params = {'AccountName': account_name}
        self.euare.get_response('CreateAccount', params)
    
    def delete_account(self,account_name,recursive=False):
        """
        Delete an account with the given name

        :param account_name: str name of account to delete
        :param recursive:
        """
        self.debug("Deleting account: " + account_name)
        params = {
            'AccountName': account_name,
            'Recursive': recursive
        }
        self.euare.get_response('DeleteAccount', params)

    def get_all_accounts(self, account_id=None, account_name=None, search=False):
        """
        Request all accounts, return account dicts that match given criteria

        :param account_id: regex string - to use for account_name
        :param account_name: regex - to use for account ID
        :param search: boolean - specify whether to use match or search when filtering the returned list
        :return: list of account names
        """
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
        """
        Create a user

        :param user_name: str name of user
        :param path: str user path
        :param delegate_account: str can be used by Cloud admin in Eucalyptus to choose an account to operate on
        """
        self.debug("Attempting to create user: " + user_name)
        params = {'UserName': user_name,
                  'Path': path }
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('CreateUser',params)
    
    def delete_user(self, user_name, delegate_account=None):
        """
        Delete a user

        :param user_name: str name of user
        :param delegate_account: str can be used by Cloud admin in Eucalyptus to choose an account to operate on
        """
        self.debug("Deleting user " + user_name)
        params = {'UserName': user_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('DeleteUser', params)

    def get_users_from_account(self, path=None, user_name=None, user_id=None, delegate_account=None, search=False):
        """
        Returns users that match given criteria. By default will return current account.

        :param path: regex - to match for path
        :param user_name: str name of user
        :param user_id: regex - to match for user_id
        :param delegate_account: str can be used by Cloud admin in Eucalyptus to choose an account to operate on
        :param search: use regex search (any occurrence) rather than match (exact same strings must occur)
        :return:
        """
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

    def show_all_accounts(self, account_name=None, account_id=None, search=False ):
        """
        Debug Method to print an account list based on given filter criteria

        :param account_name: regex - to use for account_name
        :param account_id: regex - to use for account_id
        :param search: boolean - specify whether to use match or search when filtering the returned list
        """
        list = self.get_all_accounts(account_name=account_name, account_id=account_id, search=search)
        self.debug('-----------------------------------------------------------------------')
        self.debug(str('ACCOUNT_NAME:').ljust(25) + "|" + str('ACCT_ID:'))
        self.debug('-----------------------------------------------------------------------')
        for account in list:
            self.debug(str(account['account_name']).ljust(25) + "|" +str(account['account_id']))
            self.debug('-----------------------------------------------------------------------')

    def show_all_groups(self, account_name=None,  account_id=None,  path=None, group_name=None,  group_id=None,  search=False):
        """
        Print all groups in an account

        :param account_name: regex - to use for account_name
        :param account_id: regex - to use for
        :param path: regex - to match for path
        :param group_name: regex - to match for user_name
        :param group_id: regex - to match for user_id
        :param search:  boolean - specify whether to use match or search when filtering the returned list
        """
        list = self.get_all_groups(account_name=account_name, account_id=account_id, path=path, group_name=group_name, group_id=group_id, search=search)
        self.debug('-----------------------------------------------------------------------')
        self.debug(str('ACCOUNT:').ljust(25) + "|" + str('GROUPNAME:').ljust(15) + "|" + str('GROUP_ID:').ljust(25)  )
        self.debug('-----------------------------------------------------------------------')
        for group in list:
            self.debug(str(group['account_name']).ljust(25) + "|" + str(group['group_name']).ljust(15) + "|" + str(group['group_id']))
            self.debug('-----------------------------------------------------------------------')

    def show_all_users(self, account_name=None, account_id=None,  path=None, user_name=None,  user_id=None, search=False ):
        """
        Debug Method to print a user list based on given filter criteria

        :param account_name: regex - to use for account_name
        :param account_id: regex - to use for
        :param path: regex - to match for path
        :param user_name: regex - to match for user_name
        :param user_id: regex - to match for user_id
        :param search: boolean - specify whether to use match or search when filtering the returned list
        """
        list = self.get_all_users(account_name=account_name, account_id=account_id, path=path, user_name=user_name, user_id=user_id, search=search)
        self.debug('-----------------------------------------------------------------------')
        self.debug(str('ACCOUNT:').ljust(25) + "|" + str('USERNAME:').ljust(15) + "|" + str('USER_ID').ljust(25) + "|" + str('ACCT_ID') )
        self.debug('-----------------------------------------------------------------------')
        for user in list:
            self.debug(str(user['account_name']).ljust(25) + "|" + str(user['user_name']).ljust(15) + "|" + str(user['user_id']).ljust(25) + "|" + str(user['account_id']))
            self.debug('-----------------------------------------------------------------------')
    def get_euare_username(self):
        """
        Get all users in the current users account
        """
        return self.get_all_users(account_id=str(self.get_account_id()))[0]['user_name']
    
    def get_euare_accountname(self):
        """
        Get account name of current user
        """
        return self.get_all_users(account_id=str(self.get_account_id()))[0]['account_name']

    def get_all_users(self,  account_name=None,  account_id=None,  path=None, user_name=None,  user_id=None,  search=False ):
        """
        Queries all accounts matching given account criteria, returns all users found within these accounts which then match the given user criteria.
        Account info is added to the user dicts

        :param account_name: regex - to use for account name
        :param account_id: regex - to use for account id
        :param path: regex - to match for path
        :param user_name: regex - to match for user name
        :param user_id: regex - to match for user id
        :param search: boolean - specify whether to use match or search when filtering the returned list
        :return: List of users with account name tuples
        """
        userlist=[]
        accounts = self.get_all_accounts(account_id=account_id, account_name=account_name, search=search)
        for account in accounts:
            if account['account_id'] == self.account_id:
                users =self.get_users_from_account()
            else:
                users = self.get_users_from_account(path=path, user_name=user_name, user_id=user_id, delegate_account=account['account_name'], search=search)
            for user in users:
                user['account_name']=account['account_name']
                user['account_id']=account['account_id']
                userlist.append(user)
        return userlist

    def get_user_policy_names(self, user_name, policy_name=None,delegate_account=None, search=False):
        """
        Returns list of policy names associated with a given user, and match given criteria.

        :param user_name: string - user to get policies for.
        :param policy_name: regex - to match/filter returned policies
        :param delegate_account: string - used for user lookup
        :param search: specify whether to use match or search when filtering the returned list
        :return: list of policy names
        """
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
        """
        Returns list of policy dicts associated with a given user, and match given criteria.

        :param user_name: string - user to get policies for.
        :param policy_name: regex - to match/filter returned policies
        :param delegate_account: string - used for user lookup
        :param doc: policy document to use as a filter
        :param search: boolean - specify whether to use match or search when filtering the returned list
        :return:
        """
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
        """
        Debug method to display policy summary applied to a given user

        :param user_name: string - user to get policies for.
        :param policy_name: regex - to match/filter returned policies
        :param delegate_account: string - used for user lookup
        :param doc: policy document to use as a filter
        :param search: boolean - specify whether to use match or search when filtering the returned list
        """
        policies = self.get_user_policies(user_name, policy_name=policy_name, delegate_account=delegate_account, doc=doc, search=search)
        for policy in policies:
            self.debug('-------------------------------------')
            self.debug("\tPOLICY NAME: "+str(policy['policy_name']) +", USER_NAME: " +str(user_name))
            self.debug('-------------------------------------')
            for line in str(policy['policy_document']).splitlines():
                self.debug("\t"+line)
    
    def show_user_summary(self,user_name, delegate_account=None, account_id=None):
        """
        Debug method for to display euare/iam info for a specific user.

        :param user_name: string - user to get policies for.
        :param delegate_account: string - used for user lookup
        :param account_id: regex - to use for account id
        """
        user_name = user_name
        if delegate_account is None:
            account_id=self.get_account_id()
            delegate_account= self.get_all_accounts(account_id=account_id)[0]['account_name']
        self.debug('Fetching user summary for: user_name:'+str(user_name)+" account:"+str(delegate_account)+" account_id:"+str(account_id))
        self.show_all_users(account_name=delegate_account, account_id=account_id, user_name=user_name)
        self.show_user_policy_summary(user_name, delegate_account=delegate_account)
        
        
    def show_euare_whoami(self):
        """
        Debug method used to display the who am I info related to iam/euare.
        """
        user= self.euare.get_user()['get_user_response']['get_user_result']['user']
        user_id = user['user_id']
        user_name = user['user_name']
        account_id = self.get_account_id()
        self.show_all_users(account_id=account_id, user_id=user_id)
        self.show_user_policy_summary(user_name)
        
    
    def attach_policy_user(self, user_name, policy_name, policy_json, delegate_account=None):
        """
        Attach a policy string to a user

        :param user_name: string - user to apply policy to
        :param policy_name: Name to upload policy as
        :param policy_json: Policy text
        :param delegate_account: str can be used by Cloud admin in Eucalyptus to choose an account to operate on
        """
        self.debug("Attaching the following policy to " + user_name + ":" + policy_json)
        params = {'UserName': user_name,
                  'PolicyName': policy_name,
                  'PolicyDocument': policy_json}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('PutUserPolicy', params, verb='POST')
    
    def detach_policy_user(self, user_name, policy_name, delegate_account=None):
        """
        Detach a policy from user

        :param user_name: string - user to apply policy to
        :param policy_name: Name to upload policy as
        :param delegate_account: str can be used by Cloud admin in Eucalyptus to choose an account to operate on
        """
        self.debug("Detaching the following policy from " + user_name + ":" + policy_name)
        params = {'UserName': user_name,
                  'PolicyName': policy_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('DeleteUserPolicy', params, verb='POST')

    def get_all_groups(self, account_name=None, account_id=None, path=None, group_name=None, group_id=None, search=False ):
        """
        Queries all accounts matching given account criteria, returns all groups found within these accounts which then match the given user criteria.
        Account info is added to the group dicts

        :param account_name: regex - to use for account_name
        :param account_id: regex - to use for
        :param path: regex - to match for path
        :param group_name: regex - to match for group_name
        :param group_id: regex - to match for group_id
        :param search: boolean - specify whether to use match or search when filtering the returned list
        :return:
        """
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
        """
        Returns groups that match given criteria. By default will return groups from current account.

        :param path: regex - to match for path
        :param group_name: regex - to match for group_name
        :param group_id: regex - to match for group_id
        :param delegate_account: string - to use for delegating account lookup
        :param search: specify whether to use match or search when filtering the returned list
        :return:
        """
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
            if group_name is not None and not re_meth(group_name, group['group_name']):
                continue
            if group_id is not None and not re_meth(group_id, group['group_id']):
                continue
            retlist.append(group)
        return retlist
        
    def get_group_policy_names(self, group_name, policy_name=None,delegate_account=None, search=False):
        """
        Returns list of policy names associated with a given group, and match given criteria.

        :param group_name: string - group to get policies for.
        :param policy_name: regex - to match/filter returned policies
        :param delegate_account: string - used for group lookup
        :param search: specify whether to use match or search when filtering the returned list
        :return: list of policy names
        """
        retlist = []
        params = {}
        if search:
            re_meth = re.search
        else:
            re_meth = re.match
        params = {'GroupName': group_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        response = self.euare.get_response('ListGroupPolicies',params, list_marker='PolicyNames')
        for name in response['list_group_policies_response']['list_group_policies_result']['policy_names']:
            if policy_name is not None and not re_meth(policy_name, name):
                continue
            retlist.append(name)
        return retlist

    def get_group_policies(self, group_name, policy_name=None,delegate_account=None, doc=None, search=False):
        """
        Returns list of policy dicts associated with a given group, and match given criteria.

        :param group_name: string - group to get policies for.
        :param policy_name: regex - to match/filter returned policies
        :param delegate_account: string - used for group lookup
        :param doc: policy document to use as a filter
        :param search: boolean - specify whether to use match or search when filtering the returned list
        :return:
        """
        retlist = []
        params = {}
        if search:
            re_meth = re.search
        else:
            re_meth = re.match
        names = self.get_group_policy_names(group_name, policy_name=policy_name, delegate_account=delegate_account, search=search)

        for p_name in names:
            params = {'GroupName': group_name,
                      'PolicyName': p_name}
            if delegate_account:
                params['DelegateAccount'] = delegate_account
            policy = self.euare.get_response('GetGroupPolicy', params, verb='POST')['get_group_policy_response']['get_group_policy_result']
            if doc is not None and not re_meth(doc, policy['policy_document']):
                continue
            retlist.append(policy)
        return retlist
    
    def create_group(self, group_name,path="/", delegate_account=None):
        """
        Create group.

        :param
        :param path: path for group
        :param delegate_account: str can be used by Cloud admin in Eucalyptus to choose an account to operate on
        """
        self.debug("Attempting to create group: " + group_name)
        params = {'GroupName': group_name,
                  'Path': path}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('CreateGroup', params)
    
    def delete_group(self, group_name, delegate_account=None):
        """
        Delete group.

        :param group_name: name of group to delete
        :param delegate_account:
        """
        self.debug("Deleting group " + group_name)
        params = {'GroupName': group_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('DeleteGroup', params)
    
    def add_user_to_group(self, group_name, user_name, delegate_account=None):
        """
        Add a user to a group.

        :param group_name: name of group to add user to
        :param user_name: name of user to add to group
        :param delegate_account: str can be used by Cloud admin in Eucalyptus to choose an account to operate on
        """
        self.debug("Adding user "  +  user_name + " to group " + group_name)
        params = {'GroupName': group_name,
                  'UserName': user_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('AddUserToGroup', params)
    
    def remove_user_from_group(self, group_name, user_name, delegate_account=None):
        """
        Remove a user from a group.

        :param group_name: name of group to remove user from
        :param user_name: name of user to remove from group
        :param delegate_account: str can be used by Cloud admin in Eucalyptus to choose an account to operate on
        """
        self.debug("Removing user "  +  user_name + " to group " + group_name)
        params = {'GroupName': group_name,
                  'UserName': user_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('RemoveUserFromGroup', params)
    
    def attach_policy_group(self, group_name, policy_name, policy_json, delegate_account=None):
        """
        Attach a policy to a group.

        :param group_name: name of group to remove user from
        :param policy_name: Name to upload policy as
        :param policy_json: Policy text
        :param delegate_account: str can be used by Cloud admin in Eucalyptus to choose an account to operate on
        """
        self.debug("Attaching the following policy to " + group_name + ":" + policy_json)
        params = {'GroupName': group_name,
                  'PolicyName': policy_name,
                  'PolicyDocument': policy_json}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('PutGroupPolicy', params, verb='POST')
    
    def detach_policy_group(self, group_name, policy_name, delegate_account=None):
        """
        Remove a policy from a group.

        :param group_name: name of group to remove user from
        :param policy_name: Name to upload policy as
        :param delegate_account: str can be used by Cloud admin in Eucalyptus to choose an account to operate on
        """
        self.debug("Detaching the following policy from " + group_name + ":" + policy_name)
        params = {'GroupName': group_name,
                  'PolicyName': policy_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('DeleteGroupPolicy', params, verb='POST')
    
    def create_access_key(self, user_name=None, delegate_account=None):
        """
        Create a new access key for the user.

        :param user_name: Name of user to create access key for to
        :param delegate_account: str can be used by Cloud admin in Eucalyptus to choose an account to operate on
        :return: A tuple of access key and and secret key with keys: 'access_key_id' and 'secret_access_key'
        """
        self.debug("Creating access key for " + user_name )
        params = {'UserName': user_name}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        response = self.euare.get_response('CreateAccessKey', params)
        access_tuple = {}
        access_tuple['access_key_id'] = response['create_access_key_response']['create_access_key_result']['access_key']['access_key_id']
        access_tuple['secret_access_key'] = response['create_access_key_response']['create_access_key_result']['access_key']['secret_access_key']
        return access_tuple

    def upload_server_cert(self, cert_name, cert_body, private_key):
        self.debug("uploading server certificate: " + cert_name)
        self.euare.upload_server_cert(cert_name=cert_name, cert_body=cert_body, private_key=private_key)
        if cert_name not in str(self.euare.get_server_certificate(cert_name)):
            raise Exception("certificate " + cert_name + " not uploaded")

    def update_server_cert(self, cert_name, new_cert_name=None, new_path=None):
        self.debug("updating server certificate: " + cert_name)
        self.euare.update_server_cert(cert_name=cert_name, new_cert_name=new_cert_name, new_path=new_path)
        if (new_cert_name and new_path) not in str(self.euare.get_server_certificate(new_cert_name)):
            raise Exception("certificate " + cert_name + " not updated.")

    def get_server_cert(self, cert_name):
        self.debug("getting server certificate: " + cert_name)
        cert = self.euare.get_server_certificate(cert_name=cert_name)
        self.debug(cert)
        return cert

    def delete_server_cert(self, cert_name):
        self.debug("deleting server certificate: " + cert_name)
        self.euare.delete_server_cert(cert_name)
        if (cert_name) in str(self.euare.list_server_certs()):
            raise Exception("certificate " + cert_name + " not deleted.")

    def list_server_certs(self, path_prefix='/', marker=None, max_items=None):
        self.debug("listing server certificates")
        certs = self.euare.list_server_certs(path_prefix=path_prefix, marker=marker, max_items=max_items)
        self.debug(certs)
        return certs

    def create_login_profile(self, user_name, password, delegate_account=None):
        self.debug("Creating login profile for: " + user_name + " with password: " + password)
        params = {'UserName': user_name,
                  'Password': password}
        if delegate_account:
            params['DelegateAccount'] = delegate_account
        self.euare.get_response('CreateLoginProfile', params, verb='POST')