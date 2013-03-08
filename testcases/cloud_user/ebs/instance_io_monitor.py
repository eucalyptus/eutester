__author__ = 'clarkmatthew'


from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import TestColor
from eucaops import ec2ops
#from eutester.euinstance import EuInstance
#from eutester.euvolume import EuVolume
#from eutester.eusnapshot import EuSnapshot
from eutester.sshconnection import SshCbReturn
from eucaops import Eucaops
import time
import copy
import os
import sys
import re
import curses

class Instance_Io_Monitor(EutesterTestCase):
    def __init__(self, **kwargs):
        #### Pre-conditions
        self.setuptestcase()
        self.setup_parser()

        self.parser.add_argument('--local_path_to_nc_script',
                                 dest='io_script_path',
                                 help='Path to NC IO generator script if not in local dir, default: "vm_read_write_vol.py"',
                                 default='vm_read_write_vol.py')
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
        # Allow __init__ to get args from __init__'s kwargs or through command line parser...
        for kw in kwargs:
            print 'Setting kwarg:'+str(kw)+" to "+str(kwargs[kw])
            self.set_arg(kw ,kwargs[kw])
        # Setup basic eutester object
        try:
            self.tester = self.do_with_args(Eucaops)
        except Exception, e:
            raise Exception('Couldnt create Eucaops tester object, make sure credpath, '
                            'or config_file and password was provided, err:' + str(e))
        #replace default eutester debugger with eutestcase's for more verbosity...
        self.tester.debug = lambda msg: self.debug(msg, traceback=2, linebyline=False)
        self.reservation = None
        self.instance = None
        self.size = int(self.args.size)
        ### Add and authorize a group for the instance
        ### Generate a keypair for the instance
        if self.args.zone:
            self.zone = str(self.args.zone)
        else:
            self.zone = 'PARTI00'
        self.groupname = 'jenkins'
        self.group = self.tester.add_group(self.groupname)
        self.tester.authorize_group(self.group)
        self.tester.authorize_group(self.group, protocol='icmp',port='-1')
        try:
            keys = self.tester.get_all_current_local_keys()
            if keys != []:
                self.keypair = keys[0]
            else:
                self.keypair = keypair = self.tester.add_keypair('mpathtestinstancekey')
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

        self.instance = None
        self.volumes = None
        self.remote_script_path = None



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
            tb = self.tester.get_traceback()
            raise Exception('Cleanupfailed:'+str(e) + "\n" +str(tb))

    def launch_test_instance(self):

        self.instance = self.tester.run_image(image=self.image,
                                               zone=self.zone,
                                               min=1,
                                               max=1,
                                               group=self.group,
                                               keypair=self.keypair,
                                               monitor_to_running=True)[0]

    def create_and_attach_volume(self):
        self.volume = self.tester.create_volume(self.zone,
                                                size=self.size)
        self.instance.attach_volume(self.volume, timeout=90)

    def mount_volume_and_create_test_file(self):
        mount_point = self.instance.mount_attached_volume(volume=self.volume)
        mount_point = str(mount_point).rstrip('/')+'/'
        test_file_path = mount_point+ 'testfile'
        self.instance.sys('touch ' + test_file_path, code=0)
        self.test_file_path = test_file_path


    def sftp_test_io_script_to_instance(self):
        local_script_path =str(self.args.io_script_path)
        remote_script_path = str(os.path.basename(local_script_path))
        self.instance.ssh.sftp_put(local_script_path,remote_script_path)
        self.remote_script_path = remote_script_path


    def setup_instance_volume_and_script(self):
        self.launch_test_instance()
        self.create_and_attach_volume()
        self.mount_volume_and_create_test_file()
        self.sftp_test_io_script_to_instance()

    def run_remote_script_and_monitor(self):
        cmd = 'python ' + self.remote_script_path + " -f " + self.test_file_path
        try:
            self.instance.ssh.cmd(cmd,
                                  cb=self.remote_ssh_io_script_monitor_cb,
                                  cbargs=[None,None,None,None])
        except Exception, e:
            tb = self.tester.get_traceback()
            raise exception(str(tb)+ '\nError:' + str(e))



    def remote_ssh_io_script_monitor_cb(self,
                                        buf,
                                        write_value,
                                        write_rate,
                                        read_rate,
                                        last_read):
        ret = SshCbReturn(stop=False)
        write_rate = write_rate or 'WRITE_RATE:'
        write_value = write_value or 'WRITE_VALUE'
        read_rate = read_rate or 'READ_RATE'
        last_read = last_read or 'LAST_READ'
        try:
            for line in str(buf).splitlines():
                if re.match('WRITE_VALUE',line):
                    write_value = line
                if re.match('WRITE_RATE', line):
                    write_rate = line
                if re.match('READ_RATE', line):
                    read_rate = line
                if re.match('LAST_READ', line):
                    last_read = line
            debug_string = write_value.center(20) + write_rate.center(30) + read_rate.center(30) + last_read.center(20)
            print "\r\x1b[K"+str(debug_string),
            sys.stdout.flush()
        except Exception, e:
            pass
        finally:
            ret.nextargs = [ write_value, write_rate,read_rate, last_read]
            return ret












