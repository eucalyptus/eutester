'''
Created on = '7/9/14"
Author = 'mmunn'

Unit test          : EUCA-8906 De-register/Re-register of Cluster with Different Name Doesn't Work
setUp              : Install Credentials,
test               : De-register a cluster Re-register Cluster with Different Name make sure it goes to ENABLED
tearDown           : Cleanup artifacts

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.5    64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.5    64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops


class EucaTest(unittest.TestCase):
    def setUp(self):
        self.conf = "cloud.conf"
        self.tester = Eucaops(config_file=self.conf, password="foobar")
        self.doAuth()
        self.STARTC = '\033[1m\033[1m\033[42m'
        self.ENDC = '\033[0m'
        self.cc= self.tester.service_manager.get_all_cluster_controllers()[3]
        self.orig_name = self.cc.name

    def tearDown(self):
        # deregister cluster
        self.runSysCmd("/opt/eucalyptus/usr/sbin/euca_conf --deregister-cluster --partition "
                       + self.cc.partition + " --host " +  self.cc.hostname + " --component " + self.cc.name + '_TEST' )
        # register cluster
        self.runSysCmd("/opt/eucalyptus/usr/sbin/euca_conf --register-cluster --partition "
                       + self.cc.partition + " --host " +  self.cc.hostname + " --component " + self.orig_name)
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
        # deregister cluster
        self.runSysCmd("/opt/eucalyptus/usr/sbin/euca_conf --deregister-cluster --partition "
                       + self.cc.partition + " --host " +  self.cc.hostname + " --component " + self.cc.name)
        # register cluster
        self.runSysCmd("/opt/eucalyptus/usr/sbin/euca_conf --register-cluster --partition "
                       + self.cc.partition + " --host " +  self.cc.hostname + " --component " + self.cc.name + '_TEST' )
        # Sleep for 10 seconds while cluster Enables
        print self.STARTC +  " Sleep for 10 seconds while cluster Enables. " + self.ENDC
        self.tester.sleep(10)
        # Make sure newly registered cluster with a different name is ENABLED
        try :
            check_cc = self.tester.service_manager.get_all_cluster_controllers(hostname=self.cc.hostname,
                     state="ENABLED", use_cached_list=False)[0]
            print self.STARTC + "Success " + str(check_cc.name) + " ENABLED " + self.ENDC
            pass
        except Exception, e:
            self.fail("Renamed cluster not enabled!")

if __name__ == "__main__":
    unittest.main()