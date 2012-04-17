#! ../share/python_lib/matt_dev/bin/python
'''
Test Summary: 

-create a volume (do this first)
-run an instance (do this second, if this fails at least we know we could create a vol)

Usage Tests: 
-negative -attempt to attach a volume to an instance in a separate cluster. 
-attach a single volume to an instance in the zones given, write random data and calc md5 of volumes
-negative:attempt to delete the attached instance, should fail
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
-tbd

'''
from eucaops import Eucaops
from eutester import euinstance, euvolume
from boto.ec2.snapshot import Snapshot
import re
import time
import unittest
import inspect
import gc





class TestZone():
    def __init__(self, partition):
        self.partition = partition 
        self.name = partition.name
        self.instances = []
        self.volumes = []
    
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
    
        
        
        
        


class EbsTests():
    
    tester = None
    zonelist = []
    snaps = []
    keypair = None
    group = None
    multicluster=False
    image = None
    
    def __init__(self, tester=None, zone=None, config_file='../input/2b_tested.lst', volumes=None, keypair=None, group=None, image=None, eof=1):
        if tester is None and self.tester is None:
            self.tester = Eucaops( config_file=config_file)
        else:
            self.tester = tester
        tester.exit_on_fail = eof
        
        self.image = image
            
        #create some zone objects and append them to the zonelist
        if zone is not None:
            self.zone = TestZone(zone)
            self.zonelist.append(self.zone)
        else: 
            for zone in self.tester.service_manager.partitions.keys():
                partition = tester.service_manager.partitions.get(zone)
                tzone = TestZone(partition)
                self.zonelist.append(tzone)
                self.multicluster=True
        
        #If the list of volumes passed in looks good, sort them into the zones
        if self.volumes_list_check(volumes):
            self.sort_volumes(volumes)
            
        #Setup our security group for later use
        if (group is not None):
            self.group = group
        else:
            group_name='EbsTestGroup'
            
            try:
                self.group = tester.add_group(group_name)
                tester.authorize_group_by_name(self.group.name)
                tester.authorize_group_by_name(self.group.name,protocol="icmp",port=-1)
            except Exception, e:    
                raise Exception("Error when setting up group:"+str(group_name)+", Error:"+str(e))   
        
    
        #Setup the keypairs for later use
        try:
            if (keypair is not None):
                self.keypair = keypair
            else:     
                keys = tester.get_all_current_local_keys()
                if keys != []:
                    self.keypair = keys[0]
                else:
                    self.keypair = keypair = tester.add_keypair('ebs_test_key-' + str(time.time()))
        except Exception, ke:
            raise Exception("Failed to find/create a keypair, error:" + str(ke))
        
        
            
    
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
        
    



        
    def debug(self,msg,traceback=1):
        msg = str(msg)       
        curframe = None
        '''
        for x in xrange(0,100):
            frame = inspect.currentframe(x)
            print "trying frame["+str(x)+"]"
            if frame.f_back is None:
                print "this frame is none, will use frame["+str(x-1)+"] instead"
                break
            else:
                curframe = frame
                lineno = curframe.f_lineno
        '''
        curframe = inspect.currentframe(traceback)
        lineno = curframe.f_lineno
        self.curframe = curframe
        frame_code  = curframe.f_code
        frame_globals = curframe.f_globals
        functype = type(lambda: 0)
        funcs = []
        for func in gc.get_referrers(frame_code):
            if type(func) is functype:
                if getattr(func, "func_code", None) is frame_code:
                    if getattr(func, "func_globals", None) is frame_globals:
                        funcs.append(func)
                        if len(funcs) > 1:
                            return None
            cur_method= funcs[0].func_name if funcs else ""
        for line in msg.split("\n"):
            self.tester.debug("("+str(cur_method)+":"+str(lineno)+"): "+line.strip() )
       
    
    
 
        
        
        
        
    def status(self,msg,traceback=2, b=0,a=0):
        alines = ""
        blines = ""
        for x in xrange(0,b):
            blines=blines+"\n"
        for x in xrange(0,a):
            alines=alines+"\n"
        line = "-------------------------------------------------------------------------"
        out = blines+line+"\n"+msg+"\n"+line+alines
        self.debug(out, traceback=traceback)  

        
    def startmsg(self,msg=""):
        msg = "- STARTING - " + msg
        self.status(msg, traceback=3)
        
    def endsuccess(self,msg=""):
        msg = "- SUCCESS ENDED - " + msg
        self.status(msg, traceback=3)
    
    
        

        
    def sort_volumes(self, volumes):
        for vol in volumes:
            for zone in self.zonelist:
                if vol.zone == zone.name:
                    zone.volumes.append(vol)

        
    def create_vols_per_zone(self, zonelist=None, volsperzone=1, size=1, snapshot=None):
        testmsg =   """
                    Intention of this test is to verify creation of volume(s) per zone given.
                    Upon successful creation the volumes will be appeneded to a volumes list
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
                vol = euvolume.EuVolume.make_euvol_from_vol(self.tester.create_volume(zone, size, snapshot))
                testzone.volumes.append(vol)
                self.debug('create_vols_per_zone created  vol('+str(x)+') zone:'+str(zone)+' vol:'+str(vol.id))
            
        self.endsuccess()      
                
          
    def create_test_instances_for_zones(self, zonelist=None, image=None, keypair=None, group=None, vmtype=None):
        testmsg = """
                    Create an instance within each TestZone object in zonelist to help test ebs functionality.
                  """
        testmsg = testmsg+"\nVariables provided:\nzonelist:"+str(zonelist)+"\nimage:"+str(image)+"\nkeypair:"+str(keypair)+"\ngroup:"+str(group)+"\nvmtype:"+str(vmtype)
        
        self.startmsg(testmsg)
        if image is not None:
            image = self.tester.get_emi(location=image)
        if group is None:
            group = self.group
        if keypair is None:
            keypair = self.keypair
                
        if zonelist is None:
            zonelist = self.zonelist
            
        for testzone in zonelist:
            zone = testzone.name
            inst = self.tester.run_instance(image=image, keypair=keypair.name, group=group, type=vmtype, zone=zone).instances[0]
            testzone.instances.append(inst)
            self.debug('Created instance: ' + str(inst.id)+" in zone:"+str(zone))
        self.endsuccess()
            
    def attach_all_avail_vols_to_instances_in_zones(self, zonelist=None, timeout=90):
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
                    instance.vol_write_random_data_get_md5(volume,timepergig=120)
        self.endsuccess()
                    
                        
    def negative_delete_attached_volumes_in_zones(self,zonelist=None, timeout=60):
        testmsg =   """
                    Attempts to delete attached volumes, this is a negative test as this should fail. 
                    """
        testmsg = testmsg + "\nVariables provided:\nzonelist:"+str(zonelist)+"\ntimeout:"+str(timeout)
        self.startmsg(testmsg)
        if zonelist is None:
            zonelist = self.zonelist
        instance = euinstance.EuInstance()
        volume = euvolume.EuVolume()
        for zone in zonelist:
            for instance in zone.instances:
                badvols = instance.get_unsynced_volumes() 
                if (badvols is not None) and (badvols != []):
                    self.debug("negative_delete_attached_volumes_in_zones, failed")
                    raise Exception("Unsync volumes found on:"+str(instance.id)+"\n"+"".join(badvols))
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
                        
    def reboot_instances_in_zone_verify_volumes(self,zonelist=None,waitconnect=30, timeout=300):
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
        
    def detach_volumes_in_zones(self,zonelist=None, timeout=90, volcount=1):
        testmsg =   """
                    Attempts to detach volcount volumes from each instance in the provided zonelist. 
                    Attempts to verify detached volume state on both the cloud and the guest
                    by default will attempt to detach a single volume from each instance
                    """
        testmsg = testmsg + "\nVariables provided:\nzonelist:"+str(zonelist)+"\ntimeout:"+str(timeout)+"\nvolcount:"+str(volcount)
                    
        self.startmsg(testmsg)
        if zonelist is None:
            zonelist = self.zonelist
        instance = euinstance.EuInstance()
        for zone in zonelist:
            for instance in zone.instances:
                vc=0
                badvols = instance.get_unsynced_volumes() 
                if (badvols is not None) and (badvols != []):
                    self.debug("failed")
                    raise Exception("Unsync volumes found on:"+str(instance.id)+"\n"+"".join(badvols))
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
        self.endsuccess()
        
    def create_snapshots_all_vols_in_zone(self, zonelist=None, volstate="all"):
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
                    self.snaps.append(TestSnap.make_testsnap_from_snap(self.tester.create_snapshot(volume.id, description="ebstest", waitOnProgress=10),zone))
        self.endsuccess()
        
        
    def create_vols_from_snap_in_same_zone(self, zonelist=None):
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
                    newvol = euvolume.EuVolume.make_euvol_from_vol(self.tester.create_volume(zone.name, 0, snap))
                    zone.volumes.append(newvol)
                    snap.new_vol_list.append(newvol)
        self.endsuccess()
        
    def attach_new_vols_from_snap_verify_md5(self,zonelist=None, timeout=60,timepergig=120):
        testmsg =   """
                    Attempts to attach volumes which were created from snapshots and are not in use. 
                    After verifying the volume is attached and reported as so by cloud and guest, 
                    this test will attempt to compare the md5 sum of the volume to the md5 contained in 
                    the snapshot which representst the md5 of the original volume. 
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
                        instance.attach_euvolume(vol)
                        instance.md5_attached_euvolume(vol, timepergig=timepergig)
                        if vol.md5 != snap.md5:
                            self.debug("snap:"+str(snap.md5)+" vs vol:"+str(vol.md5))
                            self.debug("Volume:"+str(vol.id)+" MD5:"+str(vol.md5)+" != Snap:"+str(snap.id)+" MD5:"+str(snap.md5))
                            raise Exception("Volume:"+str(vol.id)+" MD5:"+str(vol.md5)+" != Snap:"+str(snap.id)+" MD5:"+str(snap.md5))
                        self.debug("Successfully verified volume:"+str(vol.id)+" to snapshot:"+str(snap.id))
        self.endsuccess()
        
    def create_vols_from_snap_in_different_zone(self,zonelist=None):
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
                    newvol = euvolume.EuVolume.make_euvol_from_vol(self.tester.create_volume(zone.name,0, snap))
                    zone.volumes.append(newvol)
                    snap.new_vol_list.append(newvol)
        self.endsuccess()
        
        
        
                    
               
        
    def quick_test(self):
        self.create_vols_per_zone()
        self.create_test_instances_for_zones()
        self.attach_all_avail_vols_to_instances_in_zones()   
        self.negative_delete_attached_volumes_in_zones()
        self.create_vols_per_zone()
        self.attach_all_avail_vols_to_instances_in_zones()
        self.reboot_instances_in_zone_verify_volumes()
        #detach 1 volume leave the 2nd attached
        self.detach_volumes_in_zones(volcount=1)
        #attempt to create volumes from snaps, attach and verify md5 in same zone it was created in
        self.create_snapshots_all_vols_in_zone()
        self.create_vols_from_snap_in_same_zone()
        self.attach_new_vols_from_snap_verify_md5()  
        if (len(self.zonelist) > 1 ):
            #attempt to create volumes from     s, attach and verify md5 in a different zone than it was created in        
            self.create_vols_from_snap_in_different_zone()
            self.attach_new_vols_from_snap_verify_md5()
        
    
        
    
    '''
    def cleanup(self):
        for zone in self.zonelist:
            for instance in zone.instances:
    '''         
    
    def restart_clc_makevol(self, zonelist=None):
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
            while (sc is None) and (elapsed < 300):
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
        
        
    def spin_restart(self):
        for x in xrange(0,1000):
            self.startmsg("test attempt("+str(x)+")")
            self.restart_clc_makevol()
            self.endsuccess("test attempt("+str(x)+")")
    
    
    
    def test_max_volume_size_property(self, volumes=None, maxsize=1, zones=None):
        if zones is None or zones == []:
            zones = self.zones
        
     

    def suite(self):
        tests = ['test1_Instance', 'test2_ElasticIps', 'test3_MaxInstances', 'test4_LargeInstance','test5_MetaData', 'test6_Reboot']
        return unittest.TestSuite(map(EbsTests, tests))
    
if __name__ == "__main__":
    unittest.main()
