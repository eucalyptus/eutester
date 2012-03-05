#! ../share/python_lib/vic-dev-27/bin/python
import unittest
import time
from eucaops import Eucaops
import os
import re

class Instances(unittest.TestCase):
    def setUp(self):
        # Setup basic eutester object
        
        self.tester = Eucaops( config_file="../input/2b_tested.lst", password="foobar", credpath="../credentials")
        self.tester.poll_count = 240
        self.tester.start_euca_logs()
        
        ### Determine whether virtio drivers are being used
        self.device_prefix = "sd"
        if self.tester.hypervisor == "kvm":
            self.device_prefix = "vd"
        self.ephemeral = "/dev/" + self.device_prefix + "a2"
        
        ### Adda and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = os.curdir + "/" + self.keypair.name + ".pem"
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group.name)
        self.tester.sleep(10)
    
    def tearDown(self):
        """Stop Euca logs""" 
        self.assertTrue(self.tester.terminate_instances(self.reservation), "Unable to terminate instance(s)")
        self.tester.delete_group(self.group)
        self.tester.delete_keypair(self.keypair)
        os.remove(self.keypath)
        self.tester.stop_euca_logs()
        self.tester.save_euca_logs()
        self.reservation = None
        self.group = None
        self.keypair = None
        self.tester = None
        self.ephemeral = None
    
    def test1_Instance(self):
        """Instance checks including reachability and ephemeral storage"""
        for instance in self.reservation.instances:
            self.assertTrue( self.tester.wait_for_reservation(self.reservation) ,'Instance did not go to running')
            self.assertNotEqual( instance.public_dns_name, instance.private_ip_address, 'Public and private IP are the same')
            self.assertTrue( self.tester.ping(instance.public_dns_name), 'Could not ping instance')
            instance_ssh = Eucaops( hostname=instance.public_dns_name,  keypath= self.keypath)
            self.assertTrue( instance_ssh.found("ls -1 " + self.ephemeral,  self.ephemeral),  'Did not find ephemeral storage at ' + self.ephemeral)
            self.assertTrue( self.tester.terminate_instances(self.reservation), 'Failure when terminating instance')
    
    def test2_ElasticIps(self):
        """ Basic test for elastic IPs"""
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
            self.tester.release_address()
    
    def test3_MaxInstances(self):
        """Run the maximum m1.smalls available"""
        self.assertTrue(self.tester.terminate_instances(self.reservation), "Was not able to terminate original instance")
        available_small = self.tester.get_available_vms()
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group.name,min=available_small, max=available_small)
        self.assertTrue( self.tester.wait_for_reservation(self.reservation) ,'Not all instances  went to running')
    
    def test4_LargeInstance(self):
        """Run 1 of the largest instance c1.xlarge"""
        self.assertTrue(self.tester.terminate_instances(self.reservation), "Was not able to terminate original instance")
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group.name,type="c1.xlarge")
        self.assertTrue( self.tester.wait_for_reservation(self.reservation) ,'Not all instances  went to running')
    
    def test5_MetaData(self):
        """Check metadata for consistency"""
        # Missing nodes
        # ['block-device-mapping/',  'ami-manifest-path' , 'hostname',  'placement/']   
        for instance in self.reservation.instances:
            instance_ssh = Eucaops( hostname=instance.public_dns_name,  keypath= self.keypath)
            ### Check metadata service
            self.assertTrue(re.search(instance_ssh.get_metadata("public-keys/0/")[0], self.keypair.name))
            self.assertTrue(re.search(instance_ssh.get_metadata("security-groups")[0], self.group)) 
            #self.assertTrue(re.search(instance_ssh.get_metadata("block-device-mapping/")[0], "")) 
            self.assertTrue(re.search(instance_ssh.get_metadata("instance-id")[0], instance.id))  
            self.assertTrue(re.search(instance_ssh.get_metadata("local-ipv4")[0] , instance.private_ip_address))
            self.assertTrue(re.search(instance_ssh.get_metadata("public-ipv4")[0] , instance.ip_address))          
            self.assertTrue(re.search(instance_ssh.get_metadata("ami-id")[0], instance.image_id))
            self.assertTrue(re.search(instance_ssh.get_metadata("ami-launch-index")[0], instance.ami_launch_index))
            self.assertTrue(re.search(instance_ssh.get_metadata("reservation-id")[0], self.reservation.id))
            self.assertTrue(re.search(instance_ssh.get_metadata("kernel-id")[0], instance.kernel))
            self.assertTrue(re.search(instance_ssh.get_metadata("public-hostname")[0], instance.public_dns_name))
            self.assertTrue(re.search(instance_ssh.get_metadata("ramdisk-id")[0], instance.ramdisk )) #instance-type
            self.assertTrue(re.search(instance_ssh.get_metadata("instance-type")[0], instance.instance_type ))
           
    def test6_Reboot(self):
        """Reboot instance ensure IP connectivity and volumes stay attached"""
        for instance in self.reservation.instances:
            ### Create 1GB volume in first AZ
            volume = self.tester.create_volume(self.tester.ec2.get_all_zones()[0].name)
            
            ### Pass in check the devices on the instance before the attachment
            device_path = "/dev/" + self.device_prefix  +"j"
            instance_ssh = Eucaops( hostname=instance.public_dns_name,  keypath= self.keypath)
            before_attach = instance_ssh.sys("ls -1 /dev/ | grep " + self.device_prefix)
            
            ### Attach the volume to the instance
            self.assertTrue(self.tester.attach_volume(instance, volume, device_path), "Failure attaching volume")
            
            ### Check devices after attachment
            after_attach = instance_ssh.sys("ls -1 /dev/ | grep " + self.device_prefix)
            new_devices = self.tester.diff(after_attach, before_attach)
            
            ### Check for device in instance
            self.assertTrue(instance_ssh.check_device("/dev/" + new_devices[0]), "Did not find device on instance before reboot")
            
            ### Reboot instance
            instance.reboot()
            self.tester.sleep(30)
            
            ### Check for device in instance
            instance_ssh = Eucaops( hostname=instance.public_dns_name,  keypath= self.keypath)
            self.assertTrue(instance_ssh.check_device("/dev/" + new_devices[0]), "Did not find device on instance after reboot")
            self.assertTrue(self.tester.detach_volume(volume), "Unable to detach volume")
            self.assertTrue(self.tester.delete_volume(volume), "Unable to delete volume")
        
    def suite():
        tests = ['test1_Instance', 'test2_ElasticIps', 'test3_MaxInstances', 'test4_LargeInstance','test5_MetaData', 'test6_Reboot']
        return unittest.TestSuite(map(Instances, tests))
    
if __name__ == "__main__":
   unittest.main()