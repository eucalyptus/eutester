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
from eutester.euproperties import Euproperty_Type
from testcases.cloud_user.ebs.mpath_monkey import Mpath_Monkey
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
    def __init__(self, tester=None,**kwargs):
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
        self.parser.add_argument('--cycle_paths',
                                 action='store_true', default=False,
                                 help='Boolean used to cycle paths during basic run instance monitor io')

        self.parser.add_argument('--run_suite',
                                action='store_true', default=False,
                                help='Boolean, will run all test methods in testsuite()')

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
        self.mpath_monkey = None
        self.cycle_paths =self.args.cycle_paths




    def cleanup(self, instances=True):
        '''
        Attempts to clean up resources created during this test...
        '''
        try:
            if self.mpath_monkey:
                try:
                    node = self.mpath_monkey.host
                    self.mpath_monkey.clear_all_eutester_rules(timeout=120)
                except Exception, e:
                    self.debug('Error cleaning up iptables rules on NC:' + str(node) +', Err:'+str(e))
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


    def get_nc_paths_for_instance(self,instance=None, iface=False):
        paths = []
        instance = instance or self.instance
        partition = instance.placement
        ncpaths_property = self.tester.property_manager.get_property(service_type=Euproperty_Type.storage,partition=partition,name='ncpaths')
        for path in str(ncpaths_property.value).split(','):
            for part in path.split(':'):
                if re.search('iface', part):
                    if iface:
                        paths.append(part)
                elif not iface:
                    paths.append(part)
        return paths


    def get_node_instance_is_running_on(self, instance=None):
        instance = instance or self.instance
        nodes = self.tester.service_manager.get_all_node_controllers(instance_id=self.instance.id,use_cached_list=False)
        if not nodes:
            raise Exception('Could not find node that instance:'+str(instance.id)+" is running on")
        if len(nodes) > 1:
            nodes_string = ""
            for node in nodes:
                nodes_string += ", " +str(node.hostname)
            raise Exception('Multiple nodes found for instance:'+str(instance.id)+' ' +str(nodes_string))
        node = nodes[0]
        self.debug('Got node:' + str(node.hostname) + ", for instance:" + str(instance.id))
        return node


    def create_mpath_monkey(self,instance=None):
        instance = instance or self.instance
        paths = self.get_nc_paths_for_instance(instance=instance)
        node = self.get_node_instance_is_running_on(instance=instance)
        mm = Mpath_Monkey(node=node, sp_ip_list=paths)
        self.mpath_monkey = mm
        return mm



    def create_test_volume(self):
        if self.args.volume_id:
            self.volume  = self.tester.get_volume(volume_id=self.args.volume_id)
            if not self.volume:
                raise Exception('Faild to fetch volume from id provided:' +str(self.args.volume_id))
        else:
            self.volume = self.tester.create_volume(self.zone, size=self.size)

    def attach_test_volume(self,volume=None):
        volume = volume or self.volume
        try:
            self.instance.attach_volume(volume, timeout=90)
        except ec2ops.VolumeStateException, vse:
            self.status("This is a temp work around for testing, this is to avoid bug euca-5297"+str(vse),
                        testcolor=TestColor.get_canned_color('failred'))
            time.sleep(10)
            self.debug('Monitoring volume post VolumeStateException...')
            self.volume.eutest_attached_status = None
            self.tester.monitor_euvolumes_to_status([volume],status='in-use',attached_status='attached',timeout=90)


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
        self.create_test_volume()
        self.attach_test_volume()
        self.mount_volume_and_create_test_file()
        if self.cycle_paths:
            self.create_mpath_monkey()
        self.sftp_test_io_script_to_instance()







    def run_remote_script_and_monitor(self,timed_run=0):
        tb = None
        err = None
        exit_value = None
        exit_lines = ""
        original_inter_io_timeout = self.inter_io_timeout
        if timed_run:
            original_inter_io_timeout = self.inter_io_timeout



        cmd = 'python ' + self.remote_script_path + " -f " + self.test_file_path + ' -t ' + str(timed_run)
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
        blocked_paths ="BLOCKED_PATHS:"
        previous_blocked_path = "PREVIOUS_BLOCKED_PATH:"
        remaining_iterations = "REMAINING_ITERATIONS:"
        write_rate = write_rate or 'WRITE_RATE:'
        write_value = write_value or 'WRITE_VALUE'
        read_rate = read_rate or 'READ_RATE'
        last_read = last_read or 'LAST_READ'
        last_time = last_time or time.time()
        waited = int(time.time()- last_time)
        waited_str = "INTER_IO_SECONDS_WAITED: "+ str(waited)
        time_remaining = "TIME_REMAINING:"

        if self.mpath_monkey:
            remaining_iterations += str(self.mpath_monkey.remaining_iterations)
            if not self.mpath_monkey.remaining_iterations:
                self.stdscr.addstr(0, 0, 'MPATH MONKEY FINSIHED SUCCESSFULLY')
                self.stdscr.refresh()
                ret.stop = True
                self.mpath_monkey.timer.cancel()
            if not self.mpath_monkey.blocked:
                self.mpath_monkey.block_single_path_cycle()
            else:
                blocked_paths += self.mpath_monkey.get_blocked_string()
                previous_blocked_path += str(self.mpath_monkey.lastblocked)

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
                elif re.match('TIME_REMAINING', line):
                    time_remaining = line
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
                           + str(blocked_paths) + "\n" \
                           + str(previous_blocked_path) + "\n" \
                           + str(remaining_iterations) + "\n" \
                           + str(time_remaining) + "\n" \
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
            if self.mpath_monkey:
                self.mpath_monkey.timer.cancel()
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

    def check_mpath_iterations(self):
        if self.mpath_monkey and self.mpath_monkey.remaining_iterations:
            remaining = self.mpath_monkey.remaining_iterations
            raise Exception('Mpath monkey did not complete its iterations. Remaining:'+str(remaining))

    def test1_run_instance_monitor_io_and_cycle_all_paths_on_nc(self):
        test_list = []
        #Setup and connect to instance, create + attach vol, format vol, scp io script, create test dir/file.
        self.setup_instance_volume_and_script()

        #Run the remote io script on the test instance, monitor all script output via local call back method
        self.run_remote_script_and_monitor()

        #Check to make sure our script actually iterated through all the paths, if not something went wrong
        self.check_mpath_iterations()



    def test2_run_instance_attach_volume_while_a_single_path_is_down(self):
        single_path = None
        self.launch_test_instance()
        if self.volume:
            self.volume.update()
            if not self.volume.status == 'available':
                self.debug('Test volume:' + str(self.volume.id) + ", not in available state. Creating a new one")
                self.create_test_volume()
        if self.cycle_paths:
            self.create_mpath_monkey()
        self.mpath_monkey.clear_all_eutester_rules(timeout=120)
        if len(self.mpath_monkey.sp_ip_list) > 1:
            single_path = self.mpath_monkey.sp_ip_list[0]
        else:
            raise Exception('Not enough paths to shut one down for test')
        self.mpath_monkey.block_path(single_path)
        time.sleep(2)
        self.attach_test_volume()
        self.mount_volume_and_create_test_file()
        self.run_remote_script_and_monitor(timed_run=10)


    def test3_run_instance_attach_vol_detach_vol_while_single_path_is_down(self):
        single_path = None
        self.launch_test_instance()
        if self.volume:
            self.volume.update()
            if not self.volume.status == 'available':
                self.debug('Test volume:' + str(self.volume.id) + ", not in available state. Creating a new one")
                self.create_test_volume()
        if self.cycle_paths:
            self.create_mpath_monkey()
        self.mpath_monkey.clear_all_eutester_rules(timeout=120)
        time.sleep(2)
        self.attach_test_volume()
        if len(self.mpath_monkey.sp_ip_list) > 1:
            single_path = self.mpath_monkey.sp_ip_list[0]
        else:
            raise Exception('Not enough paths to shut one down for test')
        self.mpath_monkey.block_path(single_path)
        self.mount_volume_and_create_test_file()
        self.run_remote_script_and_monitor(timed_run=10)
        self.instance.detach_euvolume(self.volume)

    def testsuite(self):
        self.cycle_paths = True
        test_list = []
        test_list.append(self.create_testunit_from_method(self.test1_run_instance_monitor_io_and_cycle_all_paths_on_nc))
        test_list.append(self.create_testunit_from_method(self.test2_run_instance_attach_volume_while_a_single_path_is_down))
        test_list.append(self.create_testunit_from_method(self.test3_run_instance_attach_vol_detach_vol_while_single_path_is_down))
        return test_list

if __name__ == "__main__":
    testcase = Instance_Io_Monitor()

    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    if testcase.args.run_suite:
        unit_list = testcase.testsuite()
    else:
        list = testcase.args.tests or [ 'setup_instance_volume_and_script',
                                        'run_remote_script_and_monitor',
                                        'check_mpath_iterations']
        ### Convert test suite methods to EutesterUnitTest objects
        unit_list = [ ]
        for test in list:
            unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,eof=True,clean_on_exit=True)
    exit(result)









