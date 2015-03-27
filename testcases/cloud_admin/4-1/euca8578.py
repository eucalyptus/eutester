'''
Created on = '10/28/13"
Author = 'mmunn'

Unit test          : EUCA-8578 Allow 0 value in IAM Quota Policy
setUp              : Install Credentials,
test               : Try and attach the policy with ec2:quota-vminstancenumber = 0
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
import sys
import xml.etree.ElementTree as et
import pprint

from eucaops import Eucaops


class Euca(unittest.TestCase):
    def setUp(self):
        self.conf = "../cloud.conf"
        self.tester = Eucaops(config_file=self.conf, password="foobar")
        self.doAuth()
        self.STARTC = '\033[1m\033[1m\033[42m'
        self.ENDC = '\033[0m'
        self.condition_policy = """{
        "Statement": [
           {
             "Effect": "Limit",
             "Resource": "*",
             "Action": ["ec2:RunInstances"],
             "Condition": { "NumericLessThanEquals": { "ec2:quota-vminstancenumber": "0"} }
           }
        ]}"""

    def tearDown(self):
        self.tester.delete_account(self.account, recursive=True)
        self.tester.cleanup_artifacts()
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem")
        shutil.rmtree(self.tester.credpath)

    def runSysCmd(self, cmd):
        self.source = "source " + self.tester.credpath + "/eucarc && "
        self.out = self.tester.sys(self.source + cmd)

    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def test(self):
        self.account ="test-acct-x"
        self.group = "test-group-x"
        self.tester.create_account(self.account)
        self.tester.create_group(self.group, "/", self.account)
        # This should now attach without "Error in uploaded policy: net.sf.json.JSONException: Invalid value for ec2:quota-vminstancenumber: 0"
        self.tester.attach_policy_group(self.group, 'zeroLimit', self.condition_policy, self.account)
        pass

if __name__ == "__main__":
    unittest.main()
