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
from testcases.cloud_user.ebs.path_controller import Path_Controller
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
    def __init__(self, tester=None, path_controllers=None, **kwargs):
        #### Pre-conditions
        self.setuptestcase()
        self.setup_parser(testname='Multipath_instance_io_monitor')

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
                                 action='store_true', default=True,
                                 help='Boolean used to cycle paths during basic run instance monitor io')
        self.parser.add_argument('--cycle_path_interval',
                                 type=int,
                                 help='Number of seconds between cycling NC paths, default: 15 seconds',
                                 default=15)
        self.parser.add_argument('--max_path_iterations',
                                 type=int,
                                 help='Number of times to iterate over all NC paths, default:2',
                                 default=2)
        self.parser.add_argument('--path_recovery_interval',
                                 type=int,
                                 help='Number of seconds to allow a down path to recover before cycling to next, default:30',
                                 default=30)

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

        self.test_tag = 'instance_io_monitor'
        #replace default eutester debugger with eutestcase's for more verbosity...
        self.tester.debug = lambda msg: self.debug(msg, traceback=2, linebyline=False)
        self.reservation = None
        self.instance = None
        self.volume = None
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
        self.path_controller = None
        self.cycle_paths =self.args.cycle_paths
        self.current_blocked_path = None
        self.last_blocked_path = None
        self.current_cycle_method = self.cycle_method_loop_over_paths
        self.cycle_path_interval = self.args.cycle_path_interval
        self.path_recovery_interval = self.args.path_recovery_interval
        self.max_path_iterations = self.args.max_path_iterations
        self.path_controllers = path_controllers or []
        self.path_controller = None





    def cycle_method_loop_over_paths(self,instance=None, clear_retry_interval=2, clear_timeout=30):
        '''
        uses select() in ssh cmd's input to give this method sudo cycles to run
        Loops over paths until stopped or 'path_iterations is reached
        '''
        #self.debug("cycle_method_loop_over_paths...")
        status = 'unknown'
        instance = instance or self.instance
        path_controller = instance.path_controller
        if path_controller.total_path_iterations >= self.max_path_iterations:
            status = 'Max iterations met'
            return
        last_block_time = path_controller.last_block_time
        last_cleared_time = path_controller.last_cleared_time
        last_clear_attempt_time = path_controller.last_clear_attempt_time

        blocked_paths = path_controller.get_blocked_paths()
        now = time.time()

        #See if were in the process of clearing or blocking...
        if last_clear_attempt_time > last_block_time:
            #Clearing...
            #See if we need to keep clearing currently blocked paths...
            if blocked_paths:
                status = 'Waiting for blocked paths to clear'
                if (now - last_clear_attempt_time) > clear_timeout:
                    raise Exception('Could not clear paths within ' + str(clear_timeout) + 'seconds:' + ",".join(blocked_paths))
                if (now - last_clear_attempt_time > clear_retry_interval):
                    #Try to clear all eutester iptables rules
                    path_controller.clear_all_eutester_rules(retry=False)
            elif last_cleared_time and ((now - last_cleared_time) > self.path_recovery_interval):
                status = "Issued block on new path"
                path_controller.block_next_path()
            elif not last_cleared_time:
                status = 'Waiting for iptables to clear all eutester rules'
                path_controller.clear_all_eutester_rules(retry=False)
            else:
                status = "Waiting for recovery interval"
        #We're blocking, see how long it's been and if we need to clear...
        elif (now - last_block_time) > self.cycle_path_interval:
            path_controller.clear_all_eutester_rules(retry=False)
            status = 'Clearing blocked path'
        return status


    def cycle_method_loop_over_paths_once(self):
        self.debug('Looping over each path once')

    def cycle_method_loop_over_paths_twice(self):
        self.debug('Looping over each path twice')

    def clear_all_rules_on_controller(self, controller, timeout=60):
        controller.clear_all_eutester_rules(timeout=timeout)

    def cleanup(self, instances=True):
        '''
        Attempts to clean up resources created during this test...
        '''
        try:
            for path_controller in self.path_controllers:
                try:
                    host = path_controller.host
                    path_controller.clear_all_eutester_rules(timeout=120)
                except Exception, e:
                    self.debug('Error cleaning up iptables rules on NC:' + str(host) +', Err:'+str(e))
            self.tester.cleanup_artifacts()
        except Exception, e:
            tb = self.tester.get_traceback()
            raise Exception('Cleanupfailed:'+str(e) + "\n" +str(tb))

    def launch_test_instance(self):
        instance = self.get_existing_test_instance(instance_id=self.args.instance_id)
        if not instance:
            instance = self.tester.run_image(image=self.image,
                                                   zone=self.zone,
                                                   min=1,
                                                   max=1,
                                                   group=self.group,
                                                   keypair=self.keypair,
                                                   monitor_to_running=True)[0]
        else:
            instance.init_volume_list()
        if not self.test_tag in instance.tags:
            instance.add_tag(self.test_tag)
        self.instance = instance
        self.create_path_controller_for_instance(instance=instance)
        return instance

    def get_existing_test_instance(self, instance_id=None):
        instances = self.tester.get_connectable_euinstances()
        for instance in instances:
            if instance_id:
                if instance.id == instance_id:
                    return instance
            else:
                if self.test_tag in instance.tags:
                    return instance
        if instance_id:
            raise Exception('Failed to fetch instance from id provided:' +str(self.args.instance_id))
        return None


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


    def create_path_controller_for_instance(self,instance=None):
        path_controller = None
        instance = instance or self.instance
        node = self.get_node_instance_is_running_on(instance=instance)
        for pc in self.path_controllers:
            if pc.node == node:
                path_controller = pc
                break
        if not path_controller:
            paths = self.get_nc_paths_for_instance(instance=instance)
            path_controller = Path_Controller(node=node, sp_ip_list=paths)
        if not path_controller in self.path_controllers:
            self.path_controllers.append(path_controller)
        instance.path_controller = path_controller
        return path_controller


    def get_existing_test_volume(self, tagkey=None):
        if self.args.volume_id:
            volumes = self.tester.get_volumes(status='available',volume_id=str(self.args.volume_id))
            if not volumes:
                raise Exception('Faild to fetch volume from id provided:' +str(self.args.volume_id))
        else:
            tagkey = tagkey or self.test_tag
            volumes = self.tester.get_volumes(status='available', filters={'tag-key':str(tagkey)})
        if volumes:
            return volumes[0]
        return None

    def create_test_volume(self):
        volume = self.get_existing_test_volume()
        if not volume:
            volume = self.tester.create_volume(self.zone, size=self.size)
        self.volume = volume

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
        self.sftp_test_io_script_to_instance()



    def run_remote_script_and_monitor(self,timed_run=0):
        tb = None
        err = None
        exit_value = None
        exit_lines = ""

        original_inter_io_timeout = self.inter_io_timeout
        if timed_run:
            original_inter_io_timeout = self.inter_io_timeout
        path_controller = self.instance.path_controller
        self.path_controller = path_controller
        path_controller.clear_all_eutester_rules()
        path_controller.total_path_iterations=0


        cmd = 'python ' + self.remote_script_path + " -f " + self.test_file_path + ' -t ' + str(timed_run)
        self.stdscr = curses.initscr()
        try:
            signal.signal(signal.SIGWINCH, self.sigwinch_handler)
            now = time.time()
            out = self.instance.ssh.cmd(cmd,
                                  verbose=False,
                                  cb=self.remote_ssh_io_script_monitor_cb,
                                  cbargs=[None,None,None,None,now, now, 'Starting' ])
            exit_value = out['status']
            exit_lines = out['output']
        except Exception, e:
            tb = self.tester.get_traceback()
            debug_string = str(tb) + '\nError caught by remote_ssh_io_monitor_cb:'+str(e)
            self.debug(debug_string)
            if self.stdscr:
                self.stdscr.addstr(0, 0, debug_string)
                self.stdscr.refresh()
            err = str(e)
            raise Exception(str(tb)+ '\nError:' + str(err))
        finally:
            if exit_value is None or exit_value != 0:
                tb = self.tester.get_traceback()
                err = "Remote io script ended with invalid status code:" + str(exit_value) + "\n" + str(exit_lines)
            self.tear_down_curses()
            try:
                path_controller.clear_all_eutester_rules()
            except Exception, pe:
                tb += "\n" + str(pe)
            if tb:
                raise Exception(str(tb)+ '\nError:' + str(err))
            self.debug('Remote Monitor finished successfully, final output:' + "\n".join(exit_lines))


    def tear_down_curses(self):
        if self.stdscr:
            self.stdscr.keypad(0)
            curses.echo()
            curses.nocbreak()
            curses.endwin()
            self.stdscr = None


    #@eutester.Eutester.printinfo
    def remote_ssh_io_script_monitor_cb(self,
                                        buf,
                                        write_value,
                                        write_rate,
                                        read_rate,
                                        last_read,
                                        last_time,
                                        cycle_check_time,
                                        status):
        ret = SshCbReturn(stop=False, settimer=self.inter_io_timeout)
        return_buf = ""
        now = time.time()
        path_controller = self.instance.path_controller
        remaining_iterations = self.max_path_iterations- path_controller.total_path_iterations
        blocked_paths ="BLOCKED_PATHS:"
        completed_iterations = "COMPLETED_ITERATIONS:" + str(path_controller.total_path_iterations)
        remaining_iterations_str = "REMAINING_ITERATIONS:" + str(remaining_iterations)
        write_rate = write_rate or 'WRITE_RATE:'
        write_value = write_value or 'WRITE_VALUE'
        read_rate = read_rate or 'READ_RATE'
        last_read = last_read or 'LAST_READ'

        last_time = last_time or now
        waited = int(now - last_time)
        waited_str = "INTER_IO_SECONDS_WAITED: "+ str(waited)
        time_remaining = "TIME_REMAINING:"

        #Pace cycle checks by at least 1 second
        if now - cycle_check_time >= 5:
            status = self.current_cycle_method()
            cycle_check_time = now
        status_str = 'STATUS:' + str(status)

        blocked_paths += path_controller.get_blocked_string()


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
                           + str(completed_iterations) + "\n" \
                           + str(remaining_iterations_str) + "\n" \
                           + str(time_remaining) + "\n" \
                           + str(status_str) + "\n" \
                           + "ret buf:" + str(return_buf) \
                           + "\n-------------------------------------------------\n"


            if remaining_iterations <= 0:
                debug_string += '\nREMOTE MONITOR FINSIHED SUCCESSFULLY\n'
                self.tear_down_curses()
                self.debug(debug_string)
                ret.statuscode = 0
                ret.stop = True
            else:
                #print "\r\x1b[K"+str(debug_string),
                #sys.stdout.flush()
                if self.stdscr:
                    self.stdscr.clear()
                    self.stdscr.addstr(0, 0, debug_string)
                    self.stdscr.refresh()
        except Exception, e:
            tb = self.tester.get_traceback()
            debug_string = str(tb) + '\nError caught by remote_ssh_io_monitor_cb:'+str(e)
            self.tear_down_curses()
            self.errormsg(debug_string)
            ret.stop = True
            ret.statuscode=69
            pass
        finally:
            ret.nextargs = [ write_value, write_rate,read_rate, last_read, time.time(), cycle_check_time, status]
            ret.buf = return_buf
            return ret



    def sigwinch_handler(self, signal, frame ):
        if self.stdscr:
            curses.endwin()
            self.stdscr = curses.initscr()

    def check_mpath_iterations(self):
        if self.path_controller and self.path_controller.remaining_iterations:
            remaining = self.path_controller.remaining_iterations
            raise Exception('Path Controller did not complete its iterations. Remaining:'+str(remaining))

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
        self.create_path_controller()
        self.path_controller.clear_all_eutester_rules(timeout=120)
        if len(self.path_controller.sp_ip_list) > 1:
            single_path = self.path_controller.sp_ip_list[0]
        else:
            raise Exception('Not enough paths to shut one down for test')
        self.path_controller.block_path(single_path)
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

        self.create_path_controller()
        self.path_controller.clear_all_eutester_rules(timeout=120)
        time.sleep(2)
        self.attach_test_volume()
        if len(self.path_controller.sp_ip_list) > 1:
            single_path = self.path_controller.sp_ip_list[0]
        else:
            raise Exception('Not enough paths to shut one down for test')
        self.path_controller.block_path(single_path)
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









