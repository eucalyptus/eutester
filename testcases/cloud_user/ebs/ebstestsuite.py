#! ../share/python_lib/matt_dev/bin/python
'''
Test Summary: 

-create a volume (do this first)
-run an instance (do this second, if this fails at least we know we could create a vol)

Usage Tests: 
-negative -attempt to attach a volume to an instance in a separate cluster. 
-attach a single volume to an instance in the zones given, write random data and calc md5 of volumes
-negative:attempt to delete the attached instance, should fail
-negative:attempt to attach an in-use volume, should fail
-attach a 2nd volume to an instance, write random date to vol and calc md5 of volumes
-reboot instance
-verify both volumes are attached after reboot of instance
-detach 1st volume
-create snapshot of detached volume
-create snapshot of attached volume

Multi-cluster portion...
-attempt to create a volume of each snapshot, if multi 1 in each cluster
-attempt to attach each volume to an instance verify md5s

Properties tests:
-create a volume of greater than prop size, should fail
-create a 2nd volume attempting to exceed the max aggregate size, should fail


Cleanup:
-remove all volumes, instance, and snapshots created during this test

'''
from eucaops import Eucaops
from eutester import euinstance, euvolume, xmlrunner, euconfig
from boto.ec2.snapshot import Snapshot
import argparse
import re
import time
import os

from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import EutesterTestResult

class TestZone():
    def __init__(self, partition):
        self.partition = partition 
        self.name = partition.name
        self.instances = []
        self.volumes = []
        
    def __str__(self):
        return self.name
    
class TestSnap(Snapshot):
    
    @classmethod
    def make_testsnap_from_snap(cls,snap,zone):
        newsnap = TestSnap(snap.connection)
        newsnap.__dict__ = snap.__dict__
        newsnap.name = snap.id
        newsnap.zone = zone
        newsnap.new_vol_list = []
        newsnap.md5 = newsnap.get_orig_vol_md5()
        return newsnap

        
    def get_orig_vol_md5(self):
        md5 = None
        for vol in self.zone.volumes:
            if vol.id == self.volume_id:
                md5 = vol.md5
                return md5

class EbsTestSuite(EutesterTestCase):
    
    tester = None
    zonelist = []
    snaps = []
    keypair = None
    group = None
    multicluster=False
    image = None
    
    def __init__(self, 
                 tester=None, 
                 zone=None, 
                 config_file='../input/2b_tested.lst', 
                 password="foobar", 
                 credpath=None, 
                 volumes=None, 
                 keypair=None, 
                 group=None, 
                 image=None, 
                 vmtype=None,
                 eof=1):
        
        if tester is None:
            self.tester = Eucaops( config_file=config_file,password=password,credpath=credpath)
        else:
            self.tester = tester
        self.tester.exit_on_fail = eof
    
        self.testlist =[]
        
        self.image = image
        self.vmtype = vmtype
        self.zone = None    
        self.zonelist = []
            
        #create some zone objects and append them to the zonelist
        if self.zone is not None:
            partition = self.tester.service_manager.partitions.get(zone)
            self.zone = TestZone(zone)
            self.zonelist.append(self.zone)
        else: 
            self.setup_testzones()
    
        #If the list of volumes passed in looks good, sort them into the zones
        if self.volumes_list_check(volumes):
            self.sort_volumes(volumes)
            
        #Setup our security group for later use
        if (group is not None):
            self.group = group
        else:
            group_name='EbsTestGroup'
            
            try:
                self.group = self.tester.add_group(group_name)
                self.tester.authorize_group_by_name(self.group.name)
                self.tester.authorize_group_by_name(self.group.name,protocol="icmp",port=-1)
            except Exception, e:    
                raise Exception("Error when setting up group:"+str(group_name)+", Error:"+str(e))   
        
    
        #Setup the keypairs for later use
        try:
            if (keypair is not None):
                self.keypair = keypair
            else:     
                keys = self.tester.get_all_current_local_keys() 
                if keys != []:
                    self.keypair = keys[0]
                else:
                    self.keypair = keypair = self.tester.add_keypair('ebs_test_key-' + str(time.time()))
        except Exception, ke:
            raise Exception("Failed to find/create a keypair, error:" + str(ke))
        
        
    def setup_testzones(self):
        for zone in self.tester.service_manager.partitions.keys():
                partition = self.tester.service_manager.partitions.get(zone)
                tzone = TestZone(partition)
                self.zonelist.append(tzone)
                self.multicluster=True
        if not self.zonelist:
            raise Exception("Could not discover an availability zone to perform tests in. Please specify zone")
    
    def volumes_list_check(self, volumes):
        #helper method to validate volumes for use as a list
        if (volumes is not None) and (volumes != []) and (not isinstance(volumes,basestring)):
            return True
        else:
            return False

    def instances_list_check(self, instances):
        #helper method to validate instances for use as a list
        if (instances is not None) and (instances != []) and (not isinstance(instances,basestring)):
            return True
        else:
            return False
        
    
    def sort_volumes(self, volumes):
        for vol in volumes:
            for zone in self.zonelist:
                if vol.zone == zone.name:
                    zone.volumes.append(vol)

        
    def create_vols_per_zone(self, zonelist=None, volsperzone=1, size=1, snapshot=None, timepergig=300):
        testmsg =   """
                    Intention of this test is to verify creation of volume(s) per zone given.
                    Upon successful creation the volumes will be appended to a volumes list
                    for the zone it was created in. 
                    These volumes may be later used if in later ebstests suite tests. 
                    """    
        testmsg = testmsg + "variables provided:\nzonelist:"+str(zonelist)+"\nvolsperzone:"+str(volsperzone)+"\nsize:"+str(size)+"\nsnapshot:"+str(snapshot)
        
        self.startmsg(testmsg)
        if zonelist is None:
            zonelist = self.zonelist
        for testzone in zonelist:
            zone = testzone.name
            for x in xrange(0,volsperzone):
                vol = euvolume.EuVolume.make_euvol_from_vol(self.tester.create_volume(zone, size=size, snapshot=snapshot,timepergig=timepergig))
                testzone.volumes.append(vol)
                self.debug('create_vols_per_zone created  vol('+str(x)+') zone:'+str(zone)+' vol:'+str(vol.id))
            
        self.endsuccess()      
            
          
    def create_test_instances_for_zones(self, zonelist=None, image=None, keypair=None, group=None, vmtype=None):
        testmsg = """
                    Create an instance within each TestZone object in zonelist to help test ebs functionality.
                  """
        testmsg = testmsg+"\nVariables provided:\nzonelist:"+str(zonelist)+"\nimage:"+str(image)+"\nkeypair:"+str(keypair)+"\ngroup:"+str(group)+"\nvmtype:"+str(vmtype)
        
        self.startmsg(testmsg)
        if image is None:
            image = self.tester.get_emi(emi=self.image)
        else:
            image = self.tester.get_emi(emi=image)
        if group is None:
            group = self.group
        if keypair is None:
            keypair = self.keypair
                
        if zonelist is None:
            zonelist = self.zonelist
        vmtype = vmtype or self.vmtype
            
        for testzone in zonelist:
            zone = testzone.name
            inst = self.tester.run_instance(image=image, keypair=keypair.name, group=group, type=vmtype, zone=zone).instances[0]
            testzone.instances.append(inst)
            self.debug('Created instance: ' + str(inst.id)+" in zone:"+str(zone))
        self.endsuccess()
    
    def terminate_test_instances_for_zones(self, zonelist=None, timeout=360):
        if zonelist is None:
            zonelist = self.zonelist
        for zone in zonelist:
            for instance in zone.instances:
                self.tester.terminate_single_instance(instance, timeout)
                zone.instances.remove(instance)
    
    def negative_attach_in_use_volume_in_zones(self,zonelist=None,timeout=360):
        testmsg =   """
                    Iterates though zones and attempts to attach already attached volumes to instances within each zone.  
                    """
        testmsg = testmsg+"\nVariables provided:\nzonelist"+str(zonelist)+"\ntimeout:"+str(timeout)
        self.startmsg(testmsg)
        if zonelist is None:
            zonelist = self.zonelist
        instance = euinstance.EuInstance()
        for zone in zonelist:
            for volume in zone.volumes:
                volume.update()
                if (volume.status == "in-use"):
                    for instance in zone.instances:
                        try:
                            #This should fail
                            instance.attach_euvolume(volume,timeout=timeout)
                        except Exception, e:
                            #If it failed were good
                            self.debug("negative_attach_in_use_volume_in_zones Passed. Could not attach in-use volume")
                            self.endsuccess()
                            pass
                        else:
                            #The operation did fail, but this test did
                            raise Exception("negative_attach_in_use_volume_in_zones failed volume attached")
        
                
    
    def attach_all_avail_vols_to_instances_in_zones(self, zonelist=None, timeout=360):
        testmsg =   """
                    Iterates though zones and attempts to attach volumes to instances within each zone.  
                    """
        testmsg = testmsg+"\nVariables provided:\nzonelist"+str(zonelist)+"\ntimeout:"+str(timeout)
        self.startmsg(testmsg)
        if zonelist is None:
            zonelist = self.zonelist
        instance = euinstance.EuInstance()
        for zone in zonelist:
            for volume in zone.volumes:
                volume.update()
                if (volume.status == "available"):
                    for instance in zone.instances:
                        try:
                            instance.attach_euvolume(volume,timeout=timeout)
                        except Exception, e:
                            self.debug("attach_all_vols_to_instances_in_zones failed to attach volume")
                            raise e
                    #instance.vol_write_random_data_get_md5(volume,timepergig=120)
        self.endsuccess()
                    
                        
    def negative_delete_attached_volumes_in_zones(self,zonelist=None, timeout=60):
        testmsg =   """
                    Negative test case. Attempts to delete attached volumes for each euinstace
                    in each zone per zone list provided. Confirms that volumes did NOT delete while in use/attached.
                    
                    
                    """
        testmsg = testmsg + "\nVariables provided:\nzonelist:"+str(zonelist)+"\ntimeout:"+str(timeout)
        self.startmsg(testmsg)
        #instance = euinstance.EuInstance()
        #volume = euvolume.EuVolume()
      
        if zonelist is None:
            zonelist = self.zonelist
        
        for zone in zonelist:
            for instance in zone.instances:
                #resync instance volume state first
                self.debug('syncing volumes for instance:'+str(instance.id))
                badvols = instance.get_unsynced_volumes() 
                if (badvols is not None) and (badvols != []):
                    self.debug("negative_delete_attached_volumes_in_zones, failed")
                    try:
                        errmsg=""
                        for badvol in badvols:
                            errmsg=errmsg+str(badvol.id)+", "
                    except:pass
                    raise Exception("("+str(instance.id)+") Unsync'd volumes found:"+errmsg)
                #Attempt to delete volumes, confirm this operation does not succeed
                for volume in instance.attached_vols:
                    try:
                        volume.delete()
                    except: 
                        self.debug("Success- could not delete attached volume:"+str(volume.id))
                    else:
                        volume.update()
                        if (volume.status == "deleted"):
                            self.debug("negative_delete_attached_volumes_in_zones, failed:"+str(volume.id))
                            raise Exception("Was able to delete attached volume:"+str(volume.id))
        self.endsuccess()            
                        
    def reboot_instances_in_zone_verify_volumes(self,zonelist=None,waitconnect=30, timeout=360):
        testmsg =   """
                    Attempts to iterate through each instance in each zone and reboot the instance(s). 
                    Attempts to verify the attached volume state post reboot. 
                    """
        testmsg = testmsg + "\nVariables Provided:\nzonelist:"+str(zonelist)+"\nwaitconnect:"+str(waitconnect)+"\ntimeout:"+str(timeout)
        self.startmsg(testmsg)
        if zonelist is None:
            zonelist = self.zonelist
        instance = euinstance.EuInstance()
        for zone in zonelist:
            for instance in zone.instances:
                instance.reboot_instance_and_verify(waitconnect=waitconnect, timeout=timeout, checkvolstatus=True)
        self.endsuccess()
        
    def detach_volumes_in_zones(self,zonelist=None, timeout=360, volcount=1):
        testmsg =   """
                    Attempts to detach volcount volumes from each instance in the provided zonelist. 
                    Attempts to verify detached volume state on both the cloud and the guest
                    by default will attempt to detach a single volume from each instance
                    """
        testmsg = testmsg + "\nVariables provided:\nzonelist:"+str(zonelist)+"\ntimeout:"+str(timeout)+"\nvolcount:"+str(volcount)
                    
        self.startmsg(testmsg)
        if zonelist is None:
            zonelist = self.zonelist
        #instance = euinstance.EuInstance()
        for zone in zonelist:
            for instance in zone.instances:
                vc=0
                badvols = instance.get_unsynced_volumes() 
                if (badvols is not None) and (badvols != []):
                    self.debug("failed")
                    raise Exception("Unsync volumes found on:"+str(instance.id)+"\n"+" ".join(badvols))
                for volume in instance.attached_vols:
                    #detach number of volumes equal to volcount
                    if vc >= volcount:
                        break
                    else:
                        vc += 1
                        try:
                            instance.detach_euvolume(volume, timeout=timeout)
                        except Exception, e: 
                            self.debug("fail. Could not detach Volume:"+str(volume.id)+"from instance:"+str(instance.id))
                            raise e
        self.endsuccess()
        
    
    def delete_volumes_in_zones(self, zonelist=None, timeout=60):
        self.startmsg()
        if zonelist is None:
            zonelist = self.zonelist
        for zone in zonelist:
            for volume in zone.volumes:
                start = time.time()
                elapsed = 0
                volume.delete()
                while (volume.status != "deleted") and (elapsed < timeout):
                    volume.update()
                    elapsed = int(time.time()-start)
                if volume.status != "deleted":
                    self.debug("failed to delete volume:"+str(volume.id))
                else:
                    zone.volumes.remove(volume)
        self.endsuccess()
        
        
    def delete_snapshots_in_zones(self, zonelist=None,snaplist=None, timeout=300):
        testmsg =   """
                    Attempts to iterate through zonelist, and delete all snapshots 
                    within that zone
                    """
        testmsg = testmsg +"\nVariables provided:\nzonelist:"+str(zonelist)+"\nsnaplist:"+str(snaplist)+"\ntimeout:"+str(timeout)
        self.startmsg(testmsg)
        if zonelist is None:
            zonelist = self.zonelist
        if snaplist is None:
            snaplist = self.snaps
        for zone in zonelist:
            for snap in snaplist:
                if snap.zone == zone:
                    self.tester.delete_snapshot(snap, timeout=timeout)
                    snaplist.remove(snap)
        self.endsuccess()
        
                
        
        
    def create_snapshots_all_vols_in_zone(self, zonelist=None, volstate="all", waitOnProgress=20):
        testmsg =   """
                    Attempts to iterate through each zone in zonelist, and create a snapshot from each volume
                    in the zone's volume list who's state matches volstate
                    """
        testmsg = testmsg +"\nVariables provided:\nzonelist:"+str(zonelist)+"\nvolstate:"+str(volstate)
        self.startmsg(testmsg)
        if zonelist is None:
            zonelist = self.zonelist
        for zone in zonelist:
            for volume in zone.volumes:
                volume.update()
                if volstate == "all" or volume.status == volstate:
                    self.snaps.append(TestSnap.make_testsnap_from_snap(self.tester.create_snapshot(volume.id, description="ebstest", waitOnProgress=20),zone))
        self.endsuccess()
        
        
    def create_vols_from_snap_in_same_zone(self, zonelist=None,timepergig=300):
        testmsg =   """
                    Attempts to create a volume from each snapshot contained in each zone's list of snapshots.
                    This test attempts to create volumes from snapshots who's original volume is also in this
                    zone. 
                    """
        testmsg = testmsg+"\nVariables provided:\nzonelist:"+str(zonelist)
        self.startmsg(testmsg)
        
        if zonelist is None:
            zonelist = self.zonelist
        for zone in zonelist:
            for snap in self.snaps:
                if snap.zone == zone:
                    self.debug("Creating volume from snap:"+str(snap.id))
                    newvol = euvolume.EuVolume.make_euvol_from_vol(self.tester.create_volume(zone.name, size=0, snapshot=snap,timepergig=timepergig))
                    zone.volumes.append(newvol)
                    snap.new_vol_list.append(newvol)
        self.endsuccess()
        
    def attach_new_vols_from_snap_verify_md5(self,zonelist=None, timeout=360,timepergig=360):
        testmsg =   """
                    Attempts to attach volumes which were created from snapshots and are not in use. 
                    After verifying the volume is attached and reported as so by cloud and guest, 
                    this test will attempt to compare the md5 sum of the volume to the md5 contained in 
                    the snapshot which represents the md5 of the original volume. 
                    This test accepts a timepergig value which is used to guesstimate a reasobale timeout while
                    waiting for the md5 operation to be executed. 
                    """
        testmsg = testmsg + "\nVariables provided:\nzonelist:"+str(zonelist)+"\ntimeout:"+str(timeout)+"\ntimepergig:"+str(timepergig)
        self.startmsg(testmsg)
        instance = euinstance.EuInstance()
        if zonelist is None:
            zonelist = self.zonelist
        for zone in zonelist:
            self.debug("checking zone:"+zone.name)
            #use a single instance per zone for this test
            instance = zone.instances[0]
            for snap in self.snaps:
                self.debug("Checking volumes associated with snap:"+snap.id)
                for vol in snap.new_vol_list:
                    self.debug("Checking volume:"+vol.id+" status:"+vol.status)
                    if (vol.zone == zone.name) and (vol.status == "available"):
                        instance.attach_euvolume(vol, timeout=timeout)
                        instance.md5_attached_euvolume(vol, timepergig=timepergig)
                        if vol.md5 != snap.md5:
                            self.debug("snap:"+str(snap.md5)+" vs vol:"+str(vol.md5))
                            self.debug("Volume:"+str(vol.id)+" MD5:"+str(vol.md5)+" != Snap:"+str(snap.id)+" MD5:"+str(snap.md5))
                            raise Exception("Volume:"+str(vol.id)+" MD5:"+str(vol.md5)+" != Snap:"+str(snap.id)+" MD5:"+str(snap.md5))
                        self.debug("Successfully verified volume:"+str(vol.id)+" to snapshot:"+str(snap.id))
        self.endsuccess()
        
    def create_vols_from_snap_in_different_zone(self,zonelist=None, timepergig=300):
        testmsg =   """
                    Attempts to create a volume from each snapshot contained in each zone's list of snapshots.
                    This test attempts to create volumes from snapshots who's original volume is "NOT" in this 
                    same zone
                    """
        testmsg = testmsg+"\nVariables provided:\nzonelist:"+str(zonelist)
        self.startmsg()
        if zonelist is None:
            zonelist = self.zonelist
        for zone in zonelist:
            for snap in self.snaps:
                if snap.zone != zone:
                    newvol = euvolume.EuVolume.make_euvol_from_vol(self.tester.create_volume(zone.name,size=0, snapshot=snap, timepergig=timepergig))
                    zone.volumes.append(newvol)
                    snap.new_vol_list.append(newvol)
        self.endsuccess()
        
    ''' 
    def snap_vol_during_io_test(self, zonelist,None,timepergig=600):
        testmsg =   """
                    Attempts to create a snapshot from a volume while under some amount of test produced I/O. 
                    Attach a volume to an instance, begin reading and writing to the volume. Snapshot the volume. 
                    returns the elapsed time of snapshot creation. 
                    """
    ''' 
                
        
    def run_ebs_basic_test_suite(self):  
        self.testlist = [] 
        testlist = self.testlist
        
        #create first round of volumes
        testlist.append(self.create_testcase_from_method(self.create_vols_per_zone))
        #launch instances to interact with ebs volumes
        testlist.append(self.create_testcase_from_method(self.create_test_instances_for_zones))
        #attach first round of volumes
        testlist.append(self.create_testcase_from_method(self.attach_all_avail_vols_to_instances_in_zones))
        #attempt to delete attached volumes, should not be able to
        testlist.append(self.create_testcase_from_method(self.negative_delete_attached_volumes_in_zones))
        #attempt to attach a volume which is already attached, should not be able to
        testlist.append(self.create_testcase_from_method(self.negative_attach_in_use_volume_in_zones))
        #create second round of volumes
        testlist.append(self.create_testcase_from_method(self.create_vols_per_zone))
        #attach second round of volumes
        testlist.append(self.create_testcase_from_method(self.attach_all_avail_vols_to_instances_in_zones))
        #reboot instances and confirm volumes remain attached
        testlist.append(self.create_testcase_from_method(self.reboot_instances_in_zone_verify_volumes))
        #detach 1 volume leave the 2nd attached
        testlist.append(self.create_testcase_from_method(self.detach_volumes_in_zones))
        #attempt to create volumes from snaps, attach and verify md5 in same zone it was created in
        testlist.append(self.create_testcase_from_method(self.create_snapshots_all_vols_in_zone))
        #attempt to create volumes of each snap within the same zone they were originally created in
        testlist.append(self.create_testcase_from_method(self.create_vols_from_snap_in_same_zone))
        #attempt to verify integrity of the volumes  by attaching to instance and checking md5 against original
        testlist.append(self.create_testcase_from_method(self.attach_new_vols_from_snap_verify_md5))  
        if (len(self.zonelist) > 1 ):
            #attempt to create volumes from     s, attach and verify md5 in a different zone than it was created in        
            testlist.append(self.create_testcase_from_method(self.create_vols_from_snap_in_different_zone))
            #verify the integrity of the new volumes by attaching to instance and checking md5 against original
            testlist.append(self.create_testcase_from_method(self.attach_new_vols_from_snap_verify_md5))
        self.run_test_case_list(testlist)
        
                
    
    def restart_clc_makevol(self, zonelist=None):
        '''
        Test start/stop cloud service recovery as it pertains to storage
        ''' 
        if zonelist is None:
            zonelist = self.zonelist
    
        clc = self.tester.service_manager.get_enabled_clc()
        clc.stop()
        clc.start()
        self.tester.service_manager.wait_for_service(clc)
        for zone in zonelist:
            start = time.time()
            elapsed = 0
            sc = None
            while (sc is None) and (elapsed < 360):
                self.debug("waiting for sc in zone:"+str(zone.name)+" elapsed:"+str(elapsed))
                elapsed = int(time.time()-start)
                sc = zone.partition.get_enabled_sc()
                time.sleep(5)
        #wait a bit before attempting a volume
        if sc is None:
            raise Exception("Elapsed:"+str(elapsed)+"Couldn't find enabled sc for zone"+str(zone.name))
        self.debug("SC gone to enabled after "+str(elapsed)+" seconds")
        time.sleep(30)
        self.create_vols_per_zone()
        self.debug("Done creating volumes, now delete em...")
        for zone in zonelist:
            self.debug("Deleting volumes in zone:"+str(zone.name))
            for volume in zone.volumes:
                self.debug("Deleting volume:"+str(volume.id))
                volume.delete()
                start = time.time()
                elapsed = 0
                while ( volume.status == "deleted") and (elapsed < 100 ):
                    volume.update()
                    elapsed = int(time.time()- start)
                    self.debug("Waiting for volume:"+str(volume)+" to delete. elapsed:"+str(elapsed))
                    time.sleep(5)
                if ( volume.status == "deleted") :
                    raise Exception("Volume:"+str(volume)+" failed to delete. state:"+str(volume.status))
        
        
    def spin_restart(self, count=1000):
        '''
        Churn test wrapping cloud service start/stop storage tests
        '''
        for x in xrange(0,count):
            self.startmsg("test attempt("+str(x)+")")
            self.restart_clc_makevol()
            self.endsuccess("test attempt("+str(x)+")")
    
    
    
    def test_max_volume_size_property(self, volumes=None, maxsize=1, zones=None):
        if zones is None or zones == []:
            zones = self.zones
        
    def clean_created_resources(self, zonelist=None, timeout=360):
        self.terminate_test_instances_for_zones(zonelist=zonelist, timeout=timeout)
        self.delete_volumes_in_zones(zonelist=zonelist, timeout=timeout)
        self.delete_snapshots_in_zones(zonelist=zonelist,  timeout=timeout)
    '''  
    def create_testcase_from_method(self, method, *args):
        testcase =  EutesterTestCase(method, args)
        return testcase
    '''
        
    def print_test_list_results(self,list=None,printmethod=None):
        if list is None:
            list=self.testlist
        if printmethod is None:
            printmethod = self.debug
        for testcase in list:
            printmethod('-----------------------------------------------')
            printmethod(str("TEST:"+str(testcase.name)).ljust(50)+str(" RESULT:"+testcase.result).ljust(10)+str(' Time:'+str(testcase.time_to_run)).ljust(0))
            if testcase.result == EutesterTestResult.failed:
                printmethod('Error:'+str(testcase.error))
    

    def run_test_case_list(self, list, eof=True, clean_on_exit=True, printresults=True):
        '''
        wrapper to execute a list of ebsTestCase objects
        '''
        try:
            for test in list:
                self.debug('Running list method:'+str(test.name))
                try:
                    test.run()
                except Exception, e:
                    self.debug('Testcase:'+ str(test.name)+' error:'+str(e))
                    if eof:
                        raise e
                    else:
                        pass
        finally:
            try:
                 if clean_on_exit:
                    self.clean_created_resources()
            except: pass
            if printresults:
                try:
                    ebssuite.print_test_list_results()
                except:pass
                
        
            
    
if __name__ == "__main__":
    ## If given command line arguments, use them as test names to launch

    ## If given command line arguments, use them as test names to launch
    parser = argparse.ArgumentParser(prog="ebs_basic_test.py",
                                     version="Test Case [ebs_basic_test.py] Version 0.1",
                                     description="Attempts to tests and provide info on focused areas related to\
                                     Eucalyptus EBS related functionality.",
                                     usage="%(prog)s --credpath=<path to creds> [--xml] [--tests=test1,..testN]")
    
    
    
    parser.add_argument('--emi', 
                        help="pre-installed emi id which to execute these tests against", default=None)
    parser.add_argument('--credpath', 
                        help="path to credentials", default=None)
    parser.add_argument('--zone', 
                        help="zone to use in this test, defaults to testing all zones", default=None)
    parser.add_argument('--password', 
                        help="password to use for machine root ssh access", default='foobar')
    parser.add_argument('--keypair', 
                        help="keypair to use when launching instances within the test", default=None)
    parser.add_argument('--group', 
                        help="group to use when launching instances within the test", default=None) 
    parser.add_argument('--config',
                       help='path to config file', default='../input/2btested.lst') 
    parser.add_argument('--xml', 
                        help="to provide JUnit style XML output", action="store_true", default=False)
    
    parser.add_argument('--tests', nargs='+', 
                        help="test cases to be executed", 
                        default= ['run_test_suite'])
    
    args = parser.parse_args()
    #if file was not provided or is not found
    if not os.path.exists(args.config):
        print "Error: Mandatory Config File '"+str(args.config)+"' not found."
        parser.print_help()
        exit(1)
    ebssuite = EbsTestSuite(zone=args.zone, config_file= args.config, password=args.password,credpath=args.credpath, keypair=args.keypair, group=args.group, image=args.emi)
    kbtime=time.time()
    try:
       ebssuite.run_ebs_basic_test_suite()
    except KeyboardInterrupt:
        ebssuite.debug("Caught keyboard interrupt...")
        if ((time.time()-kbtime) < 2):
            ebssuite.clean_created_resources()
            ebssuite.debug("Caught 2 keyboard interupts within 2 seconds, exiting test")
            ebssuite.clean_created_resources()
            raise
        else:          
            ebssuite.print_test_list_results()
            kbtime=time.time()
            pass     
    except Exception, e:
        raise e
        exit(1)
    exit(0)
        



  
