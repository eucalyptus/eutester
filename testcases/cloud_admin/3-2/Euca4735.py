'''
Created on Jan 22, 2013
@author: mmunn
Unit test          : 
setUp              : Install Credentials,
test               : 
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca4735(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf"       
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

    def testName(self):
        self.emi = self.tester.get_emi(root_device_type='instance-store')
        self.ins= self.tester.run_image(image=self.emi, keypair=self.keypair, max=4, monitor_to_running=False, clean_on_fail=True)
        for i in self.ins:
            print 'killing instance: '+ str(i.id)
            i.terminate()
        print self.ins
    
if __name__ == "__main__":
    unittest.main("Euca4735")
    