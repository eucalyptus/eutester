'''
Created on = '11/13/13"
Author = 'mmunn'

Unit test          : EUCA-8121 Instance restoration fails for instances w/o kernel and/or ramdisk and/or in SYSTEM mode
setUp              : Install Credentials
test               : Start windows instance, stop NC, wait for instance to terminate and be removed from
                     euca-describe-instances output, restart NC, wait for instance to be restored to
                     euca-describe-instances output. If the instance is not restored in 5 minutes the test times out and
                     fails..
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
import time
from eucaops import Eucaops
from testcases.cloud_user.images.imageutils import ImageUtils


class EucaTest(unittest.TestCase):
    def setUp(self):
        self.start_total_time = time.time()
        self.conf = 'cloud.conf'
        self.tester = Eucaops(config_file=self.conf, password='foobar')
        self.doAuth()
        self.OK = '\033[1m\033[37m\033[42m'
        self.ENDC = '\033[0m'
        self.imgName = "windowsserver2003r2_ent_x64.kvm.img"

    def tearDown(self):
        self.tester.terminate_instances(self.reservation)
        self.tester.modify_property('cloud.vmstate.instance_timeout' , '720' )
        self.tester.modify_property('cloud.vmstate.terminated_time' , '60' )
        self.tester.delete_keypair(self.keypair)
        self.tester.local('rm ' + self.keypair.name + '.pem')
        shutil.rmtree(self.tester.credpath)

    def get_windows_image(self):
        # Check for windows image if there is not one get it.
        try:
          self.emi = self.tester.get_emi(location='windows')
        except:
           self.iu = ImageUtils(tester=self.tester, config_file=self.conf )
           self.iu.create_emi_from_url( "http://mirror.eucalyptus-systems.com/images/windows_images/" + self.imgName )
           self.emi = self.tester.get_emi(location='windows')

    def runInstances(self, numMax):
        self.emi = self.tester.get_emi(location='windows')
        #Start the windows instance
        self.reservation = self.tester.run_instance(self.emi,type="m1.large", keypair=self.keypair.name, group=self.group, is_reachable=False,timeout=720)
        # Make sure the windows instance is running
        for instance in self.reservation.instances:
            if instance.state == "running":
                self.ip = instance.public_dns_name
                self.instanceid = instance.id
                self.instance = instance

    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def print_time(self, start):
        elapsed = time.time() - start
        minutes = int(elapsed / 60)
        seconds = int(elapsed % 60)
        print self.OK + "Elapsed time = " +  str(minutes) + ' min ' + str(seconds) + ' sec ' + self.ENDC


    def test(self):
        self.get_windows_image()
        self.tester.modify_property('cloud.vmstate.instance_timeout' , '5' )
        self.tester.modify_property('cloud.vmstate.terminated_time' , '1' )
        self.eunode = self.tester.service_manager.get_all_node_controllers()[0]
        #start an instance
        self.runInstances(1)
        #stop the node controller
        self.eunode.stop()

        # wait for instance to terminate, this can take about 12 minutes.
        self.start = time.time()
        while ( str(self.instance.state) != 'terminated' ):
            self.tester.debug("Waiting for instance to terminate")
            self.instance.update()
            self.tester.debug("Instance State = " + str(self.instance.state))
            self.tester.sleep(30)
            self.print_time(self.start)

        # wait terminated instance to be cleared from euca-describe-instances output.
        self.start = time.time()
        while (  str(self.tester.sys('euca-describe-instances ' + self.instanceid)) != '[]' ):
            self.tester.debug( str(self.tester.sys('euca-describe-instances ' + self.instanceid ) ) )
            self.tester.debug("Waiting terminate to clear")
            self.tester.sleep(10)
            self.print_time(self.start)

        # start the node controller
        self.eunode.start()

        # wait for instance to restore, this should not take more than 5 minutes
        self.start = time.time()
        while (  str(self.tester.sys('euca-describe-instances ' + self.instanceid)) == '[]' ):
            self.tester.debug( str(self.tester.sys('euca-describe-instances ' + self.instanceid ) ) )
            self.tester.debug("Waiting for instance to restore.")
            self.tester.sleep(10)
            self.print_time(self.start)
            elapsed = time.time() - self.start
            assert int(elapsed / 60) < 5

        print self.OK + 'Total Time' + self.ENDC
        self.print_time(self.start_total_time)

if __name__ == '__main__' :
    unittest.main()