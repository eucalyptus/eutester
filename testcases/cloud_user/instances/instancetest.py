#!/usr/bin/python
import unittest
import time
from eucaops import Eucaops
from eutester import xmlrunner
import os
import re
import random
import argparse

class InstanceBasics(unittest.TestCase):
    def setUp(self):
        # Setup basic eutester object
        eucarc_regex = re.compile("eucarc-")
        eucarc_dirs = [path for path in os.listdir(".") if eucarc_regex.search(path)]
        eucarc_path = None
        if len(eucarc_dirs) > 0:
            eucarc_path = eucarc_dirs[0]
        self.tester = Eucaops( config_file="../input/2b_tested.lst", password="foobar", credpath=eucarc_path)
        self.tester.poll_count = 80
        
        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = os.curdir + "/" + self.keypair.name + ".pem"
        self.image = self.tester.get_emi(root_device_type="instance-store")
        self.reservation = None
        self.private_addressing = False
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name

    
    def tearDown(self):
        if self.reservation is not None:
            self.assertTrue(self.tester.terminate_instances(self.reservation), "Unable to terminate instance(s)")
        self.tester.delete_group(self.group)
        self.tester.delete_keypair(self.keypair)
        os.remove(self.keypath)
        self.reservation = None
        self.group = None
        self.keypair = None
        self.tester = None
        self.ephemeral = None
        
    def create_attach_volume(self, instance, size):
            self.volume = self.tester.create_volume(instance.placement, size)
            device_path = "/dev/" + instance.block_device_prefix  +"j"
            before_attach = instance.get_dev_dir()
            try:
                self.assertTrue(self.tester.attach_volume(instance, self.volume, device_path), "Failure attaching volume")
            except AssertionError, e:
                self.assertTrue( self.tester.delete_volume(self.volume))
                return False
            after_attach = instance.get_dev_dir()
            new_devices = self.tester.diff(after_attach, before_attach)
            if len(new_devices) is 0:
                return False
            self.volume_device = "/dev/" + new_devices[0].strip()
            instance.assertFilePresent(self.volume_device)
            return True
    
    def BasicInstanceChecks(self, zone = None):
        """Instance checks including reachability and ephemeral storage"""
        if zone is None:
            zone = self.zone
        if self.reservation is None:
            self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group.name, zone=zone)
            self.tester.sleep(10)
        for instance in self.reservation.instances:
            self.assertTrue( self.tester.wait_for_reservation(self.reservation) ,'Instance did not go to running')
            self.assertNotEqual( instance.public_dns_name, instance.private_ip_address, 'Public and private IP are the same')
            self.assertTrue( self.tester.ping(instance.public_dns_name), 'Could not ping instance')
            self.assertFalse( instance.found("ls -1 " + instance.rootfs_device + "2",  "No such file or directory"),  'Did not find ephemeral storage at ' + self.ephemeral)
        return self.reservation
    
    def ElasticIps(self, zone = None):
        """ Basic test for elastic IPs
            Allocate an IP, associate it with an instance, ping the instance
            Disassociate the IP, ping the instance
            Release the address"""
        if zone is None:
            zone = self.zone
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group.name)
        self.tester.sleep(10)
        for instance in self.reservation.instances:
            address = self.tester.allocate_address()
            self.assertTrue(address,'Unable to allocate address')
            self.assertTrue(self.tester.associate_address(instance, address))
            self.tester.sleep(30)
            instance.update()
            self.assertTrue( self.tester.ping(instance.public_dns_name), "Could not ping instance with new IP")
            address.disassociate()
            self.tester.sleep(30)
            instance.update()
            self.assertTrue( self.tester.ping(instance.public_dns_name), "Could not ping instance with new IP")
            address.release()
        return self.reservation
    
    def MaxSmallInstances(self, available_small=None,zone = None):
        """Run the maximum m1.smalls available"""
        if available_small is None:
            available_small = self.tester.get_available_vms()
        if zone is None:
            zone = self.zone
        self.reservation = self.tester.run_instance(self.image,keypair=self.keypair.name, group=self.group.name,min=available_small, max=available_small, zone=zone)
        self.assertTrue( self.tester.wait_for_reservation(self.reservation) ,'Not all instances  went to running')
        return self.reservation
    
    def LargestInstance(self, zone = None): 
        """Run 1 of the largest instance c1.xlarge"""
        if zone is None:
            zone = self.zone
        self.reservation = self.tester.run_instance(self.image,keypair=self.keypair.name, group=self.group.name,type="c1.xlarge")
        self.assertTrue( self.tester.wait_for_reservation(self.reservation) ,'Not all instances  went to running')
        return self.reservation
    
    def MetaData(self, zone=None):
        """Check metadata for consistency"""
        # Missing nodes
        # ['block-device-mapping/',  'ami-manifest-path' , 'hostname',  'placement/']
        if zone is None:
            zone = self.zone
        self.reservation = self.tester.run_instance(self.image,keypair=self.keypair.name, group=self.group.name, zone=zone)
        for instance in self.reservation.instances:
            ## Need to verify  the public key (could just be checking for a string of a certain length)
            #self.assertTrue(re.search(instance_ssh.get_metadata("public-keys/0/")[0], self.keypair.name), 'Incorrect public key in metadata')
            self.assertTrue(re.search(instance.get_metadata("security-groups")[0], self.group.name), 'Incorrect security group in metadata') 
            # Need to validate block device mapping
            #self.assertTrue(re.search(instance_ssh.get_metadata("block-device-mapping/")[0], "")) 
            self.assertTrue(re.search(instance.get_metadata("instance-id")[0], instance.id), 'Incorrect instance id in metadata')  
            self.assertTrue(re.search(instance.get_metadata("local-ipv4")[0] , instance.private_ip_address), 'Incorrect private ip in metadata')
            self.assertTrue(re.search(instance.get_metadata("public-ipv4")[0] , instance.ip_address), 'Incorrect public ip in metadata')          
            self.assertTrue(re.search(instance.get_metadata("ami-id")[0], instance.image_id), 'Incorrect ami id in metadata')
            self.assertTrue(re.search(instance.get_metadata("ami-launch-index")[0], instance.ami_launch_index), 'Incorrect launch index in metadata')
            self.assertTrue(re.search(instance.get_metadata("reservation-id")[0], self.reservation.id), 'Incorrect reservation in metadata')
            self.assertTrue(re.search(instance.get_metadata("kernel-id")[0], instance.kernel),  'Incorrect kernel id in metadata')
            self.assertTrue(re.search(instance.get_metadata("public-hostname")[0], instance.public_dns_name), 'Incorrect public host name in metadata')
            self.assertTrue(re.search(instance.get_metadata("ramdisk-id")[0], instance.ramdisk ), 'Incorrect ramdisk in metadata') #instance-type
            self.assertTrue(re.search(instance.get_metadata("instance-type")[0], instance.instance_type ), 'Incorrect instance type in metadata')
            BAD_META_DATA_KEYS = ['foobar']
            for key in BAD_META_DATA_KEYS:
                self.assertTrue(re.search("Not Found", "".join(instance.get_metadata(key))), 'No fail message on invalid meta-data node')
        return self.reservation
           
    def Reboot(self, zone=None):
        """Reboot instance ensure IP connectivity and volumes stay attached"""
        if zone is None:
            zone = self.zone
        self.reservation = self.tester.run_instance(self.image, keypair=self.keypair.name, group=self.group.name, zone=zone)
        self.tester.sleep(10)
        for instance in self.reservation.instances:
            ### Create 1GB volume in first AZ
            self.assertTrue(self.create_attach_volume(instance, 1), "Was not able to attach volume")
            ### Reboot instance
            instance.reboot()
            self.tester.sleep(30) 
            self.tester.debug("Restarting SSH session to instance")
            instance.reset_ssh_connection()
            ### Check for device in instance
            ### Make sure volume is still attached after reboot
            if self.volume_device is None:
                 self.assertTrue(False, "Failed to find volume on instance")
            instance.assertFilePresent(self.volume_device) 
            self.assertTrue(self.tester.detach_volume(self.volume), "Unable to detach volume")
            self.assertTrue(self.tester.delete_volume(self.volume), "Unable to delete volume")
        return self.reservation
    
    def Churn(self, testcase="BasicInstanceChecks"):
        """Start instances and stop them before they are running, increase time to terminate on each iteration"""
        from multiprocessing import Process
        from multiprocessing import Queue
        ### Increase time to terminate by step seconds on each iteration
        step = 10
        
        ## Run through count iterations of test
        count = self.tester.get_available_vms("m1.small") / 2
        thread_pool = []
        queue_pool = []
        
        ## Start asynchronous activity
        ## Run 5 basic instance check instances 10s apart
        for i in xrange(count):
            q = Queue()
            queue_pool.append(q)
            p = Process(target=self.run_testcase_thread, args=(q, step * i,testcase))
            thread_pool.append(p)
            self.tester.debug("Starting Thread " + str(i) +" in " + str(step * i))
            p.start()
        
        ### While the other tests are running, run and terminate count instances with a 10s sleep in between
        for i in xrange(count):
            self.reservation = self.image.run()
            self.tester.debug("Sleeping for " + str(step) + " seconds before terminating instances")
            self.tester.sleep(step )
            for instance in self.reservation.instances:
                instance.terminate()
                self.assertTrue(self.tester.wait_for_instance(instance, "terminated"), "Instance did not go to terminated")
        
        ### Once the previous test is complete rerun the BasicInstanceChecks test case
        q = Queue()
        queue_pool.append(q)
        p = Process(target=self.run_testcase_thread, args=(q, step * i,"BasicInstanceChecks"))
        thread_pool.append(p)
        p.start()
        
        fail_count = 0
        ### Block until the script returns a result
        for queue in queue_pool:
            test_result = queue.get(True)
            self.tester.debug("Got Result: " + str(test_result) )
            fail_count += test_result

        for thread in thread_pool:
            thread.join()
        
        self.assertEquals(fail_count, 0, "Failure detected in one of the " + str(count)  + " Basic Instance tests")

    def PrivateIPAddressing(self, zone = None):
        """Basic test to run an instance with Private only IP
           and later allocate/associate/diassociate/release 
           an Elastic IP. In the process check after diassociate
           the instance has only got private IP or new Public IP
           gets associated to it"""
        self.private_addressing = True
        if zone is None:
            zone = self.zone
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group.name, private_addressing=self.private_addressing, zone=zone)
        self.tester.sleep(10)
        for instance in self.reservation.instances:
            address = self.tester.allocate_address()
            self.assertTrue(address,'Unable to allocate address')
            self.assertTrue(self.tester.associate_address(instance, address))
            self.tester.sleep(30)
            instance.update()
            self.assertTrue( self.tester.ping(instance.public_dns_name), "Could not ping instance with new IP")
            address.disassociate()
            self.tester.sleep(30)
            instance.update()
            self.assertTrue( self.tester.ping(instance.public_dns_name), "Could not ping instance with new IP")
            address.release()
            if (instance.public_dns_name != instance.private_dns_name):
                self.tester.critical("Instance received a new public IP: " + instance.public_dns_name)
        return self.reservation
    
    def ReuseAddresses(self, zone = None):
        """ Run instances in series and ensure they get the same address"""
        prev_address = None
        if zone is None:
            zone = self.zone
        ### Run the test 5 times in a row
        for i in xrange(5):
            self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group.name, zone=zone)
            for instance in self.reservation.instances:
                if prev_address is not None:
                    self.assertTrue(re.search(str(prev_address) ,str(instance.public_dns_name)), str(prev_address) +" Address did not get reused but rather  " + str(instance.public_dns_name))
                prev_address = instance.public_dns_name
            self.tester.terminate_instances(self.reservation)
            
    def run_testcase_thread(self, queue,delay = 20, name="MetaData"):
        ### Thread that runs a testcase (function) and returns its pass or fail result
        self.tester.sleep(delay)
        try:
            result = unittest.TextTestRunner(verbosity=2).run(InstanceBasics(name))
        except Exception, e:
            queue.put(1)
            raise e
        if result.wasSuccessful():
            self.tester.debug("Passed test: " + name)
            queue.put(0)
            return False
        else:
            self.tester.debug("Failed test: " + name)
            queue.put(1)
            return True
    
if __name__ == "__main__":
    ## If given command line arguments, use them as test names to launch
    parser = argparse.ArgumentParser(description='Parse test suite arguments.')
    parser.add_argument('--xml', action="store_true", default=False)
    parser.add_argument('--tests', nargs='+', default= ["BasicInstanceChecks","ElasticIps","PrivateIPAddressing","MaxSmallInstances","LargestInstance","MetaData","Reboot", "Churn"])
    args = parser.parse_args()
    for test in args.tests:
        if args.xml:
            try:
                os.mkdir("results")
            except OSError:
                pass
            file = open("results/test-" + test + "result.xml", "w")
            result = xmlrunner.XMLTestRunner(file).run(InstanceBasics(test))
            file.close()
        else:
            result = unittest.TextTestRunner(verbosity=2).run(InstanceBasics(test))
        if result.wasSuccessful():
            pass
        else:
            exit(1)
            
