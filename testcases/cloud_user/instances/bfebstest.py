#!/usr/bin/python
import time
from eutester.eutestcase import EutesterTestCase
from instancetest import InstanceBasics
from eutester.euinstance import EuInstance

class BFEBSBasics(InstanceBasics):
    def __init__(self, name="BFEBSBasics", credpath=None, region=None, config_file=None, password=None, emi=None, zone=None,
                  user_data=None, instance_user=None, imgurl=None ):
        self.imgurl = imgurl
        super(BFEBSBasics, self).__init__(name=name, credpath=credpath, region=region, config_file=config_file, password=password,
                                          emi=emi, zone=zone, user_data=user_data, instance_user=instance_user)

    def clean_method(self):
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
        if self.volume:
            self.tester.delete_volume(self.volume)

    def RegisterImage(self):
        '''Register a BFEBS snapshot'''
        if not self.imgurl:
            raise Exception("No imgurl passed to run BFEBS tests")
        if not self.reservation:
            self.run_instance_params['image'] = self.tester.get_emi(root_device_type="instance-store",
                                                                    not_platform="windows")
            self.reservation = self.tester.run_instance(**self.run_instance_params)
        for instance in self.reservation.instances:
            self.volume = self.tester.create_volume(zone=self.zone, size=3)
            self.volume_device = instance.attach_volume(self.volume)
            instance.sys("curl " +  self.imgurl + " > " + self.volume_device, timeout=800, code=0)
            snapshot = self.tester.create_snapshot(self.volume.id)
            image_id = self.tester.register_snapshot(snapshot)
        self.run_instance_params['image'] = self.tester.get_emi(image_id)
        self.tester.terminate_instances(self.reservation)
        self.reservation = None

    def StopStart(self, zone = None):
        '''Launch a BFEBS instance, stop it then start it again'''
        if zone is None:
            zone = self.zone
        self.RunStop(zone)
        self.StartTerminate(zone)


    def MultipleBFEBSInstances(self):
        """Run half of the available m1.small instances with a BFEBS image"""
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
        self.image = self.tester.get_emi(root_device_type="ebs")
        self.MultipleInstances()

    def ChurnBFEBS(self):
        """Start instances and stop them before they are running, increase time to terminate on each iteration"""
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
        self.image = self.tester.get_emi(root_device_type="ebs")
        self.Churn()

    def RunStop(self, zone=None):
        """Run instance then stop them without starting them again"""
        if zone is None:
            zone = self.zone
        try:
            self.run_instance_params['image'] = self.tester.get_emi(root_device_type="ebs")
        except Exception,e:
            self.RegisterImage()
            self.run_instance_params['image'] = self.tester.get_emi(root_device_type="ebs")
        if not self.volume:
            self.volume = self.tester.create_volume(zone=self.zone, size=2)
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
        self.reservation = self.tester.run_instance(**self.run_instance_params)
        ## Ensure that we can attach and use a volume
        for instance in self.reservation.instances:
            vol_dev = instance.attach_volume(self.volume)
        self.tester.stop_instances(self.reservation)
        for instance in self.reservation.instances:
            if instance.ip_address or instance.private_ip_address:
                raise Exception("Instance had a public " + str(instance.ip_address) + " private " + str(instance.private_ip_address) )
        self.reservation = None

    def StartTerminate(self, zone = None):
        instances = self.tester.get_instances(state="stopped",zone=zone)
        if len(instances) == 0:
            raise Exception("Did not find any stopped instances to start and terminate")
        try:
            for instance in instances:
                self.assertTrue(self.tester.start_instances(instances))
                if self.keypair.name == instance.key_name:
                    instance = self.tester.convert_instance_to_euisntance(instance, keypair=self.keypair)
                    instance.sys("uname -r", code=0)
                else:
                    self.assertTrue(self.tester.ping(instance.ip_address))
        finally:
            self.tester.terminate_instances(instances)
            if self.volume:
                self.tester.wait_for_volume(self.volume, status="available")
                self.tester.delete_volume(self.volume)
                self.volume = None

    def CreateImage(self,zone=None):
        if zone is None:
            zone = self.zone
        try:
            self.run_instance_params['image'] = self.tester.get_emi(root_device_type="ebs")
        except Exception, e:
            self.RegisterImage()
            self.run_instance_params['image'] = self.tester.get_emi(root_device_type="ebs")
        if not self.reservation:
            self.reservation = self.tester.run_instance(**self.run_instance_params)

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
            new_image_reservation = self.tester.run_instance(**self.run_instance_params)
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
            new_image_reservation = self.tester.run_instance(**self.run_instance_params)
            for new_instance in new_image_reservation.instances:
                ## Check that our temp file exists
                new_instance.sys("ls -la")
                new_instance.sys("ls " + temp_file, code=0)
            self.tester.terminate_instances(new_image_reservation)

if __name__ == "__main__":
    testcase= EutesterTestCase(name='bfebstest')
    testcase.setup_parser(description="Test the Eucalyptus EC2 BFEBS image functionality.")
    testcase.parser.add_argument('--imgurl',
                        help="BFEBS Image to splat down", default=None)
    testcase.get_args()
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