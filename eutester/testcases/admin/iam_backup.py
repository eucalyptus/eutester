#!/usr/bin/python

import re
import urllib2
from eutester.euca.euca_ops import Eucaops
from eutester.utils.eutestcase import EutesterTestCase


class IamBackup(EutesterTestCase):
    def __init__(self):
        self.setuptestcase()
        self.setup_parser()
        self.get_args()

        self.tester = Eucaops(config_file=self.args.config, password=self.args.password, credpath=self.args.credpath)
        self.backup_file = open('account_backup.sh', 'w')

        self.backup_file.write("#!/bin/bash\n\nEIAMDIR=/root/USERCREDS\n\n")
        self.backup_file.write("mkdir $EIAMDIR; mkdir $EIAMDIR/eucalyptus-admin; cd $EIAMDIR/eucalyptus-admin\n")
        self.backup_file.write("euca-get-credentials admin.zip; unzip admin.zip; source eucarc; cd $EIAMDIR/\n")

    def clean_method(self):
        pass

    def backup_all(self):
        accounts = []
        all_accounts = self.tester.iam.get_all_accounts()
        for account in all_accounts:
            if not re.search('eucalyptus', account['account_name']):
                accounts.append(account)
        for account in accounts:
            account_name = account['account_name']
            self.backup_file.write("euare-accountcreate -a %s\n" % account_name)
            self.backup_file.write("mkdir $EIAMDIR/%s; cd $EIAMDIR/%s\n" % (account_name, account_name))
            self.backup_file.write("euca-get-credentials -a %s %s.zip\n" % (account_name, account_name))
            self.backup_file.write("unzip %s.zip; source eucarc\n" % account_name)

            new_tester = Eucaops(config_file=self.args.config, password=self.args.password,
                                 account=account_name, user='admin')
            users = new_tester.iam.get_users_from_account()
            for user in users:
                user_name = user['user_name']
                user_path = user['path']
                self.tester.debug("Got user name '%s'" % user_name)
                if user_name != 'admin':
                    self.backup_file.write("euare-usercreate -u %s -p %s\n" % (user_name, user_path))
                    self.backup_file.write("mkdir $EIAMDIR/%s; cd $EIAMDIR/%s\n" % (user_name, user_name))
                    self.backup_file.write("euca-get-credentials -a %s -u %s %s.zip; cd $EIAMDIR/%s\n"
                                           % (account_name, user_name, user_name, account_name))
                    self.tester.debug("Getting policies of user: '%s'" % user_name)
                    user_policies = new_tester.iam.get_user_policies(user_name)
                    for policy in user_policies:
                        pol = urllib2.unquote(policy['policy_document'])
                        pol = pol.replace('\'', '\"')
                        self.backup_file.write("euare-useruploadpolicy -u %s -p %s -o '%s'\n"
                                               % (user_name, policy['policy_name'], pol))

            groups = new_tester.iam.get_groups_from_account()
            for group in groups:
                group_name = group['group_name']
                group_path = group['path']
                self.backup_file.write("euare-groupcreate -g %s -p %s\n" % (group_name, group_path))
                group_users = new_tester.iam.get_users_from_group(group_name=group_name)
                for user in group_users:
                    self.backup_file.write("euare-groupadduser -g %s -u %s\n" % (group_name, user['user_name']))
            self.backup_file.write("cd $EIAMDIR/\n")
            self.backup_file.write("source $EIAMDIR/eucalyptus-admin/eucarc\n")
            self.backup_file.write("\n")
        self.backup_file.close()

if __name__ == "__main__":
    testcase = IamBackup()
    test_list = testcase.args.tests or ["backup_all"]
    unit_list = []
    for test in test_list:
        unit_list.append(testcase.create_testunit_by_name(test))
    result = testcase.run_test_case_list(unit_list, clean_on_exit=True)
    exit(result)