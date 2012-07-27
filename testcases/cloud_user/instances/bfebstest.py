#!/usr/bin/python
import unittest
import re
import os
import sys
import argparse
from instancetest import InstanceBasics
from eucaops import Eucaops
from eutester import xmlrunner

arg_credpath = None
arg_imgurl = None

class BFEBSBasics(InstanceBasics):
    def setUp(self, credpath=None):
        if credpath is None:
            credpath = arg_credpath
        super(BFEBSBasics, self).setUp(credpath)
        
    def RegisterImage(self, bfebs_img_url = None, zone= None):
        '''Register a BFEBS snapshot'''
        if zone is None:
            zone = self.zone
        if bfebs_img_url is None:
            if arg_imgurl is not None:
                bfebs_img_url = arg_imgurl
            else:
                raise Exception("No image url provided when attempting to register a BFEBS image")
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group.name, zone=zone)
        for instance in self.reservation.instances:
            self.assertTrue(self.create_attach_volume(instance, 2)) 
            instance.sys("curl " + bfebs_img_url + " > " + self.volume_device, timeout=800)
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
        self.reservation = self.tester.run_instance(self.image,keypair=self.keypair.name, group=self.group.name, zone=zone)
        self.assertTrue(self.tester.stop_instances(self.reservation))
        self.assertFalse( self.tester.ping(self.reservation.instances[0].public_dns_name, poll_count=2), 'Was able to ping stopped instance')
        self.assertTrue(self.tester.start_instances(self.reservation))
        self.tester.debug("Waiting 20s for instance to boot") 
        self.tester.sleep(20)
        self.assertTrue( self.tester.ping(self.reservation.instances[0].public_dns_name,  poll_count=2), 'Could not ping instance')
        
    def MultipleBFEBSInstances(self):
        """Run half of the available m1.small instances with a BFEBS image"""
        self.image = self.tester.get_emi(root_device_type="ebs")
        self.MaxSmallInstances(self.tester.get_available_vms() / 2) 
            
    def ChurnBFEBS(self):
        """Start instances and stop them before they are running, increase time to terminate on each iteration"""
        self.image = self.tester.get_emi(root_device_type="ebs")
        self.Churn()
   
    def StaggeredInstances(self):
        '''Run a few instances concurrently'''
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
    ## If given command line arguments, use them as test names to launch
    parser = argparse.ArgumentParser(description='Parse test suite arguments.')
    parser.add_argument('--credpath', default=".eucarc")
    parser.add_argument('--xml', action="store_true", default=False)
    parser.add_argument('--tests', nargs='+', default= ["RegisterImage","LaunchImage", "StopStart","MultipleBFEBSInstances","ChurnBFEBS"])
    parser.add_argument('--imgurl')
    args = parser.parse_args()
    arg_credpath = args.credpath
    arg_imgurl = args.imgurl
    for test in args.tests:
        if args.xml:
            try:
                os.mkdir("results")
            except OSError:
                pass
            file = open("results/test-" + test + "result.xml", "w")
            result = xmlrunner.XMLTestRunner(file).run(BFEBSBasics(test))
            file.close()
        else:
            result = unittest.TextTestRunner(verbosity=2).run(BFEBSBasics(test))
        if result.wasSuccessful():
            pass
        else:
            exit(1)
            
        