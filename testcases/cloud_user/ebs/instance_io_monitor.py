__author__ = 'clarkmatthew'


from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import TestColor
from eucaops import ec2ops
#from eutester.euinstance import EuInstance
#from eutester.euvolume import EuVolume
#from eutester.eusnapshot import EuSnapshot
from eutester.sshconnection import SshCbReturn
from eucaops import Eucaops
import eutester
import time
import copy
import os
import sys
import signal
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
        self.parser.add_argument('--instance_id',
                                 help='Instance id of an existing and running instance, default:None',
                                 default=None)
        self.parser.add_argument('--volume_id',
                                 help='Volume id of an existing and volume, default:None',
                                 default=None)
        self.parser.add_argument('--inter_io_timeout',
                                 type=int,
                                 help='Max time in seconds to wait for remote ssh command to update before failing, default:30',
                                 default=30)
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
        self.inter_io_timeout = int(self.args.inter_io_timeout)
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

        self.instance = None
        self.volumes = None
        self.remote_script_path = None
        self.longest_wait_period = 0



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

        if self.args.instance_id:
            instances = self.tester.get_instances(idstring=self.args.instance_id)
            if instances:
                self.instance = instances[0]
            else:
                raise Exception('Failed to fetch instance from id provided:' +str(self.args.instance_id))
        else:
            self.instance = self.tester.run_image(image=self.image,
                                                   zone=self.zone,
                                                   min=1,
                                                   max=1,
                                                   group=self.group,
                                                   keypair=self.keypair,
                                                   monitor_to_running=True)[0]

    def create_and_attach_volume(self):
        if self.args.volume_id:
            self.volume  = self.tester.get_volume(volume_id=self.args.volume_id)
            if not self.volume:
                raise Exception('Faild to fetch volume from id provided:' +str(self.args.volume_id))
        else:
            self.volume = self.tester.create_volume(self.zone, size=self.size)
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
        self.stdscr = curses.initscr()
        try:
            signal.signal(signal.SIGWINCH, self.sigwinch_handler)
            self.instance.ssh.cmd(cmd,
                                  verbose=False,
                                  cb=self.remote_ssh_io_script_monitor_cb,
                                  cbargs=[None,None,None,None,time.time()])
        except Exception, e:
            tb = self.tester.get_traceback()
            raise Exception(str(tb)+ '\nError:' + str(e))
        finally:
            self.stdscr.keypad(0)
            curses.echo()
            curses.nocbreak()
            curses.endwin()


    @eutester.Eutester.printinfo
    def remote_ssh_io_script_monitor_cb(self,
                                        buf,
                                        write_value,
                                        write_rate,
                                        read_rate,
                                        last_read,
                                        last_time):
        ret = SshCbReturn(stop=False, settimer=self.inter_io_timeout)
        write_rate = write_rate or 'WRITE_RATE:'
        write_value = write_value or 'WRITE_VALUE'
        read_rate = read_rate or 'READ_RATE'
        last_read = last_read or 'LAST_READ'
        last_time = last_time or time.time()
        waited = int(time.time()- last_time)
        waited_str = "INTER_IO_SECONDS_WAITED: "+ str(waited)
        if waited > self.longest_wait_period:
            self.longest_wait_period = waited
        longest_wait_period_str = "LONGEST_PERIOD_WAITED:" +str(self.longest_wait_period)
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
            '''
            debug_string = write_value.ljust(20) \
                           + write_rate.ljust(30) \
                           + read_rate.ljust(30) \
                           + last_read.ljust(20) \
                           + waited_str.ljust(20) \
                           + str(longest_wait_period_str).rjust(20)
            '''
            debug_string = write_value.ljust(20) + "\n" \
                           + write_rate.ljust(30) + "\n" \
                           + read_rate.ljust(30) + "\n" \
                           + last_read.ljust(20) + "\n" \
                           + waited_str.ljust(20) + "\n" \
                           + str(longest_wait_period_str).ljust(20) + "\n"
            #print "\r\x1b[K"+str(debug_string),
            #sys.stdout.flush()
            self.stdscr.addstr(0, 0, debug_string)
            self.stdscr.refresh()
        except Exception, e:
            tb = self.tester.trace_back()
            self.debug(str(tb) + '\nError caught by remote_ssh_io_monitor_cb:'+str(e))
            pass
        finally:
            ret.nextargs = [ write_value, write_rate,read_rate, last_read, time.time()]
            return ret

    @classmethod
    def print_fake_fault(cls):
        faultstring = (' \n'
                       '        Program received signal SIGSEGV, Segmentation fault.\n'
                       '        0x00007fc337f3857c in vfprintf () from /lib64/libc.so.6\n'
                       '        (gdb) bt\n'
                       '        #0 0x00007fc337f3857c in vfprintf () from /lib64/libc.so.6\n'
                       '        #1 0x00007fc331c27cd2 in logprintfl () from /usr/lib64/axis2c/services/EucalyptusNC/libEucalyptusNC.so\n'
                       '        #2 0x00007fc331c168f9 in vnetInit () from /usr/lib64/axis2c/services/EucalyptusNC/libEucalyptusNC.so\n'
                       '        #3 0x00007fc331bf93da in ?? () from /usr/lib64/axis2c/services/EucalyptusNC/libEucalyptusNC.so\n'
                       '        #4 0x00007fc331bfa78c in doDescribeResource () from /usr/lib64/axis2c/services/EucalyptusNC/libEucalyptusNC.so\n'
                       '        #5 0x00007fc331befada in ncDescribeResourceMarshal () from /usr/lib64/axis2c/services/EucalyptusNC/libEucalyptusNC.so\n'
                       '        #6 0x00007fc331bead14 in axis2_skel_EucalyptusNC_ncDescribeResource () from /usr/lib64/axis2c/services/EucalyptusNC/libEucalyptusNC.so\n'
                       '        #7 0x00007fc331bec3fe in axis2_svc_skel_EucalyptusNC_invoke () from /usr/lib64/axis2c/services/EucalyptusNC/libEucalyptusNC.so\n'
                       '        #8 0x00007fc337434c35 in ?? () from /usr/lib64/libaxis2_engine.so.0\n'
                       '        #9 0x00007fc3374347a1 in ?? () from /usr/lib64/libaxis2_engine.so.0\n'
                       '        #10 0x00007fc33742ad16 in axis2_engine_receive () from /usr/lib64/libaxis2_engine.so.0\n'
                       '        #11 0x00007fc337682367 in axis2_http_transport_utils_process_http_post_request () from /usr/lib64/httpd/modules/libmod_axis2.so\n'
                       '        #12 0x00007fc33767dd3c in axis2_apache2_worker_process_request () from /usr/lib64/httpd/modules/libmod_axis2.so\n'
                       '        #13 0x00007fc33767bf7c in ?? () from /usr/lib64/httpd/modules/libmod_axis2.so\n'
                       '        #14 0x00007fc3399dcb00 in ap_run_handler ()\n'
                       '        #15 0x00007fc3399e03be in ap_invoke_handler ()\n'
                       '        #16 0x00007fc3399eba30 in ap_process_request ()\n'
                       '        #17 0x00007fc3399e88f8 in ?? ()\n'
                       '        #18 0x00007fc3399e4608 in ap_run_process_connection ()\n'
                       '        #19 0x00007fc3399f0807 in ?? ()\n'
                       '        #20 0x00007fc3399f0b1a in ?? ()\n'
                       '        #21 0x00007fc3399f179c in ap_mpm_run ()\n'
                       '        #22 0x00007fc3399c8900 in main ()\n'
                       '        '
        )
        print faultstring



    def sigwinch_handler(self, signal, frame ):
        if self.stdscr:
            curses.endwin()
            self.stdscr = curses.initscr()



if __name__ == "__main__":
    testcase = Instance_Io_Monitor()

    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or [ 'setup_instance_volume_and_script',
                                    'run_remote_script_and_monitor'
    ]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,eof=True,clean_on_exit=True)
    exit(result)









