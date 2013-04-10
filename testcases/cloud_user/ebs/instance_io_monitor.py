"""
Script to Quickly run an instance, attach a volume, mount the volume, create a test file on that volume,
upload script to create and monitor read/write IO on the mounted volume. Provided real time display of read/write
operations via ssh connection to instance. 
"""

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
        #if self.args.config:
        #    setattr(self.args, 'config_file',self.args.config)
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
        Attempts to clean up resources created during this test...
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
        tb = None
        err = None
        exit_value = None
        exit_lines = ""

        cmd = 'python ' + self.remote_script_path + " -f " + self.test_file_path
        self.stdscr = curses.initscr()
        try:
            signal.signal(signal.SIGWINCH, self.sigwinch_handler)
            out = self.instance.ssh.cmd(cmd,
                                  verbose=False,
                                  cb=self.remote_ssh_io_script_monitor_cb,
                                  cbargs=[None,None,None,None,time.time()])
            exit_value = out['status']
            exit_lines = out['output']
        except Exception, e:
            tb = self.tester.get_traceback()
            debug_string = str(tb) + '\nError caught by remote_ssh_io_monitor_cb:'+str(e)
            self.debug(debug_string)
            self.stdscr.addstr(0, 0, debug_string)
            self.stdscr.refresh()
            err = str(e)
            raise Exception(str(tb)+ '\nError:' + str(err))
        finally:
            if exit_value is None or exit_value != 0:
                tb = self.tester.get_traceback()
                err = "Remote io script ended with invalid status code:" + str(exit_value) + "\n" + str(exit_lines)
            self.stdscr.keypad(0)
            curses.echo()
            curses.nocbreak()
            curses.endwin()
            time.sleep(1)
            if tb:
                raise Exception(str(tb)+ '\nError:' + str(err))



    @eutester.Eutester.printinfo
    def remote_ssh_io_script_monitor_cb(self,
                                        buf,
                                        write_value,
                                        write_rate,
                                        read_rate,
                                        last_read,
                                        last_time):
        ret = SshCbReturn(stop=False, settimer=self.inter_io_timeout)
        return_buf = ""
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
                elif re.match('WRITE_RATE', line):
                    write_rate = line
                elif re.match('READ_RATE', line):
                    read_rate = line
                elif re.match('LAST_READ', line):
                    last_read = line
                elif re.search('err', line, re.IGNORECASE):
                    return_buf += line

            debug_string = "Instance: " + str(self.instance.id) + ", Volume:" + str(self.volume.id )+ "\n" \
                           + "-------------------------------------------------\n" \
                           + write_value.ljust(20) + "\n" \
                           + write_rate.ljust(30) + "\n" \
                           + read_rate.ljust(30) + "\n" \
                           + last_read.ljust(20) + "\n" \
                           + waited_str.ljust(20) + "\n" \
                           + str(longest_wait_period_str).ljust(20) + "\n" \
                           + "ret buf:" + str(return_buf) \
                           + "\n-------------------------------------------------\n"
            #print "\r\x1b[K"+str(debug_string),
            #sys.stdout.flush()
            self.stdscr.addstr(0, 0, debug_string)
            self.stdscr.refresh()
            if return_buf:
                time.sleep(10)
        except Exception, e:
            tb = self.tester.get_traceback()
            debug_string = str(tb) + '\nError caught by remote_ssh_io_monitor_cb:'+str(e)
            self.debug(debug_string)
            self.stdscr.addstr(0, 0, debug_string)
            self.stdscr.refresh()
            ret.stop = True
            ret.nextargs = [ write_value, write_rate,read_rate, last_read, time.time()]
            ret.buf = return_buf
            time.sleep(10)
            pass
        finally:
            ret.nextargs = [ write_value, write_rate,read_rate, last_read, time.time()]
            ret.buf = return_buf
            return ret

    def sigwinch_handler(self, signal, frame ):
        if self.stdscr:
            curses.endwin()
            self.stdscr = curses.initscr()



if __name__ == "__main__":
    testcase = Instance_Io_Monitor()

    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or [ 'setup_instance_volume_and_script',
                                    'run_remote_script_and_monitor']

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,eof=True,clean_on_exit=True)
    exit(result)









