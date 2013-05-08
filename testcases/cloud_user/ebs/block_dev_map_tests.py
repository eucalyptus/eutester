__author__ = 'clarkmatthew'
'''
ec2-register -n ImageName --root-device-name /dev/sda1 -s snap-e1eb279f
-b "/dev/sdb=ephemeral0" -b "/dev/sdh=snap-d5eb27ab" -b "/dev/sdj=:100"

This command maps /dev/sda to a EBS root volume based on a snapshot, /dev/sdb to ephemeral0, /dev/sdh to an EBS volume based on a snapshot, and /dev/sdj to an empty EBS volume that is 100 GiB in size. The output is the ID for your new AMI.




1) Create a bfebs image and record snapshot md5 in process.

'''

from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
from boto.ec2.blockdevicemapping import BlockDeviceMapping, BlockDeviceType
import time
import types
import httplib



class Block_Device_Mapping_Test(EutesterTestCase):
    #Define the bytes per gig
    gig = 1073741824

    def __init__(self, url=None, tester=None, **kwargs):
        #### Pre-conditions
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument('--size',
                                 type=int,
                                 help='Size in GB for created volumes, default:1',
                                 default=1)
        self.parser.add_argument("--url",
                                 dest="url",
                                 help="URL containing remote BFEBS image to create emi from",
                                 default=None)
        self.tester = tester
        self.url = url
        self.get_args()
        # Allow __init__ to get args from __init__'s kwargs or through command line parser...
        for kw in kwargs:
            print 'Setting kwarg:'+str(kw)+" to "+str(kwargs[kw])
            self.set_arg(kw ,kwargs[kw])
        self.show_args()
        #if self.args.config:
        #    setattr(self.args, 'config_file',self.args.config)
        # Setup basic eutester object
        if not self.tester:
            try:
                self.tester = self.do_with_args(Eucaops)
            except Exception, e:
                raise Exception('Couldnt create Eucaops tester object, make sure credpath, '
                                'or config_file and password was provided, err:' + str(e))
            #replace default eutester debugger with eutestcase's for more verbosity...
            self.tester.debug = lambda msg: self.debug(msg, traceback=2, linebyline=False)
        if not self.url:
            try:
                self.url = self.args.url

            except Exception, e:
                raise Exception('')
        self.reservation = None
        self.instance = None
        self.volumes = []
        self.image_bytes = None
        self.image_gigs = None
        self.build_image_volume = None
        self.build_image_snapshot = None
        self.block_device_map = None
        self.base_test_volume = None
        self.base_test_snapshot = None
        self.snapshots = []
        self.images = []
        self.size = int(self.args.size)

        ### Add and authorize a group for the instance
        if self.args.zone:
            self.zone = str(self.args.zone)
        else:
            self.zone = 'PARTI00'
        self.groupname = 'jenkins'
        self.group = self.tester.add_group(self.groupname)
        self.tester.authorize_group(self.group)
        self.tester.authorize_group(self.group, protocol='icmp',port='-1')
        ### Generate a keypair for the instance
        try:
            keys = self.tester.get_all_current_local_keys()
            if keys:
                self.keypair = keys[0]
            else:
                self.keypair = self.tester.add_keypair('mpathtestinstancekey'+str(time.time()))
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


    def cleanup(self):
        self.tester.cleanup_artifacts()


    def get_remote_file_size_via_http(self, url=None):
        url = url or self.url
        #Get the remote file size from the http header of the url given
        try:
            url = url.replace('http://','')
            host = url.split('/')[0]
            path = url.replace(host,'')
            self.debug("get_remote_file, host("+host+") path("+path+")")
            conn=httplib.HTTPConnection(host)
            conn.request("HEAD", path)
            res=conn.getresponse()
            image_bytes = int(res.getheader('content-length'))
            self.debug("content-length:"+str(self.image_bytes))
            conn.close()
        except Exception, e:
            self.debug("Failed to get remote file size...")
            raise e
        return image_bytes

    def pmsg(self, msg):
        self.debug( "\n---------------PROGRESS MESSAGE----------\n")
        self.debug( msg )
        self.debug("\n-----------------------------------------\n")


    def setup_bfebs_instance_volume_and_snapshots_from_url(self, url=None, create_test_vol=True):

        url = url or self.url
        volumes = []
        from eutester.euvolume import EuVolume
        from eutester.euinstance import EuInstance
        self.volume = EuVolume
        self.tester = Eucaops()
        self.instance = EuInstance
        exit(1) #get rid of this stuff above
        self.image_bytes = self.get_remote_file_size_via_http(url=url)
        self.image_gigs = ( ((self.image_bytes/gig)+1) or 1)
        self.debug("Remote file size: "+ str(self.image_gigs) + "g")
        self.instance = self.tester.run_image(self.image,
                                              keypair=self.keypair.name,
                                              type=self.args.vmtype,
                                              group=self.group.name,
                                              zone=self.zone)[0]
        self.debug('create test volume(s)...')
        self.build_image_volume = self.tester.create_volume(self.zone, size = self.image_gigs,monitor_to_state=None)
        volumes.append(self.build_image_volume)
        if create_test_vol:
            self.base_test_volume = self.tester.create_volume(self.zone, size = 1, monitor_to_state=None )
            volumes.append(self.base_test_volume)
        self.tester.monitor_created_euvolumes_to_state(volumes=volumes)
        self.debug('Copy the remote bfebs image into a volume and create snapshot from it...')
        self.instance.attach_volume(self.build_image_volume)
        self.instance.sys("curl "+url+" > "+ self.build_image_volume.guestdev+" && sync")
        self.instance.md5_attached_euvolume(self.build_image_volume,length=1024)
        self.build_image_snapshot = self.tester.create_snapshots(volume=self.build_image_volume)[0]
        self.debug('Done creating bfebs snapshot and md5ing volume')
        if create_test_vol:
            self.debug('Attaching test volume, writing random data into it and gathering md5...')
            self.instance.attach_volume(self.base_test_volume)
            self.instance.write
            self.instance. vol_write_random_data_get_md5(self.base_test_volume,length=1024, overwrite=True)
            self.base_test_snapshot = self.tester.create_snapshots(volume=self.base_test_volume)[0]
        return self.build_image_snapshot


    def add_block_device_types_to_mapping(self,
                                        device_name,
                                        ephemeral_name=None,
                                        snapshot_id=None,
                                        size=None,
                                        delete_on_terminate=True,
                                        block_device_map=None):
        block_device_map = block_device_map or BlockDeviceMapping()
        block_dev_type = BlockDeviceType()
        block_dev_type.delete_on_termination = delete_on_terminate
        block_dev_type.size = size

        if snapshot_id:
            if isinstance(snapshot_id, types.StringTypes):
                snapshot_id = snapshot_id
            else:
                snapshot_id = snapshot_id.id
            block_dev_type.snapshot_id = snapshot_id
        elif ephemeral_name:
            block_dev_type.ephemeral_name = ephemeral_name

        block_device_map[device_name] = block_dev_type
        return block_device_map

    def create_bfebs_image(self,
                           snapshot,
                           root_device_name = '/dev/sda',
                           delete_on_terminate=True,
                           size=None,
                           block_device_map=None):
        if isinstance(snapshot, types.StringTypes):
            snapshot_id = snapshot
        else:
            snapshot_id = snapshot.id
        new_image = self.tester.register_snapshot_by_id(snap_id=snapshot_id,
                                                        root_device_name=root_device_name,
                                                        size=size,
                                                        dot=delete_on_terminate,
                                                        block_device_map=block_device_map
                                                        )
        self.images.append(new_image)
        return new_image



    def find_volume_on_euinstance(self, euvolume, euinstance):
        '''
        Find block devices on guest by the MD5 sum of the volume(s) they were created from.
        Will attempt to find euvolumes on an instance 'if' the euvolume(s) have md5sums to use for
        comparison on the guest's dev dir.
        '''

        return euinstance.find_blockdev_by_md5(md5=euvolume.md5, md5len=euvolume.md5len)


    def register_test1_default_bfebs_image_plus_dot_is_true(self):
        '''
        Will test running a default bfebs image. Additional tests here:
        -will verify a portion of the root device's md5sum against the original volume's/snapshot's
        -will verify delete on terminate set to True, will expect backing volume to be deleted
        -will look for 'no' ephemeral
        '''
        image = self.create_bfebs_image(snapshot=self.build_image_snapshot, delete_on_terminate=True)
        self.dot_yes_image = image
        instance = self.tester.run_image(image=image)[0]
        self.find_volumes_on_euinstance([self.build_image_volume], instance)
        try:
            instance.get_ephemeral_dev()
        except:
            self.debug('Ephemeral was not found, passing...')
        else:
            raise Exception('Ephemeral device found, but none provided?')
        instance.terminate_and_verify()


    def register_test2_default_bfebs_image_plus_dot_is_false(self):
        '''
        Will test running a default bfebs image. Additional tests here:
        -will verify a portion of the root device's md5sum against the original volume's/snapshot's
        -will verify delete on terminate set to True, will expect backing volume to remain and become available.
        -will look for 'no' ephemeral
        '''
        image = self.create_bfebs_image(snapshot=self.build_image_snapshot, delete_on_terminate=False)
        self.dot_no_image = image
        instance = self.tester.run_image(image=image)[0]
        self.find_volumes_on_euinstance([self.build_image_volume], instance)
        try:
            instance.get_ephemeral_dev()
        except:
            self.debug('Ephemeral was not found, passing...')
        else:
            raise Exception('Ephemeral device found, but none provided?')
        instance.terminate_and_verify()


    def run_time_test1_dot_yes_image_add_ephemeral_and_snap_mapped_at_run_time_dot_is_true(self, ephemeral_size=2):
        bdm_snapshot_dev = '/dev/vdc'
        bdm_ephemeral_dev = '/dev/vdb'
        image = self.dot_yes_image
        bdm = self.add_block_device_types_to_mapping(device_name=bdm_ephemeral_dev, ephemeral_name='ephemeral0',size=ephemeral_size)
        self.add_block_device_types_to_mapping(snapshot_id=self.base_test_snapshot.id, device_name=bdm_snapshot_dev)
        instance = self.tester.run_image(image=image,block_device_map=bdm)[0]
        eph_dev = instance.get_ephemeral_dev()
        guest_eph_size = instance.get_blockdev_size_in_bytes(eph_dev)/self.gig
        if guest_eph_size != ephemeral_size:
            raise Exception('Ephemeral size:' + str(ephemeral_size) + " != ephemeral disk size on guest:" + str(guest_eph_size))
        #Find block devices on guest by the MD5 sum of the volume(s) they were created from.
        self.find_volume_on_euinstance(self.build_image_volume, instance)
        snap_dev = instance.find_blockdev_by_md5(md5=self.base_test_snapshot.eutest_volume_md5,
                                                 md5len=self.base_test_snapshot.eutest_volume_md5len)
        #quick test to make sure we can write to the device...
        snap_vol = self.tester.get_volume(status='in-use', attached_instance=instance.id,attached_dev=bdm_snapshot_dev)
        snap_vol.md5 = self.base_test_snapshot.md5
        snap_vol.md5len = self.base_test_snapshot.md5len
        snap_vol.guestdev = snap_dev
        instance.vol_write_random_data_get_md5(snap_vol, length=1024, overwrite=True)



        instance.terminate_and_verify()


   #     def test4_default_image_w_




