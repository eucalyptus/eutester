#!/usr/bin/env python
#
##########################
#                        #
#       Test Cases       #
#                        #
##########################
#
#        Attempts basic EBS related churn tests. Starting from basic to more involved churn tests as defined in testcase QA214:
#        Script repetitive runs stressing the following flows in concurrent use (Test script can be run concurrently via Jenkins, etc)
#        Each sub test can be called with --test testX or a list of tests, otherwise all tests will be run
#
#        test1) repeat: (create volume X -> delete volume X)
#        test2) create volume Y, then  repeat ( attach volume Y-> detach volume Y)
#        test3) repeat : ( create volume Z -> attach volume Z -> detach volume Z)
#        test4) repeat: (create volume V -> Create snapshot S from volume V, create volume SV from snapshot S, delete volume V, delete snapshot S, delete volume SV)
#        
#       
#        Cleanup:
#        --if 'fof' flag is not set, will remove all volumes, instance, and snapshots created during this test
#
#    @author: clarkmatthew



import unittest
from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import TestColor
from eucaops import Eucaops
import time



class Qa_214_volume_churn(EutesterTestCase):
    def __init__(self):
        #### Pre-conditions
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument('--testcount', type=int, help='Number of times to repeat each test, default:5',default=5)
        self.parser.add_argument('--volcount', type=int, help='Number of volumes to create per test, default:5',default=5)
        self.parser.add_argument('--snapcount', type=int, help='Number of snapshots to create for snap related tests, default:2',default=2)
        self.parser.add_argument('--size', type=int, help='Size in GB for created volumes, default:1',default=1)
        self.parser.add_argument('--timepergig', type=int, help='Time allowed per gig size of volume during volume creation, default:120',default=120)
        self.parser.add_argument('--deletetimeout', type=int, help='Time allowed for volume to transition from deleting to deleted, default:120',default=120)
        self.get_args()
        # Setup basic eutester object
        self.tester = self.do_with_args(Eucaops)
        self.tester.debug = lambda msg: self.debug(msg, traceback=2, linebyline=False)
        self.reservation = None
        self.instance = None
        ### Add and authorize a group for the instance
        ### Generate a keypair for the instance
        #create some zone objects and append them to the zonelist
        self.zone = self.args.zone or 'PARTI00'
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
        self.image = self.tester.get_emi(root_device_type="instance-store")
        if not self.image:
            raise Exception('couldnt find image')
        self.clean_method = self.cleanup

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
    
    def launch_test_instance(self):
        self.reservation = self.tester.run_instance(self.image, keypair=self.keypair, group=self.group,timeout=480)
        self.instance = self.reservation.instances[0]
        return self.instance
        
    def qa_214_test1(self, 
                     volcount=5,
                     testcount=20, 
                     size=1,  
                     timepergig=120, 
                     deletetimeout=120):
        """
        Definition: repeats: (create volume X -> delete volume X) 'count' number of times
        
        :param volcount: integer how many concurrent volumes to create/delete
        :param testcount: integer how many times to repeat this test
        :param size: integer size of volume(s) in GB
        :param timepergig: integer time allowed per GB in seconds during creation
        :param deletetimeout: integer timeout in seconds waiting for volume to transition to 'deleted' state
        """
        for x in xrange(0,testcount):
            self.status("\'qa_214_test1\' number:"+str(x)+"/"+str(testcount))
            self.volumes = self.tester.create_volumes(self.zone, size=size, count=volcount, timepergig=timepergig)
            self.tester.delete_volumes(self.volumes, poll_interval=5, timeout=deletetimeout)
            self.status('qa_214_test1: Completed:'+str(x)+'/'+str(testcount)+' tests',testcolor=TestColor.get_canned_color('whiteonblue'))
    
    
        
    def qa_214_test2(self, testcount=20, size=1,volcount=1):
        '''
        Definition: create volumes Y, then  repeat ( attach volumes Y-> detach volumes Y)
        
        :param testcount: integer times to run this test
        :param size: integer size of volume(s) to create in GB
        :param volcount: number of volumes to create for this test
        '''
        instance = self.instance or self.launch_test_instance()
        volumes = self.tester.create_volumes(self.zone, size=size, count=volcount)
        for x in xrange(0,testcount):
            self.status("\'qa_214_test2\' number:"+str(x)+"/"+str(testcount))
            for volume in volumes:
                instance.attach_volume(volume)
                time.sleep(1)
                instance.detach_euvolume(volume)
            self.status('qa_214_test2: Completed:'+str(x)+'/'+str(testcount)+' tests',testcolor=TestColor.get_canned_color('whiteonblue'))
                    
 
    def qa_214_test3(self, 
                     volcount=5,
                     testcount=5, 
                     size=1,  
                     timepergig=120, 
                     deletetimeout=120):
        """
        Definition:  repeat : ( create volume Z -> attach volume Z -> detach volume Z -> delete volume Z)
        
        :param volcount: integer how many concurrent volumes to create/delete
        :param testcount: integer how many times to repeat this test
        :param size: integer size of volume(s) in GB
        :param timepergig: integer time allowed per GB in seconds during creation
        :param deletetimeout: integer timeout in seconds waiting for volume to transition to 'deleted' state
        """
        instance = self.instance or self.launch_test_instance()
        for x in xrange(0,testcount):
            self.status("\'qa_214_test3\' number:"+str(x)+"/"+str(testcount))
            volumes = self.tester.create_volumes(self.zone, size=size, count=volcount, timepergig=timepergig)
            for volume in volumes:
                instance.attach_volume(volume)
                time.sleep(1)
                instance.detach_euvolume(volume)
            self.tester.delete_volumes(volumes, poll_interval=5, timeout=deletetimeout)
            self.status('qa_214_test3: Completed:'+str(x)+'/'+str(testcount)+' tests',testcolor=TestColor.get_canned_color('whiteonblue'))
            
    def qa_214_test4(self, 
                     volcount=5,
                     snapcount=2,
                     testcount=5, 
                     size=1,  
                     timepergig=120, 
                     deletetimeout=120):
        """
        Definition: repeat: (create volumes V -> Create snapshots S from volumes V,
                    create volume SV from snapshot S, delete volume V, 
                    delete snapshot S, delete volume SV)
        
        :param volcount: integer how many concurrent volumes to create/delete
        :param testcount: integer how many times to repeat this test
        :param size: integer size of volume(s) in GB
        :param timepergig: integer time allowed per GB in seconds during creation
        :param deletetimeout: integer timeout in seconds waiting for volume to transition to 'deleted' state
        """
        
        wait_on_progress = 15 * snapcount
        for x in xrange(0,testcount):
            volumes=[]
            snaps=[]
            self.status("\'qa_214_test4\' number:"+str(x)+"/"+str(testcount)+", volcount:"+str(volcount)+", snapcount:"+str(snapcount)+", size:"+str(size))
            self.status('Creating '+str(volcount)+' new volumes...')
            volumes = self.tester.create_volumes(self.zone, size=size, count=volcount, timepergig=timepergig)
            for vol in volumes:
                v_index = volumes.index(vol)+1
                self.status('Creating '+str(snapcount)+' snapshots from our new volume ('+str(v_index)+'/'+str(len(volumes))+'):'+str(vol.id) )
                snaps.extend(self.tester.create_snapshots(vol, count=snapcount, wait_on_progress=wait_on_progress, monitor_to_state=False))
            for snap in snaps:
                s_index = snaps.index(snap)+1
                self.status('Creating '+str(volcount)+' volumes from our new snapshot('+str(s_index)+'/'+str(len(snaps))+'):'+str(snap.id) )
                volumes.extend(self.tester.create_volumes(self.zone, count=volcount, snapshot=snap, timepergig=timepergig))
            self.status('Test#'+str(x)+': Main block of test complete, deleting '+str(len(volumes))+' volumes, and '+str(len(snaps))+' snapshots')
           
            self.tester.delete_volumes(volumes, poll_interval=5, timeout=deletetimeout)
            self.tester.delete_snapshot(snaps, basetimeout=deletetimeout)

            self.status('qa_214_test4: Completed:'+str(x)+'/'+str(testcount)+' tests',testcolor=TestColor.get_canned_color('whiteonblue'))
    

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
