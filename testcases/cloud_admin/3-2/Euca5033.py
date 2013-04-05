'''
Created on Oct 9, 2012
@author: mmunn
Unit test          : EUCA-5033 Cannot detach root EBS volume from stopped instance
                     This test assumes you have created and registered an ebs-image
                     you can use:
                     create_bfebs_img_test.py  
                     --url  http://192.168.7.65/bfebs-image/vmware/bfebs_vmwaretools.img
                     --config ../../cloud_admin/cloud.conf
                     -p foobar
setUp              : creates tester and credentials
test               : runs euca-detach-volume and euca-attach-volume on "stopped" EBS instance
tearDown           : terminate instance remove credentials

cloud.conf:( put in same directory as this testcase )
IP_ADDRESS  CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP_ADDRESS  CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca5033(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf"
        self.device = "/dev/sda1"       
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.doAuth()
       
    def tearDown(self):
        self.tester.cleanup_artifacts()
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath)
        
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)
        
    def testEBS(self):
        # Get the existing EBS emi 
        self.emi = self.tester.get_emi(root_device_type='ebs')
        # Start instance
        self.reservation = self.tester.run_instance(self.emi, keypair=self.keypair.name, group=self.group, is_reachable=False)
        # Make sure the instance is running set instance variables
        for instance in self.reservation.instances:
            if instance.state == "running":
                self.instance = instance
                self.zone = instance.placement
        # Run test
        self.rootVolume = self.tester.get_volume(attached_dev=self.device)
        self.tester.stop_instances(self.reservation)
        # EBS Instance now in stopped state, try and detach/attach root volume.
        self.tester.detach_volume(self.rootVolume)
        self.tester.attach_volume(self.instance, self.rootVolume, self.device )
        # Make sure instance will start.
        self.tester.start_instances(self.reservation)
        pass

if __name__ == "__main__":
    unittest.main("Euca5033")

    