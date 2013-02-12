'''
Created on Oct 4, 2012
@author: mmunn
Unit test          : EUCA-2322 CLC has incorrect default encoding
setUp              : set variables and credentials
test               : Check for default File-Encoding = UTF-8
tearDown           : Removes Credentials, terminates instance

cloud.conf:( in same directory as this test )
IP_ADDRESS  CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP_ADDRESS  CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca2322(unittest.TestCase):

    def setUp(self):
        self.tester  = Eucaops( config_file="cloud.conf", password="foobar" )
        self.source  = "source " + self.tester.credpath + "/eucarc && "
        self.sbin = self.tester.eucapath + "/usr/sbin/"
        self.cmd = "euca-modify-property -peuca=\'System.getProperty(\"file.encoding\")\'"
        self.doAuth()
    
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def tearDown(self):
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath)

    def testEncoding(self):
        #call euca-modify-property which in turn calls System.getProperty("file.encoding")
        prop_string = self.tester.sys(self.source + self.sbin + self.cmd)
        # parse out the  file.encoding value 
        if (prop_string != []):
            value = str(prop_string[0]).split()[2]
        # compare the return values pass it is "UTF-8" fail otherwise  
        if not cmp( value, "UTF-8"):
            self.tester.debug("Passed Euca2322 default file.encoding = " + value)
            pass
        else: 
            self.fail("Failed Euca2322 default file.encoding " + value + " != UTF-8" ) 
        
if __name__ == "__main__":
    unittest.main("Euca2322")