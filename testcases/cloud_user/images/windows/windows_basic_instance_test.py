__author__ = 'clarkmatthew'

import sys
import time
from eutester.eutestcase import EutesterTestCase
from eucaops import Eucaops
from eucaops.ec2ops import ResourceNotFoundException
from testcases.cloud_user.images.imageutils import ImageUtils





class Windows_Basic_Instance_Test(EutesterTestCase):

    def __init__(self, tester=None, **kwargs):
        #### Pre-conditions
        self.setuptestcase()
        self.setup_parser(testname='Windows_Basic_Instance_Test')
        self.parser.add_argument('--image_id',
                                 help='Image id of an existing image to run'
                                      ' test against, default:None',
                                 default=None)
        self.parser.add_argument('--image_url',
                                 help='Image url. Will look for an existing'
                                      'tag containing this url if not found'
                                      'will attempt to create an image from'
                                      'this url, default:None',
                                 default=None)
        self.parser.add_argument('--dont_clean',
                                action='store_true', default=False,
                                help='Boolean, will run all test methods in testsuite()')
        self.parser.add_argument('--auth_ports',
                                 help='Comma delimited list of "protocol:port'
                                      ' to authorize for this test, '
                                      'default: tcp:3389,tcp:80,tcp:443,tcp:5985,tcp:5986',
                                 default='tcp:3389,tcp:80,tcp:443,tcp:5985,tcp:5986')
        self.parser.add_argument('--image_run_timeout',
                                 help='Time to wait in seconds for an image to'
                                      ' go to running state. Default allows 60'
                                      ' seconds per 1 gig of image size, or '
                                      '600 seconds if size not available.',
                                 default=None)

        self.tester = tester
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
        self.wins = None
        self.test_tag = 'windows_basic_instance_test'
        ### Add and authorize a group for the instance
        if self.args.zone:
            self.zone = str(self.args.zone)
        else:
            zones = self.tester.get_zones()
            if 'PARTI00' in zones:
                self.zone = 'PARTI00'
            elif zones:
                self.zone = zones[0]
            else:
                raise RuntimeError('No Zones found to run test')
        self.groupname = 'windows_basic_instance_test'
        self.group = self.tester.add_group(self.groupname)
        #For this basic test make it wide open...
        self.authorization_windows_group()
        ### Generate a keypair for the instance
        try:
            keys = self.tester.get_all_current_local_keys()
            if keys:
                self.keypair = keys[0]
            else:
                self.keypair = self.tester.add_keypair('mpathtestinstancekey'
                                                       + str(time.time()))
        except Exception, ke:
            raise Exception("Failed to find/create a keypair, error:" + str(ke))


    def authorization_windows_group(self,portlist=None):
        '''
        Where format for adding port in list is: 'protocol:port', example: tcp, port 80 = 'tcp:80'
        '''
        authports = portlist or self.args.auth_ports.split(',')
        for p in authports:
            protocol,port = str(p).split(':')
            self.tester.authorize_group_by_name(self.group.name,protocol=str(protocol),port=int(port))

    def get_a_windows_test_image(self):
        # If an image id was provided, attempt to get that image to use
        if self.args.image_id:
            self.image = self.tester.get_emi(self.args.image_id)
        else:
            # See if a eutester windows image already exists on the system
            # If an image url was provided try that first...
            if self.args.image_url:
                try:
                    self.image = self.tester.get_emi(
                        filters={'tag-value':self.args.image_url,
                                 'platform':'windows'})
                except ResourceNotFoundException:
                    self.debug('Image not found for provide url:"{0}", '
                               'attempting to create one now...'
                               .format(self.args.image_url))
                    self.create_image_from_url(self.args.image_url)
            else:
                # Otherwise look for a eutester created windows image...
                self.image = self.tester.get_emi(
                    filters={'tag-key':'eutester-created',
                             'platform':'windows'})
        self.debug('Using the following image to run this test. '
                   'ID:{0}, Name:{1}'.format(self.image.id, self.image.name))

    def create_image_from_url(self, url=None):
        """
        Definition: Attempts to create a windows image from a provided URL
        """
        url = url or self.args.image_url
        if not url:
            raise ValueError('No url provided to "create_image_from_url"')
        self.debug('Attempting to create image from:' + str(url))
        image_utils = ImageUtils(tester=self.tester)
        image = image_utils.create_emi(url=url,
                                       platform='windows',
                                       kernel='windows')
        self.status('Setting launch permissions to "all" on image:' + str(image.id))
        image.set_launch_permissions(group_names=['all'])
        self.debug('created image:' + str(image.id))
        self.image = image
        return image

    def get_min_vm_type_for_size(self, disk_size):
        for vmtype in self.tester.get_vm_type_list_from_zone(self.zone):
            if vmtype.disk >= disk_size:
                return vmtype.name
        raise RuntimeError('Could not find vmtype large enough for disk '
                           'size:' + str(disk_size))

    def run_windows_instance(self):
        """
        Definition: Attempts to run a windows instance.
        -Monitors instance to running state
        -Polls windows management ports for access/status
        -Attempts winrm connection to validate vm status.
        -Dumps system info,
         and disk info for block device mapping (ebs, ephemeral, etc)
        """
        vmtype = self.args.vmtype
        timeout = self.args.image_run_timeout
        default_vmtype = 'm2.xlarge'
        if not vmtype:
            size = None
            if 'size' in self.image.tags:
                if self.image.tags['size']:
                    size = int(self.image.tags['size'])
            if size:
                vmtype = self.get_min_vm_type_for_size(size)
                if not timeout:
                    timeout = 60 * size
            else:
                self.debug('No size found, using default vmtype:'
                           + str(default_vmtype))
                vmtype=default_vmtype
        if not timeout:
            timeout = 600
        if not self.image:
            self.get_a_windows_test_image()
        image_info = "Running the following Windows Image:\n"
        for key in self.image.__dict__:
            image_info += str(key) + " ----> " + \
                          str(self.image.__dict__[key]) + "\n"
        self.debug(image_info)
        self.wins = self.tester.run_image(image=self.image,
                                          group=self.group,
                                          keypair=self.keypair,
                                          zone=self.zone,
                                          type=vmtype,
                                          timeout=timeout)[0]
        return self.wins

    def check_ephemeral_test(self):
        """
        Definition: Test attempts to verify the ephemeral disk size for an
        instance store backed instance based upon the vmtype ran.
        """
        if self.wins is None:
            self.skipTest('No Windows instance to run test against')
        main_disk = None
        ephemeral_disk = None
        vmtype = self.tester.get_vm_type_from_zone(self.zone,
                                                   self.wins.instance_type)
        disk_size = vmtype.disk
        for disk in self.wins.diskdrives:
            if disk.index == 0:
                main_disk = disk
            if disk.index == 1:
                ephemeral_disk = disk
            if main_disk and ephemeral_disk:
                break
        self.debug(str(self.id) + ', Primary disk size:' +
                   str(main_disk.size))
        self.debug(str(self.id) + ', Ephemeral disk size:' +
                   str(main_disk.size))
        assert disk_size == main_disk.get_size_in_gb() + \
               ephemeral_disk.get_size_in_gb()


    def ebs_attach_detach_volume_test(self):
        '''
        Definition: Basic attach and detach ebs volume test.
        -Verifies ebs attached and detached states.
        -Verifies the volume appears on the guest as a new disk when attached
        -Verifies the size is correct
        -Verifies the volume is removed from the guest upon detach
        '''
        if self.wins is None:
            self.skipTest('No Windows instance to run test against')
        self.testvolume = self.tester.create_volume(zone=self.zone, size=1)
        self.wins.attach_volume(self.testvolume)
        time.sleep(10)
        self.wins.detach_euvolume(self.testvolume)


    def clean_method(self):
        self.tester.test_resources['images'] = []
        if self.args.dont_clean:
            self.debug('Not cleaning due to dont_clean arg')
        else:
            return self.tester.cleanup_artifacts()

if __name__ == "__main__":
    testcase = Windows_Basic_Instance_Test()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    test_names = testcase.args.tests or []
    if not test_names:
        testcase.get_a_windows_test_image()
        if not testcase.image:
            if not testcase.args.image_url:
                raise RuntimeError('No image found and no image url provided')
            else:
                test_names.append('create_image_from_url')
        test_names.extend(['run_windows_instance',
                          'check_ephemeral_test',
                          'ebs_attach_detach_volume_test'])
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in test_names:
        unit_list.append(testcase.create_testunit_by_name(test))

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,
                                         eof=False,
                                         clean_on_exit=True)
    sys.exit(result)



