#!/usr/bin/env python
#
##########################
#                        #
#       Test Cases       #
#                        #
##########################
#        Test Case is intended to test EBS services and persistance of EBS resource state(s) post EBS service
#        interruption. This should include volume and snapshots before and after service start, stop, restart, and SC
#        reboot.
#
#
#        Cleanup:
#        --if 'fof' flag is not set, will remove all volumes, instance, and snapshots created during this test
#
#    @author: clarkmatthew



from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import TestColor
from eucaops import ec2ops
#from eutester.euinstance import EuInstance
#from eutester.euvolume import EuVolume
#from eutester.eusnapshot import EuSnapshot
from eucaops import Eucaops
import eutester
import time
import copy

class Ebs_Persistance_Tests(EutesterTestCase):
    def __init__(self):
        #### Pre-conditions
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument('--testbfebs',
                                 help='If set will attempt test with a BFEBS image',
                                 action='store_true',
                                 default=False)
        self.parser.add_argument('--bfebsemi',
                                 help='BFEBS EMI to test with, otherwise will try to find one',
                                 default=None)
        self.parser.add_argument('--volsperinstance',
                                 type=int,
                                 help='Number of volumes to create per instance',
                                 default=2)
        self.parser.add_argument('--snapcount',
                                 type=int,
                                 help='Number of snapshots to create for snap related tests, default:2',
                                 default=2)
        self.parser.add_argument('--size',
                                 type=int,
                                 help='Size in GB for created volumes, default:1',
                                 default=1)
        self.parser.add_argument('--timepergig',
                                 type=int,
                                 help='Time allowed per gig size of volume during volume creation, default:120',
                                 default=300)
        self.parser.add_argument('--deletetimeout',
                                 type=int,
                                 help='Time allowed for volume to transition from deleting to deleted, default:120',
                                 default=120)
        self.parser.add_argument('--no_clean_on_exit',
                                 help='If set will not attempt to remove created test artifacts after running',
                                 action='store_true',
                                 default=False)

        self.get_args()
        # Setup basic eutester object
        self.tester = self.do_with_args(Eucaops)
        #replace default eutester debugger with eutestcase's for more verbosity...
        self.tester.debug = lambda msg: self.debug(msg, traceback=2, linebyline=False)
        self.reservation = None
        self.instance = None
        ### Add and authorize a group for the instance
        ### Generate a keypair for the instance
        if self.args.zone:
            self.zones = str(self.args.zone).split(',')
        else:
            self.zones = self.tester.get_zones()
        if not self.zones:
            raise Exception('No zones found for test?')

        self.debug('Using zones for testing: ' + ",".join(self.zones))
        self.groupname = 'jenkins'
        self.group = self.tester.add_group(self.groupname)
        self.tester.authorize_group(self.group)
        self.tester.authorize_group(self.group, protocol='icmp',port='-1')
        try:
            keys = self.tester.get_all_current_local_keys()
            if keys:
                self.keypair = keys[0]
            else:
                self.keypair = keypair = self.tester.add_keypair('qa214volumechurn'+str(time.time()))
        except Exception, ke:
            raise Exception("Failed to find/create a keypair, error:" + str(ke))

        ### Get an image to work with
        if self.args.emi:
            self.image = self.tester.get_emi(emi=str(self.args.emi))
        else:
            self.image = self.tester.get_emi(root_device_type="instance-store")
        if not self.image:
            raise Exception('couldnt find instance store image')
        self.clean_method = self.cleanup

        if self.args.testbfebs:
            if self.args.bfebsemi:
                self.bfebs_image = self.tester.get_emi(emi=str(self.args.emi))
                if self.image.root_device_type != "ebs":
                    raise Exception(str(self.args.bfebsemi) + ": Does not have EBS root_device_type")
            else:
                self.bfebs_image = self.tester.get_emi(root_device_type="ebs")
            if not self.image:
                raise Exception('"testbfebs" argument was set, but no BFEBS image found or provided')
        self.volumes = []
        self.instances = []
        self.bfebs_instances = []
        self.snapshots = []
        self.bfebs_volumes = []
        self.timepergig = self.args.timepergig
        self.clean_on_exit = True
        if self.args.no_clean_on_exit:
            self.clean_on_exit = False




    def cleanup(self, instances=True):
        '''
        Attempts to clean up test artifacts...
        '''
        try:
            self.tester.cleanup_artifacts()
        except Exception, e:
            tb = self.tester.get_traceback()
            raise Exception('Cleanupfailed:'+str(e) + "\n" +str(tb))

    def pretest1_pre_service_restart_launch_test_instances(self):
        """
        For each zone, check if there are multiple nodes. If so launch 2 instances per that zone (no need to do more for
        this test). If there is only 1 node launch 1 instance. This should produce a multi-node and multi-cluster
        test.This tests should be completed per zone prior to restarting services.
        """
        instances = []
        for zone in self.zones:
            count = 2 if len(self.tester.service_manager.get_all_node_controllers(part_name=str(zone))) > 1 else 1
            instances.extend(self.tester.run_image(image=self.image,
                                                   zone=zone,
                                                   min=count,
                                                   max=count,
                                                   group=self.group,
                                                   keypair=self.keypair,
                                                   monitor_to_running=False))
        self.instances = self.tester.monitor_euinstances_to_running(instances)


    def pretest2_pre_service_restart_create_volume_resources(self,
                                                     volsperinstance=2,
                                                     size=1,
                                                     timepergig=300):
        """
        Definition: Create volumes to be used in this test based upon volsperinstance and size args provided.
         This tests should be completed per zone prior to restarting services.

        :param volsperinstance: integer how many concurrent volumes to create/delete per instance
        :param size: integer size of volume(s) in GB
        :param timepergig: integer time allowed per GB in seconds during creation
        """
        volumes = []
        for zone in self.zones:
            instancecount = 0
            for instance in self.instances:
                if instance.placement == zone:
                    instancecount += 1
            volcount = instancecount*volsperinstance
            volumes.extend(self.tester.create_volumes(zone,
                                                      size=size,
                                                      count=volcount,
                                                      monitor_to_state=None,
                                                      timepergig=timepergig))
        self.volumes = self.tester.monitor_created_euvolumes_to_state(volumes,timepergig=timepergig)
        self.status('pre_service_restart_create_volume_resources, done',
                    testcolor=TestColor.get_canned_color('whiteonblue'))


    def pretest3_pre_service_restart_attach_all_volumes(self):
        '''
        Definition: Attach all volumes created in this test to all instances created in this test.
        This tests should be completed per zone prior to restarting services.
        '''
        self.status("\'pre_service_restart_attach_all_volumes\' starting...",
                    testcolor=TestColor.get_canned_color('whiteonblue'))

        for instance in self.instances:
            for x in xrange(0,self.args.volsperinstance):
                for vol in self.volumes:
                    if vol.zone == instance.placement and vol.status == 'available':
                        try:
                            instance.attach_volume(vol,timeout=90)
                        except ec2ops.VolumeStateException, vse:
                            self.status("This is a temp work around for testing, this is to avoid bug euca-5297"+str(vse),
                                        testcolor=TestColor.get_canned_color('failred'))
                            time.sleep(10)
                            self.debug('Monitoring volume post VolumeStateException...')
                            vol.eutest_attached_status = None
                            self.tester.monitor_euvolumes_to_status([vol],status='in-use',attached_status='attached',timeout=60)
        self.status("\'pre_service_restart_attach_all_volumes\' done",
                        testcolor=TestColor.get_canned_color('whiteonblue'))


    def pretest4_pre_service_restart_create_snap_per_zone(self,timepergig=300):
        """
        Definition: Create a single snapshot. This tests should be completed per zone prior to restarting services.
        :param timepergig: integer time allowed per GB in seconds during creation
        :param deletetimeout: integer timeout in seconds waiting for volume to transition to 'deleted' state
        """
        snaps = []
        snapvols = []
        #Add one volume from each zone...
        for zone in self.zones:
            for vol in self.volumes:
                if vol.zone == zone:
                    snapvols.append(vol)
                    break
        #Create a snapshot of each volume...
        wait_on_progress = len(snapvols)*25
        for vol in snapvols:
            snaps.extend(self.tester.create_snapshots(vol,
                                                      count=1,
                                                      wait_on_progress=wait_on_progress,
                                                      monitor_to_completed=False,))
        self.tester.monitor_eusnaps_to_completed(snaps, wait_on_progress=wait_on_progress)
        self.snapshots = snaps


    def pretest5_pre_service_restart_launch_bfebs_test_instances(self):
        """
        For each zone, check if there are multiple nodes.
        If so launch 2 bfebs instances per that zone (no need to do more for
        this test). If there is only 1 node launch 1 instance. This should produce a multi-node and multi-cluster
        test. This tests should be completed per zone prior to restarting services.
        """
        instances = []
        for zone in self.zones:
            count = 2 if len(self.tester.service_manager.get_all_node_controllers(part_name=str(zone))) > 1 else 1
            instances.extend(self.tester.run_image(image=self.image,
                                                   zone=zone,
                                                   min=count,
                                                   max=count,
                                                   group=self.group,
                                                   keypair=self.keypair,
                                                   monitor_to_running=False))
        self.bfebs_instances = self.tester.monitor_euinstances_to_running(instances)


    def pretest6_pre_service_restart_create_bfebs_volume_resources(self,
                                                                    volsperinstance=2,
                                                                    size=1,
                                                                    timepergig=300):
        """
        Definition: Create volumes to be used in this test based upon volsperinstance and size args provided.
         This tests should be completed per zone prior to restarting services.

        :param volsperinstance: integer how many concurrent volumes to create/delete per instance
        :param size: integer size of volume(s) in GB
        :param timepergig: integer time allowed per GB in seconds during creation
        """
        volumes = []
        for zone in self.zones:
            instancecount = 0
            for instance in self.bfebs_instances:
                if instance.placement == zone:
                    instancecount += 1
            volcount = instancecount*volsperinstance
            volumes.extend(self.tester.create_volumes(zone,
                                                      size=size,
                                                      count=volcount,
                                                      monitor_to_state=None,
                                                      timepergig=timepergig))
        self.bfebs_volumes = self.tester.monitor_created_euvolumes_to_state(volumes,timepergig=timepergig)
        self.status('pretest6_pre_service_restart_create_bfebs_volume_resources, done',
                    testcolor=TestColor.get_canned_color('whiteonblue'))

    def pretest7_per_service_restart_attach_vols_to_bfebs_instances(self,volsperinstance=2):
        '''
        Definition: Attach all volumes created in this test for bfebs to all bfebs instances created in this test.
        This tests should be completed per zone prior to restarting services.
        '''
        self.status("\' pretest7_per_service_restart_attach_vols_to_bfebs_instances\' starting...",
                    testcolor=TestColor.get_canned_color('whiteonblue'))

        for instance in self.bfebs_instances:
            for x in xrange(0, volsperinstance):
                for vol in self.bfebs_volumes:
                    if vol.zone == instance.placement and vol.status == 'available':
                        try:
                            instance.attach_volume(vol,timeout=90)
                        except ec2ops.VolumeStateException, vse:
                            self.status("This is a temp work around for testing, this is to avoid bug euca-5297"+str(vse),
                                        testcolor=TestColor.get_canned_color('failred'))
                            time.sleep(10)
                            self.debug('Monitoring volume post VolumeStateException...')
                            vol.eutest_attached_status = None
                            self.tester.monitor_euvolumes_to_status([vol],status='in-use',attached_status='attached',timeout=60)
        self.status("\' pretest7_per_service_restart_attach_vols_to_bfebs_instances\' done",
                    testcolor=TestColor.get_canned_color('whiteonblue'))

    def print_all_test_resources(self):
        self.status('Printing test resources prior to service interruption...',
                    testcolor=TestColor.get_canned_color('whiteonblue'))
        self.tester.print_euinstance_list(self.instances)
        self.tester.print_euvolume_list(self.volumes)
        self.tester.print_eusnapshot_list(self.snapshots)

    def reboot_sc_machine_verify_post_reboot(self, timeout = 600):
        """
        Definition: Restart the eucalyptus storage controller service
        """
        self.print_all_test_resources()
        #List to delay restart of storage controllers co-located with a cloud controller
        debug_str = ""
        #first make sure everything is good before we star the test...
        self.tester.service_manager.all_services_operational()
        storage_controllers = []
        self.zones = self.zones or self.tester.get_zones()
        for zone in self.zones:
            self.debug('Getting storage controllers for :' + str(zone))
            storage_controllers.extend(self.tester.service_manager.get_all_storage_controllers(partition=zone))
        self.tester.service_manager.print_services_list(storage_controllers)
        if not storage_controllers:
            raise Exception('Storage controller list was not populated for zones:' + ",".join(self.zones))
        for sc in storage_controllers:
            debug_str = ""
            all_services_on_sc = self.tester.service_manager.get_all_services_by_filter(hostname=sc.hostname)
            for service in all_services_on_sc:
                debug_str += "(" + str(service.hostname) + ":" + service.type + "), "
            self.status("Now rebooting machine hosting services:"+str(debug_str),
                        testcolor=TestColor.get_canned_color('whiteonblue'))
            sc.machine.reboot()
        if not storage_controllers:
            raise Exception('Storage controller list post reboot was not populated for zones:' + ",".join(self.zones))
        start = time.time()
        elapsed = 0
        waiting = copy.copy(storage_controllers)
        while elapsed < timeout and waiting:
            elapsed = int(time.time()-start)
            for sc in waiting:
                if self.tester.ping(sc.hostname, poll_count=1):
                    waiting.remove(sc)
            if waiting:
                debug_str = ""
                for sc in waiting:
                    debug_str += " " + str(sc.hostname) + ","
                self.debug("Waiting on SC's to become reachable post reboot:"
                           + str(debug_str) + ", elapsed:"+str(elapsed))
                time.sleep(10)
            else:
                self.status("All SC machines are reachable again, now wait for SSH...",
                            testcolor=TestColor.get_canned_color('whiteonblue'))
                break
        if waiting:
            raise Exception("SC machines were not reachable after: "+str(elapsed)+" seconds:"+str(debug_str))
        if not storage_controllers:
            raise Exception('Storage controller list was not populated after waiting for reachable')
        start = time.time()
        elapsed = 0
        waiting_for_ssh = copy.copy(storage_controllers)
        debug_str = ""
        while elapsed < 90 and waiting_for_ssh:
            elapsed = int(time.time()-start)
            for sc in waiting_for_ssh:
                try:
                    sc.machine.refresh_ssh()
                    sc.machine.cmd(" ")
                    waiting_for_ssh.remove(sc)
                except Exception, e:
                    self.debug('Failed to refresh ssh to:' + str(sc.hostname) + ', err:'+str(e))

            if waiting_for_ssh:
                debug_str = ""
                for sc in waiting:
                    debug_str += " " + str(sc.hostname) + ","
                self.debug("Waiting on SSH connections to SCs:"
                           + str(debug_str) + ", elapsed:"+str(elapsed))
                time.sleep(10)
            else:
                self.status("All SC machines have established SSH connections, now wait on services to come back...",
                            testcolor=TestColor.get_canned_color('whiteonblue'))
                break
        if waiting_for_ssh:
            raise("SC machines failed to establish SSH after: "+str(elapsed)+" seconds:"+str(debug_str))
        if not storage_controllers:
            raise Exception('Storage controller list was not populated after waiting for ssh')
        self.start_all_services_on_storage_controllers(storage_controllers)

    def start_tgtd_service(self,sc_list):
        for sc in sc_list:
            sc.machine.sys('service tgtd start', code=0)

    @eutester.Eutester.printinfo
    def start_all_services_on_storage_controllers(self, sc_list):
        self.status("Waiting for storage controller's services to start...",
                    testcolor=TestColor.get_canned_color('whiteonblue'))
        all_services_on_sc = []
        if not sc_list:
            raise Exception("sc_list was empty in: start_all_services_on_storage_controllers")
        #wait = 10 * 60
        for sc in sc_list:
            self.debug('Getting all services co-existing on sc: ' + str(sc.hostname))
            all_services_on_sc.extend(self.tester.service_manager.get_all_services_by_filter(hostname=sc.hostname))

        for service in all_services_on_sc:
            service.start()
        self.debug('Issued start to all services, now wait for: all_services_operational')
        self.tester.service_manager.all_services_operational()
        try:
            for service in all_services_on_sc:
                self.tester.service_manager.wait_for_service(service)
        except Exception, e:
            dbgout = self.tester.get_traceback()
            self.tester.service_manager.print_services_list(all_services_on_sc)
            dbgout += "\nFailed waiting for all services on rebooted machines to recover\n"
            raise Exception(dbgout + str(e))
        self.tester.service_manager.print_services_list(all_services_on_sc)


    def test1_post_service_interruption_check_attached_volumes(self, check_vols=None, check_instances=None):
        """
        Definition: Attempts to verify that volumes maintained their attached state through the SC reboot.
        """
        check_vols = check_vols or self.volumes
        check_instances = check_instances or self.instances
        write_length = 10000
        errmsg = ""
        self.tester.print_euvolume_list(check_vols)

        for vol in check_vols:
            vol.update()
            if vol.status == "in-use" and (vol.attach_data and vol.attach_data.status == 'attached' ):
                for instance in check_instances:
                    if instance.id == vol.attach_data.instance_id:
                        if not vol in instance.attached_vols:
                            errmsg += "Volume:" + str(vol.id) \
                                      + " is attached to " + str(instance.id) + ", but not in instance attached list?"
                        break
            else:
                errmsg += "Volume:" + str(vol.id) + ", status:" + str(vol.status) \
                          + " was not attached post service interruption \n"

        if errmsg:
            raise Exception(errmsg)

        self.status("Attached state passed. Now checking read/write with attached volumes...",
                    testcolor=TestColor.get_canned_color('whiteonblue'))
        for instance in check_instances:
            instance.update()
            instance.reset_ssh_connection()
            try:
                bad_vols = instance.get_unsynced_volumes()
                if bad_vols:
                    errmsg = str(instance.id) + "Unsynced vols found:"
                    for bad_vol in bad_vols:
                        errmsg = errmsg + str(bad_vol.id) + ":" + str(bad_vol.status) + ","
                    errmsg = errmsg + "\n"
            except Exception, ve:
                errmsg = errmsg + "\n" + str(ve)
            if errmsg:
                raise Exception(errmsg)
            for vol in instance.attached_vols:
                try:
                    md5before = vol.md5
                    md5now = instance.md5_attached_euvolume(vol,updatevol=False)
                    if md5before != md5now:
                        errmsg += str(instance.id) +"Volume:" + str(vol.id) \
                                    + "has different md5 sum after service interruption. Before:'" \
                                    + str(md5before) + "' - vs - '" + str(md5now) + "'"
                    vol.length = write_length
                    instance.vol_write_random_data_get_md5(vol,length=write_length, overwrite=True)
                    instance.sys('sync',code=0)
                except Exception, e:
                    errmsg += str(instance.id) + "Volume:" + \
                              str(vol.id) + ", error while using vol post service interruption, err: "+str(e)
        if errmsg:
            raise Exception(errmsg)
        self.status("Read/write test passed, now testing detachment of volumes...",
                    testcolor=TestColor.get_canned_color('whiteonblue'))
        for instance in self.instances:
            for vol in instance.attached_vols:
                try:
                    instance.detach_euvolume(vol)
                except Exception, e:
                    errmsg += str(instance.id) + "Volume:" + str(vol.id) + "Error while detaching, err:" + str(e)
        if errmsg:
            raise Exception(errmsg)
        self.status("Attached volume checks post service interruption have passed.",
                    testcolor=TestColor.get_canned_color('whiteonblue'))



    def test2_post_service_interuption_check_volume_from_snapshots(self):

        """
        Definition: Attempts to check volume creation from snapshots created before SC restart.
        """
        self.status("Checking creation of volumes from pre-existing snapshots post service interruption...",
                    testcolor=TestColor.get_canned_color('whiteonblue'))
        vols = []
        if not self.snapshots:
            raise Exception("self.snapshots not populated?")
        for snap in self.snapshots:
            for zone in self.zones:
                vols.extend(self.tester.create_volumes(zone, snapshot=snap, monitor_to_state=None))
        #Now monitor created volumes to state available, use a large timeout per gig here.
        self.volumes.extend(self.tester.monitor_created_euvolumes_to_state(vols, state='available', timepergig=360))
        self.status("Done creating volumes from pre-existing snapshots post service interruption.",
                    testcolor=TestColor.get_canned_color('whiteonblue'))


    def test3_post_service_interuption_check_volume_attachment_of_new_vols_from_old_snaps(self):
        vols = []
        errmsg = ""
        for snap in self.snapshots:
            vols.extend(self.tester.get_volumes(status='available', snapid=snap.id))

        if not vols:
            raise Exception("No vols were found as created from previous snapshots")
        if not self.instances:
            raise Exception('No instances to use for this test')
        if not self.snapshots:
            raise Exception('No snapshots to use for this test')
        for vol in vols:
            vol.update()
        availvols = copy.copy(vols)
        self.status('Attempting to attach the following volumes:',testcolor=TestColor.get_canned_color('whiteonblue'))
        self.tester.print_euvolume_list(availvols)
        #Iterate through the volumes, and attach them all to at least one instance in each zone.
        for instance in self.instances:
            if not availvols:
                break
            for vol in availvols:
                if vol.zone == instance.placement:
                    availvols.remove(vol)
                    try:
                        try:
                            instance.attach_volume(vol, timeout=90)
                        except ec2ops.VolumeStateException, vse:
                            self.status("This is a temp work around for testing, this is to avoid bug euca-5297"+str(vse),
                                        testcolor=TestColor.get_canned_color('failred'))
                            time.sleep(10)
                            self.tester.monitor_euvolumes_to_status([vol],status='in-use',attached_status='attached',timeout=60)
                        for snap in self.snapshots:
                            snap.update()
                            if vol.snapshot_id == snap.id:
                                if vol.md5len != snap.eutest_volume_md5len:
                                    self.debug('Need to adjust md5sum for length of snapshot...')
                                    vol.md5len = snap.eutest_volume_md5len
                                    instance.vol_write_random_data_get_md5(vol,length=snap.eutest_volume_md5len)
                                if vol.md5 != snap.eutest_volume_md5:
                                    errmsg += "Volume:" + str(vol.id) + " MD5 did not match snapshots " \
                                              + str(snap.id) + ": snapmd5:" + str(snap.eutest_volume_md5) \
                                              + " --vs volmd5:-- " + str(vol.md5)
                    except Exception, e:
                        errmsg += str(instance.id) +"Volume:" + str(vol.id) \
                              + " error when attaching and comparing md5, err:" + str(e)
        self.status('Volume status post attachment operation:',testcolor=TestColor.get_canned_color('whiteonblue'))
        self.tester.print_euvolume_list(vols)
        if errmsg:
            raise Exception(errmsg)




    def test4_post_service_interuption_check_snapshot_creation(self):
        self.status('Attempting to verify snapshot creation post reboot',\
                    testcolor=TestColor.get_canned_color('whiteonblue'))
        testvols = []
        testsnaps = []
        for zone in self.zones:
            for vol in self.volumes:
                if vol.zone == zone:
                    testvols.append(vol)
                    break
        for vol in testvols:
            testsnaps.extend(self.tester.create_snapshots(vol, monitor_to_completed=False))
        wait_on_progress = int(len(testsnaps)*25)
        self.tester.monitor_eusnaps_to_completed(testsnaps,wait_on_progress=wait_on_progress)
        self.snapshots.extend(testsnaps)

    def test5_post_service_interruption_check_bfebs_instances(self):
        """
        Definition: Attempts to check the state of bfebs instances launched in this test prior
        to restarting the SC.
        """
        for instance in self.bfebs_instances:
            last_state = instance.state
            instance.update()
            if instance.state != last_state:
                raise Exception('Instance state before SC restart: '
                                + str(last_state) + " != post restart:"
                                + str(instance.state))
            self.test1_post_service_interruption_check_attached_volumes(check_vols=self.bfebs_volumes,
                                                                        check_instances=self.bfebs_instances)


if __name__ == "__main__":
    testcase = Ebs_Persistance_Tests()

    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list

    instance_store_only_tests = [ 'pretest1_pre_service_restart_launch_test_instances',
                                    'pretest2_pre_service_restart_create_volume_resources',
                                    'pretest3_pre_service_restart_attach_all_volumes',
                                    'pretest4_pre_service_restart_create_snap_per_zone',
                                    'reboot_sc_machine_verify_post_reboot',
                                    'test1_post_service_interruption_check_attached_volumes',
                                    'test2_post_service_interuption_check_volume_from_snapshots',
                                    'test3_post_service_interuption_check_volume_attachment_of_new_vols_from_old_snaps',
                                    'test4_post_service_interuption_check_snapshot_creation']
    bfebs_test_list = [ 'pretest1_pre_service_restart_launch_test_instances',
                        'pretest2_pre_service_restart_create_volume_resources',
                        'pretest3_pre_service_restart_attach_all_volumes',
                        'pretest4_pre_service_restart_create_snap_per_zone',
                        'pretest5_pre_service_restart_launch_bfebs_test_instances',
                        'pretest6_pre_service_restart_create_bfebs_volume_resources',
                        'pretest7_per_service_restart_attach_vols_to_bfebs_instances',
                        'reboot_sc_machine_verify_post_reboot',
                        'test1_post_service_interruption_check_attached_volumes',
                        'test2_post_service_interuption_check_volume_from_snapshots',
                        'test3_post_service_interuption_check_volume_attachment_of_new_vols_from_old_snaps',
                        'test4_post_service_interuption_check_snapshot_creation',
                        'test5_post_service_interruption_check_bfebs_instances']

    list = testcase.args.tests
    if not list:
        if testcase.args.testbfebs:
            list = bfebs_test_list
        else:
            list = instance_store_only_tests


    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,eof=True,clean_on_exit=testcase.clean_on_exit)
    exit(result)
