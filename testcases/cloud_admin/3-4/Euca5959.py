'''
Created on = '11/21/13"
Author = 'mmunn'

Unit test          : EUCA-5959 stopped instances show invalid value for public private DNS names
                     This test assumes you have a registered ebs-image, you can use:
                     bfebstest.py --imgurl http://mirror.eucalyptus-systems.com/images/bfebs-image/vmware/bfebs_vmwaretools.img
                                  --config ../../cloud_admin/3-4/cloud.conf --password foobar --tests RegisterImage
setUp              : Install Credentials,
test               : enable dns, start and then stop an ebs backed instance and check for public/private DNS names in
                      euca-descibe-instances output
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops


class EucaTest(unittest.TestCase):
    def setUp(self):
        self.conf = "cloud.conf"
        self.tester = Eucaops(config_file=self.conf, password="foobar")
        self.doAuth()
        self.OK = '\033[1m\033[37m\033[42m'
        self.ENDC = '\033[0m'

    def tearDown(self):
        self.tester.cleanup_artifacts()
        self.tester.modify_property('bootstrap.webservices.use_instance_dns' , 'false')
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem")
        shutil.rmtree(self.tester.credpath)

    def runInstances(self, numMax):
        self.emi = self.tester.get_emi(root_device_type='ebs')
        #Start instance
        self.reservation = self.tester.run_instance(self.emi, keypair=self.keypair.name, group=self.group, min=1, max=numMax,
                                                    is_reachable=False)
        # Make sure the instance is running       
        for instance in self.reservation.instances:
            if instance.state == "running":
                self.ip = instance.public_dns_name
                self.instanceid = instance.id

    def runSysCmd(self, cmd):
        self.source = "source " + self.tester.credpath + "/eucarc && "
        self.out = self.tester.sys(self.source + cmd)

    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def test(self):
        self.tester.modify_property('bootstrap.webservices.use_instance_dns' , 'true')
        self.runInstances(1)
        self.tester.stop_instances(self.reservation)
        self.runSysCmd('euca-describe-instances ' + self.instanceid)
        # make sure publicdnsname and privatednsname fields are empty in euca-descibe-instances output
        assert str(self.out).count('eucalyptus.internal') == 0
        assert str(self.out).count('eucalyptus.localhost') == 0
        print self.OK + 'SUCCESS: publicdns and privatedns fields are empty in euca-descibe-instances output' + self.ENDC

if __name__ == "__main__":
    unittest.main()