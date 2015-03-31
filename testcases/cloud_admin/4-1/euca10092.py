'''
Created on = '10/28/13"
Author = 'mmunn'

Unit test          : EUCA-10092 Vague Error Message from CreateLoadBalancer when using incorrect load balancer port
setUp              : Install Credentials,
test               :
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

    def tearDown(self):
        #reset property
        self.runSysCmd("euca-modify-property -r services.loadbalancing.restricted_ports")
        self.tester.cleanup_artifacts()
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem")
        shutil.rmtree(self.tester.credpath)

    def runSysCmd(self, cmd):
        self.source = 'export EUCALYPTUS=' + self.tester.eucapath + " && source " + self.tester.credpath + "/eucarc && " + self.tester.eucapath + "/usr/sbin/"
        self.out = self.tester.sys(self.source + cmd)

    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def test(self):
        # Restrict ports 1-100 for lb creation"
        self.tester.modify_property('services.loadbalancing.restricted_ports','1-100')
        try:
            # try and reate a loadbalancer using a restricted port defined in property "services.loadbalancing.restricted_port"
            self.tester.create_load_balancer(zones=self.tester.get_euzones(),load_balancer_port=44)
            # The lb should not be created on restricted port and should have thrown an error
            self.fail("Loadbalancer created with restricted port.")
        except Exception, e:
            self.tester.debug(e)
            # check for restricted ports in error message
            assert str(e).count('1-100')

if __name__ == "__main__":
    unittest.main()
