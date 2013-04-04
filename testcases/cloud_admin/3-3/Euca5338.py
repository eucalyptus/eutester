'''
Created on Mar 14, 2013
@author: mmunn
Unit test          : EUCA-5338 Eucalyptus Reporting: Usage information incorrect
setUp              : Install Credentials,
test               : create and delete a volume, run report volume twice, compare report output to see if
                     the GB-Secs is still increasing after the volume id deleted
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from datetime import date
from datetime import timedelta
from eucaops import Eucaops

class Euca5338(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf" 
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.doAuth()
        self.startDate = date.today()
        self.endDate = date.today() + timedelta(days=1)
        self.dates  = "-s " + str(self.startDate) +  " -e " + str(self.endDate)
        self.cmd = "eureport-generate-report " + self.dates + " --time-unit=seconds --format=csv -t volume"
        self.source  = "source " + self.tester.credpath + "/eucarc && "

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
        # Get availibility zone
        self.zone = self.tester.get_zones().pop()
        # Create and delete a volume
        self.volume = self.tester.create_volume(self.zone)
        self.tester.delete_volume(self.volume)
        # run report, save output and wait 10 seconds
        self.out1 = self.tester.sys(self.source + self.cmd)
        self.tester.sleep(10)
        # run report again
        self.out2 = self.tester.sys(self.source + self.cmd)
        # Get the string index for the volume specific information from the report
        self.index = str(self.out1).find(self.volume.id)
        # get the newly created/deleted volume information from the two reports
        self.volStringOne = str(self.out1)[self.index:self.index + 21]
        self.volStringTwo = str(self.out2)[self.index:self.index + 21]
        
        # Compare strings to make sure the GB-Secs is not increasing for the deleted volume.
        self.tester.debug("Report 1 = " + self.volStringOne + "  Report 2 = " + self.volStringTwo)
        if self.volStringOne == self.volStringTwo :
            self.tester.debug("SUCCESS the GB-Secs did not increase for deleted volume " + self.volume.id)
            pass
        else:
            self.fail("FAIL GB-Secs increased for deleted volume " + self.volume.id)
        
if __name__ == "__main__":
    unittest.main("Euca5338")
    