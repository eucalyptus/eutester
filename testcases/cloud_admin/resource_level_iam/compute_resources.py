#!/usr/bin/env python
"""
Purpose:  Testcase to confirm resoure-level permissions
          for Compute (EC2) API actions are supported
          in a Eucalyptus environment

Author:   Harold Spencer, Jr. (https://github.com/hspencer77)
"""
import re
import random
import socket
import os
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
from awacs.aws import Action, Allow, Policy, Statement


class ComputeResourceLevelTest(EutesterTestCase):
    def __init__(self):
        """
        Function to initialize testcase to
        confirm resource-level permissions are
        supported for Compute (EC2) API actions

        param: --credpath: path to directory
                location of Eucalyptus credentials
        """
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument('--clean_on_exit',
                                 action='store_true', default=True,
                                 help=("Boolean, used to flag whether "
                                       + "to run clean up method after "
                                       + "running test list"))
        self.get_args()
        self.tester = Eucaops(credpath=self.args.credpath,
                              config_file=self.args.config,
                              password=self.args.password)
        self.testers = []
        self.regions = []
        self.keypairs = []
        self.accounts = []
        for region in self.tester.ec2.get_all_regions():
            region_info = {'name': str(region.name),
                           'endpoint': str(region.endpoint)}
            self.regions.append(region_info)

    def clean_method(self):
        """
        Function to clean up artifacts associated
        with test case.
        """
        # Delete account, groups, users
        for account in self.accounts:
            self.tester.delete_account(account,
                                       recursive=True)
        # Remove keypairs created
        for key in self.keypairs:
            os.remove(key)

    def remove_testers(self):
        """
        Function to remove testers after testcase
        has completed.
        """
        for tester in self.testers:
            try:
                tester.show_euare_whoami()
            except:
                pass
            tester.cleanup_artifacts()
            self.testers.remove(tester)

    def setup_users(self, account_name, group_name, user_name):
        """
        Function to set up users under a given account as
        testers.  For each user, the following is created:
        - access key id
        - secret key
        - Eucaops object

        param: account_name: IAM (Euare) account
        param: group_name: IAM (Euare) group
        param: user_name: IAM (Euare) user
        """
        users = ['admin', user_name]
        self.tester.info("Setting up users in " + account_name)
        for user in users:
            self.tester.debug("Create access key for "
                              + user + " user in " + account_name)
            keys = self.tester.create_access_key(user_name=user,
                                                 delegate_account=account_name)
            access_key = keys['access_key_id']
            secret_key = keys['secret_access_key']
            self.tester.debug("Creating Eucaops object with access key "
                              + access_key + " and secret key "
                              + secret_key)
            new_tester = Eucaops(aws_access_key_id=access_key,
                                 aws_secret_access_key=secret_key,
                                 ec2_ip=self.tester.ec2.host,
                                 ec2_path=self.tester.ec2.path,
                                 iam_ip=self.tester.euare.host,
                                 iam_path=self.tester.euare.path,
                                 s3_ip=self.tester.s3.host,
                                 s3_path=self.tester.s3.path,
                                 sts_ip=self.tester.tokens.host,
                                 sts_path=self.tester.tokens.path,
                                 cw_ip=self.tester.cw.host,
                                 cw_path=self.tester.cw.path,
                                 as_ip=self.tester.autoscale.host,
                                 as_path=self.tester.autoscale.path,
                                 elb_ip=self.tester.elb.host,
                                 elb_path=self.tester.elb.path,
                                 username=user, account=account_name)
            self.testers.append(new_tester)
            # If not 'admin' user, add user to group
            if user != 'admin':
                self.tester.debug("Adding " + user + " to "
                                  + group_name)
                self.tester.add_user_to_group(group_name,
                                              user,
                                              delegate_account=account_name)

    def group_policy_add(self, group_name, account_name,
                         account_id=None, region=None,
                         instance_id=None):
        """
        Function to create IAM access policy with resource-level
        permission, then apply the policy to a group
        under the account.

        param: group_name: IAM (Euare) group
        param: account_name: IAM (Euare) account
        param: account_id: Account ID
        param: region: region (i.e. cloud) name/endpoint information
        param: instance_id: instance ID
        """
        policy_id = "EC2-Instance-Resource-Level-Permissions"
        sid = "Stmt" + self.tester.id_generator()
        if account_id is None:
            account_id = ""
        if region is None:
            region = ""
        if instance_id is None:
            instance_id = "*"
        ec2_arn = ("arn:aws:ec2:" + region + ":"
                   + account_id + ":"
                   + "instance/" + instance_id)
        pd = Policy(
                 Version="2012-10-17",
                 Id=policy_id,
                 Statement=[
                     Statement(
                         Sid=sid,
                         Effect=Allow,
                         Action=[Action("ec2", "*")],
                         Resource=[ec2_arn],
                     ),
                 ],
             )
        self.tester.debug("Applying " + policy_id + " policy to "
                          + group_name + " group")
        try:
            self.tester.attach_policy_group(group_name,
                                            policy_id,
                                            pd.to_json(),
                                            delegate_account=account_name)
        except Exception as e:
            self.tester.debug("Policy failed to be applied "
                              + "to group " + group_name
                              + ": " + str(e))
            return False
        return True

    def connect_to_ec2_endpoint(self, tester, region):
        """
        Function to establish EC2 connection to a
        specific region (based on endpoint)

        param: tester: Eucaops object
        param: region: region (i.e. cloud) name/endpoint information
        """
        if re.search('^https', region['endpoint']):
            ssl_flag = True
        else:
            ssl_flag = False
        endpoint = region['endpoint'].strip(':8773/')
        fqdn_endpoint = endpoint.strip('http://https://')
        try:
            ip_endpoint = socket.gethostbyname(fqdn_endpoint)
        except Exception as e:
            self.errormsg("Unable to resolve Compute endpoint to "
                          + fqdn_endpoint + ": " + str(e))
            raise e
        tester.info("Establishing EC2 connection to " + region['name']
                    + " region")
        try:
            tester.setup_ec2_connection(
                        endpoint=ip_endpoint,
                        region=region['name'],
                        aws_access_key_id=tester.ec2.aws_access_key_id,
                        aws_secret_access_key=tester.ec2.aws_secret_access_key,
                        port=8773,
                        path="services/compute",
                        is_secure=ssl_flag)
        except Exception as e:
            self.errormsg("Unable to establish EC2 connection to "
                          + "region " + region['name'] + ": " + str(e))
            raise e
        return tester

    def setup_instance_resources(self, tester, region):
        """
        Function to set up EC2 instance resources

        param: tester: Eucaops object ('admin' user)
        param: region: region (i.e. cloud) name/endpoint information
        """
        tester = self.connect_to_ec2_endpoint(tester, region)
        zone = random.choice(tester.get_zones())
        keypair = tester.add_keypair("keypair-" + tester.id_generator())
        keypath = '%s/%s.pem' % (os.curdir, keypair.name)
        self.keypairs.append(keypath)
        group = tester.add_group("group-" + tester.id_generator())
        tester.authorize_group_by_name(group_name=group.name)
        tester.authorize_group_by_name(group_name=group.name,
                                       port=-1,
                                       protocol="icmp")
        # Use supplied EMI, if not find instance-store backed EMI
        if self.args.emi:
            image = tester.get_emi(emi=self.args.emi)
        else:
            image = tester.get_emi(root_device_type="instance-store",
                                   basic_image=True)
        params = {'image': image,
                  'user_data': self.args.user_data,
                  'username': self.args.instance_user,
                  'keypair': keypair.name,
                  'group': group.name,
                  'zone': zone,
                  'return_reservation': True,
                  'timeout': 600}
        reservation = tester.run_image(**params)
        for instance in reservation.instances:
            # Confirm instance reaches 'running' state
            self.assertTrue(tester.wait_for_reservation(reservation),
                            'Instance did not go to running')
            # Confirm instance can be pinged
            self.assertTrue(tester.ping(instance.ip_address),
                            'Could not ping instance')

    def test_instance_resources(self, tester, region):
        """
        Function to perform Compute (EC2) API actions
        to confirm access to all instances under the
        account.

        param: tester: Eucaops object ('instance_admin' user)
        param: region: region (i.e. cloud) name/endpoint information
        """
        tester = self.connect_to_ec2_endpoint(tester, region)
        reservations = tester.ec2.get_all_reservations()
        # Test DescribeInstances
        tester.info("Execute DescribeInstances as "
                    + tester.username + " user")
        for reservation in reservations:
            self.assertIsNotNone(reservation,
                                 msg=("DescribeInstances failed for "
                                      + region['name'] + " region."))
            for instance in reservation.instances:
                # Test DescribeInstanceAttribute
                tester.info("Execute DescribeInstanceAttribute for "
                            + "instance " + instance.id
                            + "in region " + region['name'])
                inst_attr = tester.ec2.get_instance_attribute(
                                instance.id, 'instanceType')
                self.assertIsNotNone(inst_attr,
                                     msg=("DescribeInstanceAttribute "
                                          + "to grab instance type "
                                          + "failed for " + instance.id
                                          + " in region " + region['name']))
                # Test GetConsoleOutput
                tester.info("Execute GetConsoleOutput for "
                            + "instance " + instance.id
                            + "in region " + region['name'])
                self.assertIsNotNone(instance.get_console_output().output,
                                     msg=("GetConsoleOuptut failed "
                                          + "for " + instance.id
                                          + " in region " + region['name']))
                # Test CreateTags
                tester.info("Execute CreateTags for "
                            + "instance " + instance.id
                            + "in region " + region['name'])
                try:
                    instance.add_tag("Purpose",
                                     "Test CreateTags with " + instance.id)
                except Exception as e:
                    self.errormsg("Failed to execute CreateTags with "
                                  + instance.id + " in region "
                                  + region['name'] + ": " + str(e))
                    raise e
                # Test DescribeTags
                tester.info("Execute DescribeTags for "
                            + "instance " + instance.id
                            + "in region " + region['name'])
                self.assertIsNotNone(instance.tags['Purpose'],
                                     msg=("DescribeTags for instance "
                                          + instance.id + "failed in "
                                          + "region " + region['name']))
        # Test DescribeInstanceStatus
        tester.info("Execute DescribeInstanceStatus as "
                    + tester.username + " user")
        stats = tester.ec2.get_all_instance_status()
        for entry in stats:
            self.assertIsNotNone(entry.state_name,
                                 msg=("DescribeInstanceStatus failed for "
                                      + "instance(s) in "
                                      + "region " + region['name']))

    def remove_instance_resources(self, tester, region):
        """
        Function to remove instances from under account

        param: tester: Eucaops object ('admin' user of account)
        param: region: region (i.e. cloud) name/endpoint information
        """
        tester = self.connect_to_ec2_endpoint(tester, region)
        reservations = tester.ec2.get_all_reservations()
        for reservation in reservations:
            tester.terminate_instances(reservation)

    def InstanceWildcardResourceLevelTest(self):
        """
        [**] NEGATIVE TEST [**]
        Function to execute testcase to confirm
        malformed document error when IAM access policies for
        Compute API actions with resource-level defined ARN
        (containing wildcards for 'region' and 'account-id') for instance(s)
        under a given IAM (Euare) account.

        IAM access policy contains the following:
        - Effect: Allow
        - Action: All EC2 actions (i.e. ec2:*)
        - Resource: All instances (i.e. arn:aws:ec2:*:*:instance/*)

        The following is performed:
        * IAM (Euare) account/user/group creation
        * IAM access policy with resource ARN, which contains
          wildcard (*) for 'region' and 'account-id',
          defined for all instances.
        """
        account_name = 'wildcards-acct-account'
        self.accounts.append(account_name)
        group_name = 'ec2_instance_admins'
        self.tester.info("Creating " + account_name)
        # Create 'ec2-account' account
        self.tester.create_account(account_name)
        self.tester.info("Creating " + group_name
                         + " in account " + account_name)
        # Create 'ec2_instance_admins' group and add IAM policy
        self.tester.create_group(group_name, "/",
                                 delegate_account=account_name)
        region_name = "*"
        account_id = "*"
        result = self.group_policy_add(group_name, account_name,
                                       account_id=account_id,
                                       region=region_name)
        # Confirm IAM policy wasn't accepted
        self.tester.debug("Applied malformed policy. Test should"
                          + " pass on failed upload of policy.")
        self.assertFalse(result, msg=("Malformed IAM access policy "
                         + "with wildcard(*) value for 'region' and "
                         + "'account-id' was accepted"))

    def InstanceAccountResourceLevelTest(self):
        """
        Function to execute testcase to confirm
        support Compute API actions for resource-level defined ARN
        (containing 'account-id') for instance(s)
        under a given IAM (Euare) account.

        IAM access policy contains the following:
        - Effect: Allow
        - Action: All EC2 actions (i.e. ec2:*)
        - Resource: All instances (i.e. arn:aws:ec2::<account-id>:instance/*)

        The following is performed:
        * IAM (Euare) account/user/group creation
        * IAM access policy with resource ARN, which contains
          'account-id',  defined for all instances.
        * Creation of instances by 'admin' user of account
        * Test API actions associated with instances under the
          account by 'instance_admin' user
        * Removal of instances by 'admin' user of account
        """
        account_name = 'strict-acct-account'
        self.accounts.append(account_name)
        group_name = 'ec2_instance_admins'
        user_name = 'instance_admin'
        self.tester.info("Creating " + account_name)
        # Create 'ec2-account' account
        self.tester.create_account(account_name)
        self.tester.info("Creating " + group_name
                         + " in account " + account_name)
        # Create 'ec2_instance_admins' group and add IAM policy
        self.tester.create_group(group_name, "/",
                                 delegate_account=account_name)
        try:
            usr = self.tester.get_users_from_account(
                                          delegate_account=account_name)
        except Exception as e:
            self.errormsg("Failed obtain 'admin' user "
                          + " from account "
                          + account_name + ": " + str(e))
            raise e
        admin_user = usr[0]
        account_id = str(admin_user['arn'].split(':')[4])
        result = self.group_policy_add(group_name, account_name,
                                       account_id=account_id)
        if result:
            # Create 'instance_admin' user
            self.tester.create_user(user_name,
                                    "/",
                                    delegate_account=account_name)
            # Set up test users
            self.setup_users(account_name,
                             group_name,
                             user_name)
            for resource_tester in self.testers:
                if resource_tester.username == 'admin':
                    # If 'admin' user, create EC2 resources
                    for region in self.regions:
                        self.setup_instance_resources(resource_tester,
                                                      region)
                else:
                    # Test API actions against instance resources
                    for region in self.regions:
                        self.test_instance_resources(resource_tester,
                                                     region)
            for resource_tester in self.testers:
                if resource_tester.username == 'admin':
                    # If 'admin' user, remove EC2 resources
                    for region in self.regions:
                        self.remove_instance_resources(resource_tester,
                                                       region)
            # Remove testers from self.testers list
            self.remove_testers()

    def InstanceWildcardAccountResourceLevelTest(self):
        """
        [**] NEGATIVE TEST [**]
        Function to execute testcase to confirm
        malformed document error for IAM access policy for
        Compute API actions with resource-level defined ARN
        (containing a wildcard for 'account-id') for instance(s)
        under a given IAM (Euare) account.

        IAM access policy contains the following:
        - Effect: Allow
        - Action: All EC2 actions (i.e. ec2:*)
        - Resource: All instances (i.e. arn:aws:ec2::*:instance/*)

        The following is performed:
        * IAM (Euare) account/user/group creation
        * IAM access policy with resource ARN, which contains
          a wildcard for 'account-id',  defined for all instances.
        """
        account_name = 'wildcardacct-acct-account'
        self.accounts.append(account_name)
        group_name = 'ec2_instance_admins'
        self.tester.info("Creating " + account_name)
        # Create 'ec2-account' account
        self.tester.create_account(account_name)
        self.tester.info("Creating " + group_name
                         + " in account " + account_name)
        # Create 'ec2_instance_admins' group and add IAM policy
        self.tester.create_group(group_name, "/",
                                 delegate_account=account_name)
        account_id = "*"
        result = self.group_policy_add(group_name, account_name,
                                       account_id=account_id)
        # Confirm IAM policy wasn't accepted
        self.tester.debug("Applied malformed policy. Test should"
                          + " pass on failed upload of policy.")
        self.assertFalse(result, msg=("Malformed IAM access policy "
                         + "with wildcard(*) value 'account-id' "
                         + "was accepted"))

    def InstanceResourceLevelTest(self):
        """
        Function to execute testcase to confirm
        support Compute API actions for resource-level defined ARN
        for instance(s) under a given IAM (Euare) account.

        IAM access policy contains the following:
        - Effect: Allow
        - Action: All EC2 actions (i.e. ec2:*)
        - Resource: All instances (i.e. arn:aws:ec2:::instance/*)

        The following is performed:
        * IAM (Euare) account/user/group creation
        * IAM access policy with resource ARN defined for all
          instances.
        * Creation of instances by 'admin' user of account
        * Test API actions associated with instances under the
          account by 'instance_admin' user
        * Removal of instances by 'admin' user of account
        """
        account_name = 'basic-account'
        self.accounts.append(account_name)
        group_name = 'ec2_instance_admins'
        user_name = 'instance_admin'
        self.tester.info("Creating " + account_name)
        # Create 'ec2-account' account
        self.tester.create_account(account_name)
        self.tester.info("Creating " + group_name
                         + " in account " + account_name)
        # Create 'ec2_instance_admins' group and add IAM policy
        self.tester.create_group(group_name, "/",
                                 delegate_account=account_name)
        result = self.group_policy_add(group_name, account_name)
        if result:
            # Create 'instance_admin' user
            self.tester.create_user(user_name,
                                    "/",
                                    delegate_account=account_name)
            # Set up test users
            self.setup_users(account_name,
                             group_name,
                             user_name)
            for resource_tester in self.testers:
                if resource_tester.username == 'admin':
                    # If 'admin' user, create EC2 resources
                    for region in self.regions:
                        self.setup_instance_resources(resource_tester, region)
                else:
                    # Test API actions against instance resources
                    for region in self.regions:
                        self.test_instance_resources(resource_tester, region)
            for resource_tester in self.testers:
                if resource_tester.username == 'admin':
                    # If 'admin' user, remove EC2 resources
                    for region in self.regions:
                        self.remove_instance_resources(resource_tester, region)
            # Remove testers from self.testers list
            self.remove_testers()

if __name__ == '__main__':
    # Define ComputeResourceLevelTest testcase
    testcase = ComputeResourceLevelTest()
    list = ['InstanceResourceLevelTest', 'InstanceAccountResourceLevelTest',
            'InstanceWildcardAccountResourceLevelTest',
            'InstanceWildcardResourceLevelTest']
    unit_list = []
    for test in list:
        unit_list.append(testcase.create_testunit_by_name(test))
    # Execute testcase
    result = testcase.run_test_case_list(
                         unit_list,
                         clean_on_exit=testcase.args.clean_on_exit)
    exit(result)
