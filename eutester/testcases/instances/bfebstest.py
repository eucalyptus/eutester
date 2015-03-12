#!/usr/bin/python
import time
from instancetest import InstanceBasics
from eutester.aws.ec2.euinstance import EuInstance

class BFEBSBasics(InstanceBasics):
    def __init__(self, name="BFEBSBasics", credpath=None, region=None, config_file=None,
                 password=None, emi=None, zone=None, user_data=None, instance_user=None,
                 imgurl=None, **kwargs ):
        self.name = name
        self.imgurl = imgurl
        self.setup_parser(description="Test the Eucalyptus EC2 BFEBS image functionality.")
        self.parser.add_argument('--imgurl',
                                 help="BFEBS Image to splat down", default=None)
        self.root_volume_path = '/dev/sda'
        self.test_volume_1_path = '/dev/sde'
        self.test_volume_2_path = '/dev/sdf'
        self.volume_1 = None
        self.volume_2 = None
        super(BFEBSBasics, self).__init__(name=name, credpath=credpath, region=region,
                                          config_file=config_file, password=password,
                                          emi=emi, zone=zone, user_data=user_data,
                                          instance_user=instance_user, **kwargs)

    def clean_method(self):
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
        if self.volume:
            self.tester.delete_volume(self.volume)
        if self.volume_1:
            self.tester.delete_volume(self.volume_1)
        if self.volume_2:
            self.tester.delete_volume(self.volume_2)

    def RegisterImage(self):
        '''Register a BFEBS snapshot'''
        if not self.imgurl:
            raise Exception("No imgurl passed to run BFEBS tests")
        if not self.reservation:
            self.run_instance_params['image'] = self.tester.get_emi(root_device_type="instance-store",
                                                                    basic_image=True)
            self.reservation = self.tester.run_image(**self.run_instance_params)
        for instance in self.reservation.instances:
            self.volume_1 = self.tester.create_volume(zone=self.zone, size=3)
            self.volume_device = instance.attach_volume(self.volume_1)
            instance.sys("curl " +  self.imgurl + " > " + self.volume_device, timeout=800, code=0)
            snapshot = self.tester.create_snapshot(self.volume_1.id)
            image_id = self.tester.register_snapshot(snapshot)
        self.run_instance_params['image'] = self.tester.get_emi(image_id)
        self.tester.terminate_instances(self.reservation)
        self.reservation = None

    def StopStart(self, zone = None):
        '''Launch a BFEBS instance, stop it then start it again'''
        if zone is None:
            zone = self.zone
        self.RunStop(zone)
        self.DetachAttachRoot(zone)
        self.StartTerminate(zone)


    def MultipleBFEBSInstances(self):
        """Run half of the available m1.small instances with a BFEBS image"""
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
        self.image = self.tester.get_emi(emi=self.args.emi,
                                         root_device_type="ebs",
                                         basic_image=True)
        self.MultipleInstances()

    def ChurnBFEBS(self):
        """Start instances and stop them before they are running, increase time to terminate on each iteration"""
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
        self.image = self.tester.get_emi(emi=self.args.emi,
                                         root_device_type="ebs",
                                         basic_image=True)
        self.Churn()

    def RunStop(self, zone=None):
        """Run instance then stop them without starting them again"""
        if zone is None:
            zone = self.zone
        try:
            self.run_instance_params['image'] = self.tester.get_emi(emi=self.args.emi,
                                                                    root_device_type="ebs",
                                                                    basic_image=True)
        except Exception, e:
            self.RegisterImage()
            self.run_instance_params['image'] = self.tester.get_emi(emi=self.args.emi,
                                                                    root_device_type="ebs",
                                                                    basic_image=True)
        if not self.volume_1:
            self.volume_1 = self.tester.create_volume(zone=self.zone, size=2)
        if not self.volume_2:
            self.volume_2 = self.tester.create_volume(zone=self.zone, size=1)

        if self.reservation:
            self.tester.terminate_instances(self.reservation)
        self.reservation = self.tester.run_image(**self.run_instance_params)
        ## Ensure that we can attach and use a volume
        for instance in self.reservation.instances:
            instance.attach_volume(self.volume_1, self.test_volume_1_path)
            instance.attach_volume(self.volume_2, self.test_volume_2_path)
        self.tester.stop_instances(self.reservation)
        for instance in self.reservation.instances:
            if instance.ip_address or instance.private_ip_address:
                raise Exception("Instance had a public " + str(instance.ip_address) + " private " + str(instance.private_ip_address) )
            if instance.block_device_mapping[self.test_volume_1_path] is None:
                raise Exception("DBM path is invalid")
            if self.volume_1.id != instance.block_device_mapping[self.test_volume_1_path].volume_id:
                raise Exception("Volume id does not match")

    def DetachAttachRoot(self, zone = None):
        """Detach and attach root for stopped instances"""
        instances = self.tester.get_instances(state="stopped",zone=zone)
        if len(instances) == 0:
            raise Exception("Did not find any stopped instances"
                            " to detach/attach root")
        for instance in instances:
            self.assertTrue(3 == len(instance.block_device_mapping),
                             "Did not find three BDM for the instance")
            root_vol_id = instance.block_device_mapping[self.root_volume_path].volume_id
            self.detachVolumeByPath(instance, self.root_volume_path)
            self.detachVolumeByPath(instance, self.test_volume_1_path)
            instances = self.tester.get_instances(idstring=instance.id)
            if len(instances) != 1:
                raise Exception("Could not find the instance")
            instance = instances[0]
            root_volume = self.tester.get_volumes(volume_id=root_vol_id)[0]
            self.volume = root_volume
            self.tester.attach_volume(instance, root_volume, self.root_volume_path)

    def StartTerminate(self, zone = None):
        instances = self.tester.get_instances(state="stopped",zone=zone)
        if len(instances) == 0:
            raise Exception("Did not find any stopped instances to start and terminate")
        for instance in instances:
            self.assertTrue(self.tester.start_instances(instances))
            # check that the volume 2 can be detached after instance re-start
            self.detachVolumeByPath(instance, self.test_volume_2_path)
            if self.keypair.name == instance.key_name:
                instance = self.tester.convert_instance_to_euisntance(instance, keypair=self.keypair)
                instance.sys("uname -r", code=0)
            else:
                self.assertTrue(self.tester.ping(instance.ip_address))


    def CreateImage(self,zone=None):
        if zone is None:
            zone = self.zone
        try:
            self.run_instance_params['image'] = self.tester.get_emi(emi=self.args.emi,
                                                                    root_device_type="ebs",
                                                                    basic_image=True)
        except Exception, e:
            self.RegisterImage()
            self.run_instance_params['image'] = self.tester.get_emi(emi=self.args.emi,
                                                                    root_device_type="ebs",
                                                                    basic_image=True)
        if not self.reservation:
            self.reservation = self.tester.run_image(**self.run_instance_params)

        ### Run with reboot
        original_image = self.run_instance_params['image']
        for instance in self.reservation.instances:
            assert isinstance(instance, EuInstance)
            self.tester.sleep(60)
            starting_uptime = instance.get_uptime()
            ## Drop a file so we know if we actually created an image
            current_time = str(int(time.time()))
            temp_file = "/root/my-new-file-" + current_time
            instance.sys("touch " + temp_file + " && sync", code=0)
            instance.sys('ls -la', code=0)
            rebooted_image = self.tester.create_image(instance, "BFEBS-test-create-image-reboot-" + current_time)
            instance.connect_to_instance()
            ending_uptime = instance.get_uptime()
            if ending_uptime > starting_uptime:
                raise Exception("Instance did not get stopped then started")
            self.run_instance_params['image'] = rebooted_image
            new_image_reservation = self.tester.run_image(**self.run_instance_params)
            for new_instance in new_image_reservation.instances:
                ## Check that our temp file exists
                new_instance.sys("ls -la")
                new_instance.sys("ls " + temp_file, code=0)
            self.tester.terminate_instances(new_image_reservation)

        ### Run without reboot
        self.run_instance_params['image'] = original_image
        for instance in self.reservation.instances:
            assert isinstance(instance, EuInstance)
            self.tester.sleep(60)
            starting_uptime = instance.get_uptime()
            ## Drop a file so we know if we actually created an image
            current_time = str(int(time.time()))
            temp_file = "/root/my-new-file-" + current_time
            instance.sys("touch " + temp_file + " && sync", code=0)
            instance.sys('ls -la', code=0)
            not_rebooted_image = self.tester.create_image(instance, "BFEBS-test-create-image-noreboot-" + current_time, no_reboot=True)
            ending_uptime = instance.get_uptime()
            if ending_uptime < starting_uptime:
                raise Exception("Instance did get stopped then started when it shouldn't have")
            self.run_instance_params['image'] = not_rebooted_image
            new_image_reservation = self.tester.run_image(**self.run_instance_params)
            for new_instance in new_image_reservation.instances:
                ## Check that our temp file exists
                new_instance.sys("ls -la")
                new_instance.sys("ls " + temp_file, code=0)
            self.tester.terminate_instances(new_image_reservation)

    def detachVolumeByPath(self, instance, path):
        vol_id = instance.block_device_mapping[path].volume_id
        vol_to_detach = self.tester.get_volumes(volume_id=vol_id)[0]
        self.tester.detach_volume(vol_to_detach)


if __name__ == "__main__":
    testcase = BFEBSBasics()
    bfebstestsuite = testcase.do_with_args(BFEBSBasics)

    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or ["RegisterImage",  "StopStart", "MultipleBFEBSInstances"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = []
    for test in list:
        test = getattr(bfebstestsuite,test)
        unit_list.append(testcase.create_testunit_from_method(test))
    testcase.clean_method = bfebstestsuite.clean_method
    result = testcase.run_test_case_list(unit_list)
    exit(result)