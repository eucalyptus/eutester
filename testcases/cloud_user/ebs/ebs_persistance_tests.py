#!/usr/bin/env python
#
##########################
#                        #
#       Test Cases       #
#                        #
##########################
#
#
#
#        Cleanup:
#        --if 'fof' flag is not set, will remove all volumes, instance, and snapshots created during this test
#
#    @author: clarkmatthew



from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import TestColor
from eucaops import Eucaops
import time

class Ebs_Multi_Node_Multi_Cluster_Persistance_Tests(EutesterTestCase):
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
                                 default=5)
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
                                 default=120)
        self.parser.add_argument('--deletetimeout',
                                 type=int,
                                 help='Time allowed for volume to transition from deleting to deleted, default:120',
                                 default=120)
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops()
        print 'remove this line^^'
        exit(1)
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
        self.groupname = 'jenkins'
        self.group = self.tester.add_group(self.groupname)
        self.tester.authorize_group(self.group)
        self.tester.authorize_group(self.group, protocol='icmp',port='-1')
        try:
            keys = self.tester.get_all_current_local_keys()
            if keys != []:
                self.keypair = keys[0]
            else:
                self.keypair = keypair = self.tester.add_keypair('qa214volumechurn')
        except Exception, ke:
            raise Exception("Failed to find/create a keypair, error:" + str(ke))

        ### Get an image to work with
        if self.args.emi:
            self.image = self.tester.get_emi(emi=str(self.args.emi))
        else:
            self.image = self.tester.get_emi(root_device_type="instance-store",not_location='windows')
        if not self.image:
            raise Exception('couldnt find instance store image')
        self.clean_method = self.cleanup

        if self.args.testbfebs:
            if self.args.bfebsemi:
                self.image = self.tester.get_emi(emi=str(self.args.emi))
                if self.image.root_device_type != "ebs":
                    raise Exception(str(self.args.bfebsemi) + ": Does not have EBS root_device_type")
            else:
                self.image = self.tester.get_emi(root_device_type="ebs",not_location='windows')
            if not self.image:
                raise Exception('"testbfebs" argument was set, but no BFEBS image found or provided')




    def cleanup(self, instances=True):
        '''
        if instances:
            try:
                if self.reservation:
                    self.tester.terminate_instances(self.reservation)
            except Exception, e:
                err = str(e)
        '''
        try:
            self.tester.cleanup_artifacts()
        except Exception, e:
            raise Exception('Cleanupfailed:'+str(e))

    def pre_service_restart_launch_test_instances(self):
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
                                                   monitor_to_running=False))
        self.instances = self.tester.monitor_euinstances_to_running(instances)


    def pre_service_restart_create_volume_resources(self,
                                                     volsperinstance=2,
                                                     size=1,
                                                     timepergig=120):
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
        self.volumes = self.tester.monitor_created_euvolumes_to_state(volumes,timpergig=self.timepergig)
        self.status('pre_service_restart_create_volume_resources, done',
                    testcolor=TestColor.get_canned_color('whiteonblue'))


    def pre_service_restart_attach_all_volumes(self):
        '''
        Definition: Attach all volumes created in this test to all instances created in this test.
        This tests should be completed per zone prior to restarting services.
        '''


            self.status("\'pre_service_restart_attach_all_volumes\' starting...",
                        testcolor=TestColor.get_canned_color('whiteonblue'))

            self.tester.print
            for instance in self.instances:
                for x in xrange(0,self.args.volsperinstance):
                    for vol in self.volumes:
                        if vol.zone == instance.placement and vol.status == 'available':
                            instance.attach_volume(vol)
                            break
            self.status("\'pre_service_restart_attach_all_volumes\' done",
                        testcolor=TestColor.get_canned_color('whiteonblue'))


    def pre_service_restart_create_snap_per_zone(self,timepergig=120):
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
                snapvols.append(vol)
                break
        #Create a snapshot of each volume...
        for vol in snapvols:
            snaps.extend(self.tester.create_snapshots(vol, count=1, monitor_to_state=False))
        self.snaps = self.tester.monitor_eusnaps_to_completed(snaps)



    def restart_sc_test(self):
        """
        Definition: Restart the eucalyptus storage controller service
        """
        for zone in self.zones:
            storage_controller = self.tester.service_manager.



if __name__ == "__main__":
    testcase =Qa_214_volume_churn()

    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or [ "qa_214_test1", "qa_214_test2", "qa_214_test3", "qa_214_test4"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
