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
import copy
import types
import time
import os

from eucaops import Eucaops
from eutester import euinstance
from eutester.eutestcase import EutesterTestCase
from eucaops import ec2ops
from eutester.eutestcase import TestColor

class TestZone():
    def __init__(self, partition):
        self.partition = partition 
        self.name = partition
        self.instances = []
        self.volumes = []
        
    def __str__(self):
        return self.name

class EbsTestSuite(EutesterTestCase):

    def __init__(self, 
                 name='ebs test suite',
                 tester=None,
                 **kwargs):

        self.setuptestcase(name=name)
        self.setup_parser(testname='ebs test suite',
                    description="Attempts to test and provide info on focused areas related to Eucalyptus EBS related functionality.",
                    testlist=False)
        self.parser.add_argument('--reboot_timeout',dest='waitconnect',
                                 help='Time to wait before trying to connect to '
                                      'rebooted guests',
                                 default=30)
        self.parser.add_argument('--group',
                                 dest='group',
                                 help='Security group to use in test',
                                 default=None)
        self.parser.add_argument('--waitconnect',
                                 dest='waitconnect',
                                 help='Time to wait before attempting to '
                                      'connect to a rebooted instance',
                                 default=30)
        self.parser.add_argument('--wait_on_progress',
                                 dest='wait_on_progress',
                                 help='Time to wait for incremental '
                                      'progress during snapshot creation',
                                 default=20)
        self.parser.add_argument('--root_device_type',dest='root_device_type',
                                 help='Root device type for instance used '
                                      'in test. Default: isntance-store',
                                 default='instance-store')
        self.parser.add_argument('--instance_password',
                                 help="Instance password for ssh session if not "
                                      "key enabled", default=None)
        self.parser.add_argument('--no_clean_on_exit', dest='clean_on_exit',
                                 help="Clean up resources created in this test. "
                                      "Default=True",
                                 action='store_false', default=True)
        self.parser.add_argument('--exit_on_failure', dest='exit_on_failure',
                                 help="End test on first test unit failure "
                                    "Default=False",
                                 action='store_true', default=False)
        self.parser.add_argument('--volumes', dest='volumes',
                                 help="Comma separated list of volumes to use "
                                      "in this test",
                                 default="")
        self.get_args()
             # Allow __init__ to get args from __init__'s kwargs or through command line parser...
        for kw in kwargs:
            print 'Setting kwarg:'+str(kw)+" to "+str(kwargs[kw])
            self.set_arg(kw ,kwargs[kw])
        self.show_args()
        for key in self.args.__dict__:
            if key != 'args':
                print 'Setting local value:' + str(key) + ", value:" + str(self.args.__dict__[key])
                setattr(self,key, self.args.__dict__[key])

        else:
            self.show_args()
            self.multicluster = False
            self.zonelist = []
            self.snaps = []
            if tester is None:
                self.tester = Eucaops( config_file=self.configfile,password=self.password,credpath=self.credpath)
            else:
                self.tester = tester
            if self.emi:
                self.image = self.tester.get_emi(emi=self.emi)
            else:
                self.image = self.tester.get_emi(root_device_type=self.root_device_type)
            #create some zone objects and append them to the zonelist
            if self.zone:
                self.zone = TestZone(self.zone)
                self.zonelist.append(self.zone)
            else:
                self.setup_testzones()

            #If the list of volumes passed in looks good, sort them into the zones
            if self.volumes_list_check(self.volumes):
                self.sort_volumes(self.volumes)

            #Setup our security group for later use
            if self.group:
                if isinstance(self.group, types.StringType):
                    self.group = self.tester.add_group(self.group)
            else:
                group_name='EbsTestGroup'
                try:
                    self.group = self.tester.add_group(group_name,fail_if_exists=False)
                    self.tester.authorize_group_by_name(self.group.name)
                    self.tester.authorize_group_by_name(self.group.name,protocol="icmp",port=-1)
                except Exception, e:
                    self.debug(self.tester.get_traceback())
                    raise Exception("Error when setting up group:"+str(group_name)+", Error:"+str(e))

        #Setup the keypairs for later use
        if not self.instance_password:
            try:
                if not self.keypair:
                    keys = self.tester.get_all_current_local_keys() 
                    if keys:
                        self.keypair = keys[0]
                    else:
                        self.keypair = keypair = self.tester.add_keypair('ebs_test_key-' + str(time.time()))
            except Exception, ke:
                raise Exception("Failed to find/create a keypair, error:" + str(ke))
        print "###########################################################"
        print "Done with EBS SUITE INIT"
        print "###########################################################"
        
    def setup_testzones(self):
        for zone in self.tester.get_zones():
                tzone = TestZone(zone)
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
        """
        Description:
                    Intention of this test is to verify creation of volume(s) per zone given.
                    Upon successful creation the volumes will be appended to a volumes list
                    for the zone it was created in. 
                    These volumes may be later used if in later ebstests suite tests. 
        """    
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        for testzone in zonelist:
            zone = testzone.name
            vols = self.tester.create_volumes(zone, size=size, count=volsperzone, snapshot=snapshot,timepergig=timepergig)
            for vol in vols:
                vol.add_tag('ebstestsuite_created')
            testzone.volumes.extend(vols)
            self.debug('create_vols_per_zone created vols('+str(len(vols))+') zone:'+str(zone))
            
           
            
          
    def create_test_instances_for_zones(self, zonelist=None, image=None, keypair=None, username='root', instance_password=None, group=None, vmtype=None,count=1):
        """
        Description:
                    Create an instance within each TestZone object in zonelist to help test ebs functionality.
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        if image is not None:
            if isinstance(image,types.StringTypes):
                image = self.tester.get_emi(emi=image)    
        else:
            image = self.image
        if group is None:
            group = self.group
        if keypair is None:
            keypair = self.keypair
        instance_password = instance_password or self.instance_password
                
        vmtype = vmtype or self.vmtype
        if keypair:
            keyname = keypair.name
        else:
            keyname = None
            
        for testzone in zonelist:
            zone = testzone.name
            instances = self.tester.run_image( image=image,
                                                keypair=keyname,
                                                group=group,
                                                username=username,
                                                password=instance_password,
                                                user_data=self.user_data,
                                                type=vmtype,
                                                zone=zone,
                                                min=count,
                                                max=count)

            for inst in instances:
                testzone.instances.append(inst)
            self.debug('Created instance: ' + str(inst.id)+" in zone:"+str(zone))
        #self.endsuccess()
    
    def terminate_test_instances_for_zones(self, zonelist=None, timeout=480):
        if zonelist is None:
            zonelist = self.zonelist
        for zone in zonelist:
            for instance in zone.instances:
                self.tester.terminate_single_instance(instance, timeout)
                zone.instances.remove(instance)
                
    def terminate_instances_in_zones_verify_volume_detach(self,zonelist=None,timeout=480):
        """
        Description:
                  Iterates over all instances in this testcase's zonelist attempts to terminate the instances,
                  and verify the attached volumes go to available after the instances are terminated. 
        """
        instance = euinstance.EuInstance()
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        for zone in zonelist:
            for instance in zone.instances:
                instance.terminate_and_verify(verify_vols=True,timeout=timeout)
                zone.instances.remove(instance)

    def negative_attach_in_use_volume_in_zones(self,zonelist=None,timeout=480):
        """
        Description:
                    Iterates though zones and attempts to attach already attached volumes to instances within each zone.  
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        instance = euinstance.EuInstance()
        for zone in zonelist:
            tested = 0
            for volume in zone.volumes:
                volume.update()
                if (volume.status == "in-use"):
                    tested += 1
                    for instance in zone.instances:
                        try:
                            #This should fail
                            instance.attach_euvolume(volume,timeout=timeout)
                        except Exception, e:
                            #If it failed were good
                            self.debug("negative_attach_in_use_volume_in_zones Passed. Could not attach in-use volume")
                            #self.endsuccess()
                            pass
                        else:
                            #The operation did fail, but this test did
                            raise Exception("negative_attach_in_use_volume_in_zones failed volume attached")
            if not tested:
                raise Exception("No attached volumes found to test against")
                
    
    def attach_all_avail_vols_to_instances_in_zones(self, zonelist=None, timeout=480, overwrite=False):
        """
        Description:
                    Iterates though zones and attempts to attach volumes to an instance within each zone.  
                    
        :parram zonelist: list of zones to include in test
        :param timeout: timeout used for attach volume method
        :param overwrite: boolean to indicate whether a non-zero filled volume should have new unique data prepended for md5sum. 
                          This should be used when zero fill volume property is not in use upon volume first attach. 
                          It should not be used after the 1st attach and volume has been converted to a euvolume within this test. 
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("attach_all_avail_vols_to_instances_in_zones: Zonelist is empty")
        for zone in zonelist:
            if not zone.volumes:
                raise Exception('attach_all_avail_vols_to_instances_in_zones: Zone.volumes is empty')
            if not zone.instances:
                raise Exception('attach_all_avail_vols_to_instances_in_zones: Instance list is empty')
            i=0
            for volume in zone.volumes:
                volume.update()
                if (volume.status == "available"):
                        if i > (len(zone.instances)-1):
                            i = 0
                        self.debug("Attempting to attach to "+str(i)+"/"+str(len(zone.instances))+" instances in zone:"+str(zone))
                        instance = zone.instances[i]
                        try:
                            instance.attach_euvolume(volume,timeout=timeout, overwrite=overwrite)
                        except ec2ops.VolumeStateException, vse:
                            self.status("This is a temp work around for testing, this is to avoid bug euca-5297"+str(vse),
                                        testcolor=TestColor.get_canned_color('failred'))
                            time.sleep(10)
                            self.debug('Monitoring volume post VolumeStateException...')
                            volume.eutest_attached_status = None
                            self.tester.monitor_euvolumes_to_status([volume],status='in-use',attached_status='attached',timeout=60)
                        except Exception, e:
                            self.debug("attach_all_vols_to_instances_in_zones failed to attach volume")
                            raise e
                        i += 1
            
                    
                        
    def negative_delete_attached_volumes_in_zones(self,zonelist=None, timeout=60):
        """
        Description:
                    Negative test case. Attempts to delete attached volumes for each euinstace
                    in each zone per zone list provided. Confirms that volumes did NOT delete while in use/attached.            
        """
        #instance = euinstance.EuInstance()
        #volume = euvolume.EuVolume()
      
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        
        for zone in zonelist:
            if not zone.instances:
                raise Exception("No Instances in zone:"+str(zone.name))
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
                if not instance.attached_vols:
                    raise Exception("No attached volumes found for test")
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
                   
                        
    def reboot_instances_in_zone_verify_volumes(self,zonelist=None,waitconnect=30, timeout=480):
        """
        Description:
                    Attempts to iterate through each instance in each zone and reboot the instance(s). 
                    Attempts to verify the attached volume state post reboot. 
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        instance = euinstance.EuInstance()
        for zone in zonelist:
            if not zone.instances:
                raise Exception("No instances in zone:"+str(zone.name))
            for instance in zone.instances:
                instance.reboot_instance_and_verify(waitconnect=waitconnect, timeout=timeout, checkvolstatus=True)
        #self.endsuccess()
        
    def detach_volumes_in_zones(self,zonelist=None, timeout=480, volcount=1, eof=False):
        """
        Description:
                    Attempts to detach volcount volumes from each instance in the provided zonelist. 
                    If volcount is None or 0, will attempt to detach all volumes from all instances. 
                    Attempts to verify detached volume state on both the cloud and the guest
                    by default will attempt to detach a single volume from each instance
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        #instance = euinstance.EuInstance()
        for zone in zonelist:
            if not zone.instances:
                raise Exception("No instances in zone:"+str(zone.name))
            for instance in zone.instances:
                vc=0
                badvols = instance.get_unsynced_volumes() 
                if (badvols is not None) and (badvols != []):
                    self.debug("failed")
                    errlist=[]
                    for badvol in badvols:
                        errlist.append(str(badvol.id))
                    raise Exception("Unsync volumes found on:"+str(instance.id)+"\n"+" ".join(errlist))
                errmsg=""
                for volume in instance.attached_vols:
                    #detach number of volumes equal to volcount
                    if volcount and vc >= volcount:
                        break
                    else:
                        vc += 1
                        try:
                            instance.detach_euvolume(volume, timeout=timeout)
                        except Exception, e: 
                            self.debug("fail. Could not detach Volume:"+str(volume.id)+"from instance:"+str(instance.id))
                            if eof:
                                raise e
                            else:
                                errmsg += "\nCould not detach Volume:"+str(volume.id)+"from instance:"+str(instance.id)+",err:"+str(e)
                            
        if errmsg:
            raise Exception(errmsg)
        
    def detach_all_volumes_from_stopped_instances_in_zones(self,zonelist=None, timeout=480):
        """
        Description:
                    Attempts to detach volumes from instances while in the stopped state and
                    verify volumes are detached, and upon instance start verify that both guest
                    and cloud states are correct.
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        for zone in zonelist:
            if not zone.instances:
                raise Exception("No instances in zone:"+str(zone.name))
            for instance in zone.instances:
                if instance.block_device_mapping != 'ebs':
                    continue
                if not instance.attached_vols:
                    raise Exception('detach_all_volumes_from_stopped_instances_in_zones: No attached volumes for:'+str(instance.id))
                instance.stop_instance_and_verify()
                for vol in instance.attached_vols:
                    instance.detach_euvolume(vol, waitfordev=False)
                instance.start_instance_and_verify(checkvolstatus=True)
        #self.endsuccess()
    
    def delete_volumes_in_zones(self, zonelist=None, timeout=60):
        """
        Description:
                    Attempts to iterate over each zone and delete all test volumes.
        
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
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
        #self.endsuccess()
        
        
    def delete_snapshots_in_zones(self, zonelist=None,snaplist=None, timeout=300):
        """
        Description:
                    Attempts to iterate through zonelist, and delete all snapshots 
                    within that zone
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        if snaplist is None:
            snaplist = self.snaps
        for zone in zonelist:
            for snap in snaplist:
                if snap.eutest_volume_zone == zone:
                    self.tester.delete_snapshot(snap, timeout=timeout)
                    snaplist.remove(snap)
        #self.endsuccess()
        
                
        
        
    def create_snapshots_all_vols_in_zone(self, zonelist=None, volstate="all", wait_on_progress=None):
        """
        Description:
                    Attempts to iterate through each zone in zonelist, and create a snapshot from each volume
                    in the zone's volume list who's state matches volstate
                    
        """
        wait_on_progress = wait_on_progress or self.wait_on_progress
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        for zone in zonelist:
            if not zone.volumes:
                raise Exception("No volumes in zone:"+str(zone.name))
            for volume in zone.volumes:
                volume.update()
                if volstate == "all" or volume.status == volstate:
                    new_snap = self.tester.create_snapshot_from_volume(volume, description="ebstest", wait_on_progress=wait_on_progress)
                    new_snap.add_tag('ebstestsuite_created')
                    self.snaps.append(new_snap)
        #self.endsuccess()
        
        
    def create_vols_from_snap_in_same_zone(self, zonelist=None,timepergig=300):
        """
        Description:
                    Attempts to create a volume from each snapshot contained in each zone's list of snapshots.
                    This test attempts to create volumes from snapshots who's original volume is also in this
                    zone. 
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        for zone in zonelist:
            if not self.snaps:
                raise Exception("Create_Vols_from_snap_in_same_zone error: No snapshots available for test")
            zonesnaps = self.get_snaps_from_zone(self.snaps, zone)
            if not zonesnaps:
                raise Exception("No Snapshots from this test found in zone:"+str(zone))
            for snap in zonesnaps:
                self.debug("Creating volume from snap:"+str(snap.id))
                newvol = self.tester.create_volume(zone.name, size=0, snapshot=snap,timepergig=timepergig)
                newvol.add_tag('ebstestsuite_created')
                zone.volumes.append(newvol)
                snap.eutest_volumes.append(newvol)
        #self.endsuccess()
        
    def get_snaps_from_zone(self,snaplist, zone):
        retlist = []
        for snap in snaplist:
            self.debug(snap.id+", zone:"+str(zone)+" snap.eutest_volume_zone:"+str(snap.eutest_volume_zone))
            if str(snap.eutest_volume_zone).strip() == str(zone).strip():
                self.debug('Adding snap to retlist:'+str(snap.id))
                retlist.append(snap)
        return retlist
        
    def attach_new_vols_from_snap_verify_md5(self,zonelist=None, timeout=480,timepergig=480):
        """
        Description:
                    Attempts to attach volumes which were created from snapshots and are not in use. 
                    Iterates over test instances in zones for attaching the test volumes. 
                    After verifying the volume is attached and reported as so by cloud and guest, 
                    this test will attempt to compare the md5 sum of the volume to the md5 contained in 
                    the snapshot which represents the md5 of the original volume. 
                    This test accepts a timepergig value which is used to guesstimate a reasobale timeout while
                    waiting for the md5 operation to be executed. 
        """
        
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("attach_new_vols_from_snap_verify_md5: Zonelist is empty")
        for zone in zonelist:
            self.debug("checking zone:"+zone.name)
            
            if not self.snaps:
                raise Exception('attach_new_vols_from_snap_verify_md5: self.snaps is None')
            for snap in self.snaps:
                self.debug("Checking volumes associated with snap:"+snap.id)
                if not snap.eutest_volumes:
                    raise Exception('attach_new_vols_from_snap_verify_md5: snap '+str(snap.id)+" eutest_volumes is None")
                i = 0
                for vol in snap.eutest_volumes:
                    self.debug("Checking volume:"+vol.id+" status:"+vol.status)
                    if (vol.zone == zone.name) and (vol.status == "available"):
                        if i > len(zone.instances)-1:
                            i = 0
                        instance = zone.instances[i]
                        try:
                            instance.attach_euvolume(vol, timeout=timeout)
                        except ec2ops.VolumeStateException, vse:
                            self.status("This is a temp work around for testing, this is to avoid bug euca-5297"+str(vse),
                                        testcolor=TestColor.get_canned_color('failred'))
                            time.sleep(10)
                            self.debug('Monitoring volume post VolumeStateException...')
                            vol.eutest_attached_status = None
                            self.tester.monitor_euvolumes_to_status([vol],status='in-use',attached_status='attached',timeout=60)
                        except Exception, e:
                            self.debug("Failed to attach volume: " + str(vol.id) + "to instance:" + str())
                            raise e
                        instance.md5_attached_euvolume(vol, timepergig=timepergig)
                        if vol.md5 != snap.eutest_volume_md5:
                            self.debug("snap:"+str(snap.eutest_volume_md5)+" vs vol:"+str(vol.md5))
                            self.debug("Volume:"+str(vol.id)+" MD5:"+str(vol.md5)+" != Snap:"+str(snap.id)+" MD5:"+str(snap.eutest_volume_md5))
                            raise Exception("Volume:"+str(vol.id)+" MD5:"+str(vol.md5)+" != Snap:"+str(snap.id)+" MD5:"+str(snap.eutest_volume_md5))
                        self.debug("Successfully verified volume:"+str(vol.id)+" to snapshot:"+str(snap.id))
                        i += 1
        #self.endsuccess()
        
    def create_vols_from_snap_in_different_zone(self,zonelist=None, timepergig=300):
        """
        Description:         
                    Attempts to create a volume from each snapshot contained in each zone's list of snapshots.
                    This test attempts to create volumes from snapshots who's original volume is "NOT" in this 
                    same zone
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        for zone in zonelist:
            for snap in self.snaps:
                if snap.eutest_volume_zone != zone:
                    newvol = self.tester.create_volume(zone.name,size=0, snapshot=snap, timepergig=timepergig)
                    newvol.add_tag('ebstestsuite_created')
                    zone.volumes.append(newvol)
                    snap.eutest_volumes.append(newvol)
        #self.endsuccess()
        
    
    def consecutive_snapshot_to_vol_verify_md5s(self,
                                                zonelist=None, 
                                                count=5, 
                                                volmaxsize=1, 
                                                delay=0, 
                                                tpg=300,
                                                delete_to=120,
                                                poll_progress=60,
                                                attach_timeout=480):
        """
        Description:
                   Attempts to create a 'count' number of snapshots consecutively with a delay of 'delay'
                   between each creation attempt. If snapshot % progress does not increase within 'wait_on_progress'
                   10 second poll intervals, test will fail. IF snapshots are successfully created. Then they will
                   each have a volume created, and attached to an instance to verify the md5 against the original volume. 
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        zone = TestZone
        #vol = euvolume.EuVolume
        instance = euinstance.EuInstance
        for zone in zonelist:
            snaps =[]
            vols = []
            createdvols = []
            self.status('STARTING ZONE:'+str(zone.name))
            if not zone.instances or not zone.volumes:
                raise Exception("Zone "+str(zone.name)+", did not have at least 1 volume and 1 instance to run test")
            instance = zone.instances[0]
            for vol in zone.volumes:
                if vol.size <= volmaxsize:
                    break
            if vol.size > volmaxsize:
                raise Exception("Could not find volume in zone "+str(zone.name)+" <= volmaxsize of:"+str(volmaxsize))
            self.status("Attempting to create "+str(count)+" snapshots in zone:"+str(zone.name)+"...")
            snaps = self.tester.create_snapshots(vol, count=count, delay=delay, wait_on_progress=poll_progress)
            self.debug('Finished creating '+str(count)+' snapshots in zone:'+str(zone.name)+', now creating vols from them')
            try:
                for snap in snaps:
                    new_vols = self.tester.create_volumes(zone,snapshot=snap,timepergig=tpg, monitor_to_state=False)
                    for vol in new_vols:
                        vol.add_tag('ebstestsuite_created')
                    createdvols.extend(new_vols)
                vols.extend(self.tester.monitor_created_euvolumes_to_state(createdvols, timepergig=tpg))
                self.tester.print_euvolume_list(vols)
                self.status("Attempting to attach new vols from new snapshots to instance:"+str(instance.id)+" to verify md5s...")
                for newvol in vols:
                    try:
                        instance.attach_euvolume(newvol,timeout=attach_timeout)
                    except ec2ops.VolumeStateException, vse:
                        self.status("This is a temp work around for testing, this is to avoid bug euca-5297"+str(vse),
                                    testcolor=TestColor.get_canned_color('failred'))
                        time.sleep(10)
                        self.debug('Monitoring volume post VolumeStateException...')
                        newvol.eutest_attached_status = None
                        self.tester.monitor_euvolumes_to_status([newvol],status='in-use',attached_status='attached',timeout=60)
                    except Exception, e:
                        self.debug("Failed to attach volume: " + str(newvol.id) + "to instance:" + str())
                        raise e
                    if vol.md5 != newvol.md5:
                        raise Exception("New volume's md5:"+str(newvol.md5)+" !=  original volume md5:"+str(vol.md5))
                    else:
                        self.debug("Success. New volume:"+str(newvol.id)+"'s md5:"+str(newvol.md5)+" ==  original volume:"+str(vol.id)+"'s md5:"+str(vol.md5))
                    instance.detach_euvolume(newvol)
            finally:
                self.debug("Attempting to cleanup/delete snapshots and volumes from this test...")
                #add snapshots to global list for cleanup later
                self.snaps.extend(snaps)
                for avol in instance.attached_vols:
                    if avol in vols:
                        instance.detach_euvolume(avol, waitfordev=False)
                delfail = None  
                for vol in vols:
                    try:
                        self.tester.delete_volume(vol,timeout=delete_to)
                    except Exception, e:
                        delfail = str(vol.id)+" failed to delete, err:"+str(e)
                if delfail:
                    raise Exception(delfail)
               
            
    def concurrent_consecutive_volumes_from_snap_verify_md5(self, 
                                                            zonelist=None, 
                                                            snap=None, 
                                                            count=5, 
                                                            volmaxsize=1, 
                                                            delay=0, 
                                                            tpg=300,
                                                            delete_to=120,
                                                            poll_progress=60,
                                                            attach_timeout=480):
        """
        Description:
                   Attempts to create a 'count' number of volumes from a given snapshot consecutively with a delay of 'delay'
                   between each creation attempt. Waits for volumes to become available. Attempts to attach each volume and
                   verify it's md5 sum matches the original volumes. If multiple zones are specified will try in both zones at the same time. 
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        zone = TestZone
        #vol = euvolume.EuVolume
        instance = euinstance.EuInstance
        if not snap:
            for snap in self.snaps:
                if snap.volume_size <= volmaxsize:
                    break
            if not snap or snap.volume_size > volmaxsize:
                raise Exception("Could not find  snapshot <= volmaxsize of:"+str(volmaxsize))
        if snap.eutest_volume_md5:
            origmd5 = snap.eutest_volume_md5 
        else: 
            raise Exception('Snapshot must be created from a previously attached euvolume in order to derive md5')
        self.debug('Using Snapshot:'+str(snap.id))
        for zone in zonelist:
            if not zone.instances:
                raise Exception("Zone "+str(zone.name)+", did not have at least 1 instance to run test")
        vols = []
        instances = []
        try:
            for zone in zonelist:
                self.status('STARTING ZONE:'+str(zone.name))
                #Do not set monitor flag in order to quickly request count number of consecutive vols in each zone
                new_vols = self.tester.create_volumes(zone,snapshot=snap, count=count, monitor_to_state=None, timepergig=tpg)
                for vol in new_vols:
                    vol.add_tag('ebstestsuite_created')
                vols.extend(new_vols)
            vols = self.tester.monitor_created_euvolumes_to_state(vols,timepergig=tpg)
            self.tester.print_euvolume_list(vols)
            for zone in zonelist:
                instance = zone.instances[0]
                instances.append(instance)
                self.status("Attempting to attach new vols from new snapshots to instance:"+str(instance.id)+" to verify md5s...")      
                for newvol in vols:
                    if newvol.zone == zone.name:
                        try:
                            instance.attach_euvolume(newvol, timeout=attach_timeout)
                        except ec2ops.VolumeStateException, vse:
                            self.status("This is a temp work around for testing, this is to avoid bug euca-5297"+str(vse),
                                    testcolor=TestColor.get_canned_color('failred'))
                            time.sleep(10)
                            self.debug('Monitoring volume post VolumeStateException...')
                            newvol.eutest_attached_status = None
                            self.tester.monitor_euvolumes_to_status([newvol],status='in-use',attached_status='attached',timeout=60)
                        except Exception, e:
                            self.debug("Failed to attach volume: " + str(newvol.id) + "to instance:" + str())
                            raise e
                        #Compare MD5 sum to original volume
                        if str(origmd5).rstrip().lstrip() != str(newvol.md5).rstrip().lstrip():
                            raise Exception("New volume's md5:'"+str(newvol.md5)+"' !=  original volume md5:'"+str(origmd5)+"'")
                        else:
                            self.debug("Success. New volume:"+str(newvol.id)+"'s md5:"+str(newvol.md5)+" ==  original volume:"+str(snap.volume_id)+"'s md5:"+str(origmd5))
                        instance.detach_euvolume(newvol)
        
        finally:
            self.debug("Attempting to cleanup/delete snapshots and volumes from this test...")
            for instance in instances:
                for avol in instance.attached_vols:
                    if avol in vols:
                        instance.detach_euvolume(avol)
            self.tester.print_euvolume_list(vols)
            delfail = None
            for vol in vols:
                try:
                    self.tester.delete_volume(vol,timeout=delete_to)
                except Exception, e:
                    delfail = str(vol.id)+" failed to delete, err:"+str(e)
            if delfail:
                raise Exception(delfail)
            
                   
    def test_multi_node(self,run=True, count=10, nodecount=2):
        testlist = [] 
        #create 4 volumes per zone
        testlist.append(self.create_testunit_from_method(self.create_vols_per_zone, volsperzone=(2*nodecount), eof=True))
        #launch instances to interact with ebs volumes per zone
        testlist.append(self.create_testunit_from_method(self.create_test_instances_for_zones, count=nodecount, eof=True))
        
        for x in xrange(0,count):
            #attach first round of volumes
            testlist.append(self.create_testunit_from_method(self.attach_all_avail_vols_to_instances_in_zones, 
                                                             overwrite=True, 
                                                             eof=True))
            #detach 1 volume leave the 2nd attached
            testlist.append(self.create_testunit_from_method(self.detach_volumes_in_zones))
        
            
        #terminate each instance and verify that any attached volumes return to available state
        testlist.append(self.create_testunit_from_method(self.terminate_instances_in_zones_verify_volume_detach))
        
        if run:
            self.run_test_case_list(testlist)
        else:
            return testlist
    
    def test_consecutive_concurrent(self,run=True, count=5, delay=0, tpg=300, poll_progress=60, delete_to=120, snap_attached=False):
        testlist = [] 
        #create 1 volume per zone
        testlist.append(self.create_testunit_from_method(self.create_vols_per_zone, volsperzone=1, eof=True))
        #launch an instances to interact with ebs volumes per zone
        testlist.append(self.create_testunit_from_method(self.create_test_instances_for_zones, eof=True))
        #attach first round of volumes
        testlist.append(self.create_testunit_from_method(self.attach_all_avail_vols_to_instances_in_zones, 
                                                         overwrite=True, 
                                                         eof=True))
        if not snap_attached:
            #detach 1 volume 
            testlist.append(self.create_testunit_from_method(self.detach_volumes_in_zones))
        
        #Attempt to create multiple snapshots quickly then volumes from thos snaps and verify the md5 against original volume's
        testlist.append(self.create_testunit_from_method(self.consecutive_snapshot_to_vol_verify_md5s, 
                                                         count=count, 
                                                         delay=delay, 
                                                         tpg=tpg,
                                                         delete_to=delete_to,
                                                         poll_progress=poll_progress))
        #attempt to create volumes from snaps, attach and verify md5 in same zone it was created in
        testlist.append(self.create_testunit_from_method(self.create_snapshots_all_vols_in_zone))
        #Attempt to create multiple consecutive volumes from a single snapshot, will attempt concurrent tests accross multiple zones if in multi zone test
        testlist.append(self.create_testunit_from_method(self.concurrent_consecutive_volumes_from_snap_verify_md5,
                                                         count=count, 
                                                         delay=delay, 
                                                         tpg=tpg,
                                                         delete_to=delete_to))
        #terminate each instance and verify that any attached volumes return to available state
        testlist.append(self.create_testunit_from_method(self.terminate_instances_in_zones_verify_volume_detach))
        if run:
            self.run_test_case_list(testlist)
        else:
            return testlist


    def expand_volume_size(self, zonelist=None, volsperzone=1, size=1):
        """
        Description:
                    Intention of this test is to verify creation of volume(s) from a snapshot and expanding
                    the size of the volume
        """
        zonelist = zonelist or self.zonelist
        if not zonelist:
            raise Exception("Zone list was empty")
        for testzone in zonelist:
            vols = self.tester.create_volumes(testzone, size=size, count=volsperzone)
            for vol in vols:
                vol.add_tag('ebstestsuite_created')
            testzone.volumes.extend(vols)
            snapshots = []
            for volume in vols:
                snapshots.append(self.tester.create_snapshot_from_volume(volume))
            larger_volumes = []
            for snaphot in snapshots:
                larger_volume = self.tester.create_volume(testzone, snapshot=snaphot, size=size+1)
                larger_volume.add_tag('ebstestsuite_created')
                larger_volumes.append(larger_volume)
            for volume in larger_volumes:
                assert volume.size > size


    def ebs_basic_test_suite(self, run=True):  
        testlist = [] 
        #create first round of volumes
        testlist.append(self.create_testunit_from_method(self.create_vols_per_zone, eof=True))
        #create volumes that have their sizes expanded from their original snapshots
        testlist.append(self.create_testunit_from_method(self.expand_volume_size, eof=True))
        #launch instances to interact with ebs volumes
        testlist.append(self.create_testunit_from_method(self.create_test_instances_for_zones, eof=True))
        #attach first round of volumes
        testlist.append(self.create_testunit_from_method(self.attach_all_avail_vols_to_instances_in_zones, overwrite=True, eof=True))
        #attempt to delete attached volumes, should not be able to
        testlist.append(self.create_testunit_from_method(self.negative_delete_attached_volumes_in_zones))
        #attempt to attach a volume which is already attached, should not be able to
        testlist.append(self.create_testunit_from_method(self.negative_attach_in_use_volume_in_zones))
        #create second round of volumes
        testlist.append(self.create_testunit_from_method(self.create_vols_per_zone))
        #attach second round of volumes
        testlist.append(self.create_testunit_from_method(self.attach_all_avail_vols_to_instances_in_zones, overwrite=True))
        #reboot instances and confirm volumes remain attached
        testlist.append(self.create_testunit_from_method(self.reboot_instances_in_zone_verify_volumes, waitconnect=self.waitconnect))
        #detach 1 volume leave the 2nd attached
        testlist.append(self.create_testunit_from_method(self.detach_volumes_in_zones))
        #attempt to create volumes from snaps, attach and verify md5 in same zone it was created in
        testlist.append(self.create_testunit_from_method(self.create_snapshots_all_vols_in_zone))
        #attempt to create volumes of each snap within the same zone they were originally created in
        testlist.append(self.create_testunit_from_method(self.create_vols_from_snap_in_same_zone))
        #attempt to verify integrity of the volumes  by attaching to instance and checking md5 against original
        testlist.append(self.create_testunit_from_method(self.attach_new_vols_from_snap_verify_md5))  
        if (len(self.zonelist) > 1 ):
            #attempt to create volumes from     s, attach and verify md5 in a different zone than it was created in        
            testlist.append(self.create_testunit_from_method(self.create_vols_from_snap_in_different_zone))
            #verify the integrity of the new volumes by attaching to instance and checking md5 against original
            testlist.append(self.create_testunit_from_method(self.attach_new_vols_from_snap_verify_md5))
        #'IF' a bfebs instance was used, confirm attached volumes can be detached while in stopped state
        testlist.append(self.create_testunit_from_method(self.detach_all_volumes_from_stopped_instances_in_zones))
        #terminate each instance and verify that any attached volumes return to available state
        testlist.append(self.create_testunit_from_method(self.terminate_instances_in_zones_verify_volume_detach))
        if run:
            self.run_test_case_list(testlist)
        else:
            return testlist
        
                
    
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
            while (sc is None) and (elapsed < 480):
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

    def clean_method(self):
        """
        Definition:
        Attempts to clean up test artifacts created during this test
        """

        self.clean_created_resources(zonelist=self.zonelist, timeout=480)
    
    def clean_created_resources(self, zonelist=None, timeout=480):
        """
        Definition:
        Attempts to clean up test artifacts created during this test
        """
        self.tester.cleanup_artifacts()
        #self.terminate_test_instances_for_zones(zonelist=zonelist, timeout=timeout)
        #self.delete_volumes_in_zones(zonelist=zonelist, timeout=timeout)
        #self.delete_snapshots_in_zones(zonelist=zonelist,  timeout=timeout)
   
if __name__ == "__main__":
    ## If given command line arguments, use them as test names to launch
    testcase= EbsTestSuite()
    testcase.clean_method = testcase.clean_created_resources
    testlist = testcase.ebs_basic_test_suite(run=False)

    ret = testcase.run_test_case_list(testlist,
                                      eof=testcase.args.exit_on_failure,
                                      clean_on_exit=testcase.args.clean_on_exit)
    print "ebs_basic_test exiting:("+str(ret)+")"
    exit(ret)


        



  
