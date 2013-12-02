'''
Created on = '10/28/13"
Author = 'mmunn'

Unit test          : EUCA-5876 LDAP Sync: fails to look up and sync users
setUp              : Install Credentials,
test               : modify authentication.ldap_integration_configuration property and make sure that the users sync.
tearDown           : Removes Credentials, terminates instance
NOTE               : The ldap server is configured in the lic file

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
        self.conf = "cloud.conf"
        self.tester = Eucaops(config_file=self.conf, password="foobar")
        self.doAuth()
        self.OK = '\033[1m\033[37m\033[42m'
        self.ENDC = '\033[0m'

    def tearDown(self):
        self.runSysCmd('euca-modify-property --property-to-reset authentication.ldap_integration_configuration')
        self.tester.delete_account('account-euca5876', recursive=True)
        self.tester.sys('rm -rf euca5876.lic')
        self.tester.cleanup_artifacts()
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem")
        shutil.rmtree(self.tester.credpath)

    def runSysCmd(self, cmd):
        self.source =  'export EUCALYPTUS=' + self.tester.eucapath + " && source " + self.tester.credpath + "/eucarc && "  + self.tester.eucapath + "/usr/sbin/"
        self.out = self.tester.sys(self.source + cmd)

    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def test(self):
        self.clc_ip = str(self.tester.clc.hostname)
        os.system('scp euca5876.lic root@' + self.clc_ip + ':euca5876.lic')
        self.runSysCmd('euca-modify-property --property-to-reset authentication.ldap_integration_configuration')
        self.runSysCmd('euca-lictool --password password --custom euca5876.lic --out euca5876.lic --nocomment')
        self.runSysCmd('euca-modify-property -f authentication.ldap_integration_configuration=euca5876.lic')
        # Wait for LDAP to sync
        self.tester.sleep(20)
        # Count the numbers of users in the euca5876 group and make sure it is over 100
        self.out = str(self.tester.sys('euare-grouplistusers -g euca5876 --as-account account-euca5876')).count('arn:aws:iam::')
        print self.OK + 'Number of users created = ' + str(self.out) + self.ENDC
        assert self.out > 100
if __name__ == "__main__":
    unittest.main()