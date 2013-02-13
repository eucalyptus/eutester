'''
Created on Sep 10, 2012
@author            : mmunn

Unit test          : EUCA_3460 euca-bundle-instance does not work with remote WALRUS (takes about 30 minutes to run)
setUp              : Install Credentials, download image
test               : Attempts to bundle a windows instance on a remote walrus. If a Bundle ID is returned the test passes,
                     the windows instance will then be terminated causing the bundle-task to fail, this is expected. 
                     As long bundle-instance can connect with walrus and start the task, the test passes.  
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as Euca3460.py )
IP_ADDRESS   CENTOS  6.3     64      BZR     [CLC]
IP_ADDRESS   CENTOS  6.3     64      BZR     [WS]
IP_ADDRESS   CENTOS  6.3     64      BZR     [CC00 SC00]
IP_ADDRESS   CENTOS  6.3     64      BZR     [NC00]
'''

import unittest
import shutil
import re
from eucaops import Eucaops
from testcases.cloud_user.images.imageutils import ImageUtils

class Euca3460(unittest.TestCase):
    
    def setUp(self):

        self.conf = "cloud.conf"       
        self.imgName = "windowsserver2003r2_ent_x64.kvm.img"
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.source  = "source " + self.tester.credpath + "/eucarc && "
        self.clc1 = self.tester.service_manager.get_enabled_clc() 
        self.iu = ImageUtils(tester=self.tester, config_file=self.conf )
        self.iu.create_emi_from_url( "http://192.168.7.65/windows_images/" + self.imgName )
        self.doAuth()
        
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)
        self.tester.authorize_group(self.group, port=3389, protocol="tcp")
        self.skey = self.tester.get_secret_key()
        self.akey = self.tester.get_access_key()
                   
    def test_EUCA_3460(self):      
        self.emi = self.tester.get_emi(location=self.imgName)
        #Start the windows instance
        self.reservation = self.tester.run_instance(self.emi,type="m1.large", keypair=self.keypair.name, group=self.group, is_reachable=False,timeout=720)
        # Make sure the windows instance is running
        
        for instance in self.reservation.instances:
            if instance.state == "running":
                self.ip = instance.public_dns_name
                self.instanceid = instance.id
                                
        # Attempt to bundle the running windows instance
        print "Access  = " + self.akey 
        print "Secret  = " + self.skey 
        self.cmd = "euca-bundle-instance " + self.instanceid + " -b " + str(self.keypair) + " -p windows -o " + self.akey + " -w " + self.skey
        self.out = self.clc1.machine.cmd(self.source + self.cmd)
        
        # Check for Bundle ID
        match = re.search(r'bun-........', self.out["output"])
        if match:
            self.tester.debug("Passed test_EUCA_3460: Bundle ID = " + match.group())
        else: 
            self.fail("Failed test_EUCA_3460: Bundle ID not returned") 
         
                       
    def tearDown(self):
        if self.reservation is not None:
            self.tester.terminate_instances(self.reservation)  
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath)  
              
                 
    if __name__ == '__main__':
        unittest.main("Euca3460")

