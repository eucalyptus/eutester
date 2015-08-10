'''
Created on = '10/28/13"
Author = 'mmunn'

Unit test          : EUCA-9959 MalformedPolicyDocument: Policy document should not specify a principal." Should Be Returned
setUp              : Install Credentials,
test               : create role with MalformedPolicyDocument and make sure an error message is returned instead of the policy text
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
import os
from eucaops import Eucaops


class Euca(unittest.TestCase):
    def setUp(self):
        self.conf = "../cloud.conf"
        self.tester = Eucaops(config_file=self.conf, password="foobar")
        self.doAuth()
        self.STARTC = '\033[1m\033[1m\033[42m'
        self.ENDC = '\033[0m'
        self.account = "9959-account"
        self.groupname = "9959-group"
        self.username ="9959-user"

    def tearDown(self):
        self.tester.delete_account(self.account, recursive=True)
        self.tester.sys('rm -rf role-describe-instances-principle.json')
        self.tester.sys('rm -rf role-trust.json')
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
        # create account, group and user
        self.tester.create_account(account_name=self.account)
        self.tester.create_group(self.groupname, "/", self.account)
        self.tester.create_user(self.username, "/", self.account)
        self.tester.add_user_to_group(self.groupname,self.username,self.account)
        # copy json to clc
        self.clc_ip = str(self.tester.clc.hostname)
        os.system('scp role-describe-instances-principle.json root@' + self.clc_ip + ':role-describe-instances-principle.json')
        os.system('scp role-trust.json root@' + self.clc_ip + ':role-trust.json')
        # create user role
        self.runSysCmd("euare-rolecreate -r describe-instances -f role-trust.json --region " + self.account + "-" + self.username)
        self.runSysCmd("euare-roleuploadpolicy -r describe-instances -p describe-instances-policy -f role-describe-instances-principle.json  --region " + self.account + "-" + self.username)
        print self.STARTC + "Success " + str(self.out) + " ENABLED " + self.ENDC
        # Check to see that the error message was thrown and not the text from the json file.
        count = str(self.out).count("Policy document should not specify a principal.")
        if count > 0 :
            self.tester.debug("SUCCESS")
            pass
        else:
            self.fail("FAILED : correct error message not thrown")


if __name__ == "__main__":
    unittest.main()
