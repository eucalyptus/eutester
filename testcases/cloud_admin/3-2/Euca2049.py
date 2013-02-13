import unittest
import shutil
from eucaops import Eucaops

'''
Created on Sep 10, 2012
@author   : mmunn
Unit test : EUCA-2049 eucalyptus-cloud binary does not honor --bind-addr argument

setup     : comments out existing CLOUD_OPTS in eucalyptus.conf and adds new --bind-addr argument then restarts CLC
test      : checks log files to make sure the new --bind-addr was in fact bound at restart. The log message
            "Identified local bind address:IP_Address" is only seen if address is actually bound.
            Without the fix for 2049 you would never see this message.
restart   : Restarts the CLC and waits until it is in enabled state
teardown  : restore eucalyptus.conf to original state, restart CLC and cleanup credentials

cloud.conf:( in same directory as Euca2049.py )
IP_ADDRESS  CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP_ADDRESS  CENTOS  6.3     64      BZR     [NC00]

'''

class Euca2049(unittest.TestCase):
    
    def setUp(self):
        self.tester = Eucaops( config_file="cloud.conf", password="foobar" )
        self.clc1 = self.tester.service_manager.get_enabled_clc() 
        self.IP = self.tester.get_ec2_ip() 
        self.conf = self.tester.eucapath + "/etc/eucalyptus/eucalyptus.conf" 
        self.CLOUD_OPTS ="echo \"CLOUD_OPTS='--java-home=/usr/lib/jvm/java-1.6.0-openjdk.x86_64 --debug --db-home=/usr/pgsql-9.1/ --bind-addr=" + self.IP + "'\"  >> " + self.conf
        #Comment out existing CLOUD_OPTS            
        self.clc1.machine.sys( "sed -i 's/^CLOUD_OPTS/#CLOUD_OPTS/g\' " + self.conf )
        #Add new CLOUD_OPTS with  --bind-addr
        self.clc1.machine.sys( self.CLOUD_OPTS )
        self.restart()
           
    def test_bindaddress(self):
        self.logFile = self.tester.eucapath + "/var/log/eucalyptus/cloud-output.log"
        self.logMsg = "'Identified local bind address:'"
        #check log file to see if address was bound at CLC startup
        if not self.clc1.machine.found( "grep " + self.logMsg + " " + self.logFile , self.IP):
            self.fail("New CLOUD_OPTS --bind-addr = " + self.IP + " not added.")
           
    def restart(self):
        self.tester.service_manager.stop( self.clc1 )
        self.tester.service_manager.start( self.clc1 )
        self.tester.sleep(60)
        self.tester.service_manager.wait_for_service( self.clc1,"ENABLED", False )
               
    def tearDown(self):
        #Remove added Cloud_OPTS 
        self.clc1.machine.sys( "sed -i '$d' " + self.conf)       
        #Uncomment original Cloud_OPTS
        self.clc1.machine.sys( "sed -i 's/#CLOUD_OPTS/CLOUD_OPTS/g' " + self.conf )        
        self.restart()
        shutil.rmtree(self.tester.credpath)
                
    if __name__ == '__main__':
        unittest.main("Euca2049")
