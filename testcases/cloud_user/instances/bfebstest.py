#!/usr/bin/python
from Queue import Queue
import unittest
import re
from eutester.euinstance import EuInstance
from eutester.eutestcase import EutesterTestCase
from instancetest import InstanceBasics

class BFEBSBasics(InstanceBasics):
    def __init__(self, credpath=None, imgurl= None):
        super(BFEBSBasics, self).__init__(credpath)
        self.add_arg("imgurl", imgurl)

    def RegisterImage(self, zone= None):
        '''Register a BFEBS snapshot'''
        if zone is None:
            zone = self.zone
        if not self.args.imgurl:
            raise Exception("No imgurl passed to run BFEBS tests")
        if not self.reservation:
            self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group.name, zone=zone)
        for instance in self.reservation.instances:
            assert isinstance(instance, EuInstance)
            self.volume = self.tester.create_volume(azone=self.zone, size=2)
            self.volume_device = instance.attach_volume(self.volume)
            instance.sys("curl " +  self.args.imgurl + " > " + self.volume_device, timeout=800)
            snapshot = self.tester.create_snapshot(self.volume.id, waitOnProgress=10)
            self.assertTrue( re.search("completed", snapshot.status), "Snapshot did not complete"  )
            image_id = self.tester.register_snapshot(snapshot)
        self.image = self.tester.get_emi(image_id)

    def LaunchImage(self, zone= None):
        '''Launch a BFEBS image'''
        if zone is None:
            zone = self.zone
        self.image = self.tester.get_emi(root_device_type="ebs")
        self.reservation = self.tester.run_instance(self.image,keypair=self.keypair.name, group=self.group.name, zone=zone)
        self.assertTrue( self.tester.ping(self.reservation.instances[0].public_dns_name), 'Could not ping instance')

    def StopStart(self, zone = None):
        '''Launch a BFEBS instance, stop it then start it again'''
        if zone is None:
            zone = self.zone
        self.image = self.tester.get_emi(root_device_type="ebs")
        if not self.reservation:
            self.reservation = self.tester.run_instance(self.image,keypair=self.keypair.name, group=self.group.name, zone=zone)
        self.assertTrue(self.tester.stop_instances(self.reservation))
        self.assertFalse( self.tester.ping(self.reservation.instances[0].public_dns_name, poll_count=2), 'Was able to ping stopped instance')
        self.assertTrue(self.tester.start_instances(self.reservation))
        self.tester.debug("Waiting 20s for instance to boot") 
        self.tester.sleep(20)
        self.assertTrue( self.tester.ping(self.reservation.instances[0].public_dns_name,  poll_count=2), 'Could not ping instance')

    def MultipleBFEBSInstances(self):
        """Run half of the available m1.small instances with a BFEBS image"""
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
        self.image = self.tester.get_emi(root_device_type="ebs")
        self.MaxSmallInstances(self.tester.get_available_vms() / 2) 

    def ChurnBFEBS(self):
        """Start instances and stop them before they are running, increase time to terminate on each iteration"""
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
        self.image = self.tester.get_emi(root_device_type="ebs")
        self.Churn()

    def StaggeredInstances(self):
        '''Run a few instances concurrently'''
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
        from multiprocessing import Process
        self.failure = 0
        thread_pool = []
        queue_pool = []
        total = self.tester.get_available_vms() / 2
        for i in xrange(total):
            q = Queue()
            p = Process(target=self.run_testcase, args=(q))
            thread_pool.append(p)
            self.tester.debug("Starting Thread " + str(i))
            p.start()
            self.tester.sleep(2)
        for thread in thread_pool:
            thread.join()
        self.assertEqual(self.failure, 0, str(self.failure) + " Tests failed out of " + str(total))
        self.failure = 0

    def AddressIssue(self, zone = None):
        if zone is None:
            zone = self.zone
        if not self.reservation:
            self.reservation = self.tester.run_instance(self.image,keypair=self.keypair.name, group=self.group.name, zone=zone)
        original_ip = ""
        for instance in self.reservation.instances:
            original_ip = instance.ip_address
            self.tester.debug("Terminating instance " + str(instance))
            instance.terminate()
        self.tester.sleep(1)
        self.BasicInstanceChecks()

    def run_testcase(self, queue,delay = 20, testcase="LaunchImage"):
        self.tester.sleep(delay)
        try:
            result = unittest.TextTestRunner(verbosity=2).run(BFEBSBasics(testcase))
        except Exception, e:
            queue.put(1)
            raise e
        if result.wasSuccessful():
            self.tester.debug("Passed test: " + testcase)
            queue.put(0)
        else:
            self.tester.debug("Failed test: " + testcase)
            queue.put(1)

if __name__ == "__main__":
    testcase = EutesterTestCase()

    #### Adds argparse to testcase and adds some defaults args
    testcase.setup_parser()

    ### Get all cli arguments and any config arguments and merge them
    testcase.get_args()

    ### Instantiate an object of your test suite class using args found from above
    bfebs_basic_tests = testcase.do_with_args(BFEBSBasics)

    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or [ "RegisterImage",  "LaunchImage", "StopStart" , "MultipleBFEBSInstances",
                                    "ChurnBFEBS", "StaggeredInstances"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( bfebs_basic_tests.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    testcase.run_test_case_list(unit_list)
    bfebs_basic_tests.clean_method()

