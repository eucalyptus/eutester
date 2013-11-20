'''
Created on = '11/15/13"
Author = 'mmunn'

Unit test          : EUCA-6429 DNS TCP handler should have read timeout
setUp              : Install Credentials,
test               : use "nc" to open a TCP connection to the DNS service and and check for timeout
                     the TCP socket should timeout before the ssh timeout.
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
import time
from eucaops import Eucaops


class EucaTest(unittest.TestCase):
    def setUp(self):
        self.conf = "cloud.conf"
        self.tester = Eucaops(config_file=self.conf, password="foobar")
        self.doAuth()
        self.OK = '\033[1m\033[37m\033[42m'
        self.ENDC = '\033[0m'

    def tearDown(self):
        self.tester.modify_property('dns.tcp.timeout_seconds' , '30' )
        self.tester.cleanup_artifacts()
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem")
        shutil.rmtree(self.tester.credpath)

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
        # Set the timeout the default is 30
        self.tester.modify_property('dns.tcp.timeout_seconds' , '10' )
        self.start = time.time()
        # The DNS TCP HANDLER should timeout before the ssh timeout=120
        self.tester.sys("nc -w 120 " + str(self.tester.clc.hostname) + " 53",timeout=120)
        self.print_time(self.start)


if __name__ == "__main__":
    unittest.main()