#!/usr/bin/python
# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2011, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author: matt.clark@eucalyptus.com

"""
Description:
Set of methods to aid in multipath testing. Main test points are ebs usage during blocking and unblocking network i/o to
 device mapper multipath paths via iptables.
 Node Controller Test points:
    -confirm multiple paths are set on the NC and/or SC in order to run test, else will throw 'SkipTestException' for
     testcase class to handle
    -constant i/o on guest mounted volume with read, write, and checks during mpath failovers
    -attach and detach during different phases of path(s) failing over.
    -attach a volume to a guest while a single path is down, verify read/write direct to device on guest
    -attach a volume while a path is in the process of failing
    -attach a volume with all paths in good state, then detach while single path is down.
    -attach a volume to a guest while a single path is down, verify mounted formated volume i/o, verify detach
    -Multiple volume attach/detach checks with different path up/down states.
Storage Controller Test points:
    -If multiple sanhosts are provided in the SC's storage property, will attempt to test sanhost fail over using iptables
    to block network i/o to a given host and iterate through the hosts. Will attempt to create volumes to verify functionality.
    -If multiple scpaths are provided in the storage property, will attempt to block dev mapper paths with iptables, while
    creating snapshots. Will test blocking paths before and during snapshot creation.
"""

__author__ = 'clarkmatthew'


from eutester.eutestcase import EutesterTestCase, SkipTestException
from eutester.eutestcase import TestColor
from eucaops import ec2ops
#from eutester.euinstance import EuInstance
#from eutester.euvolume import EuVolume
#from eutester.eusnapshot import EuSnapshot
from eutester.sshconnection import SshCbReturn
from eutester.euproperties import Euproperty_Type, EupropertyNotFoundException
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

class Mpath_Suite(EutesterTestCase):
    stopped_status = 'STOPPED'
    def __init__(self, tester=None, path_controllers=None, **kwargs):
        #### Pre-conditions
        self.setuptestcase()
        self.setup_parser(testname='Multipath_suite')

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
        self.parser.add_argument('--timed_test_period',
                                 type=int,
                                 help='Number of seconds for timed tests to run instance monitor, default:30',
                                 default=30)

        self.parser.add_argument('--path_recovery_interval',
                                 type=int,
                                 help='Number of seconds to allow a down path to recover before cycling to next, default:30',
                                 default=30)

        self.parser.add_argument('--run_suite',
                                action='store_true', default=True,
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

        self.test_tag = 'mpath_suite'
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
            self.image = self.tester.get_emi(root_device_type="instance-store")
        if not self.image:
            raise Exception('couldnt find instance store image')
        self.clean_method = self.cleanup

        self.timed_test_period = self.args.timed_test_period
        self.instance = None
        self.volumes = []
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
        self.stdscr = None
        self.curses_fd = None
        self.testvol_w_checksum = None


    def get_enabled_storage_controller_for_zone(self, zone=None):
        zone = zone or self.zone
        sc_list = self.tester.service_manager.get_all_storage_controllers(partition=zone, state='ENABLED',use_cached_list=False)
        if sc_list:
            sc = sc_list[0]
        else:
            tb = self.tester.get_traceback()
            raise Exception('\n' + str(tb) + 'No enabled storage controllers found in partition:' + str(zone))
        return sc


    def memo_use_multipathing_check(self):
        if self.has_arg('USE_MULTIPATHING') and re.search('YES', self.args.USE_MULTIPATHING,  re.IGNORECASE):
            self.debug('USE_MULTIPATHING flag set in memo field ')
            return True
        else:
            self.debug('USE_MULTIPATHING flag not set in memo field')
            return False


    def zone_has_multiple_nc_paths(self, zone=None):
        zone = zone or self.zone
        try:
            ncpaths_property = self.tester.property_manager.get_property(service_type=Euproperty_Type.storage,partition=zone,name='ncpaths')
            paths = str(ncpaths_property.value).split(',')
        except EupropertyNotFoundException:
            return False
        if len(paths) > 1:
            self.debug('Multiple paths detected on this systems partition:' +str(zone))
            return True
        else:
            self.debug('Multiple paths NOT detected on this systems partition:' +str(zone))
            return False

    def zone_has_multiple_sc_paths(self, zone=None):
        zone = zone or self.zone
        try:
            scpaths_property = self.tester.property_manager.get_property(service_type=Euproperty_Type.storage,partition=zone,name='scpaths')
            paths = str(scpaths_property.value).split(',')
        except EupropertyNotFoundException:
            return False
        if len(paths) > 1:
            self.debug('Multiple SC paths detected on this systems partition:' +str(zone))
            return True
        else:
            self.debug('Multiple SC paths NOT detected on this systems partition:' +str(zone))
            return False

    def zone_has_multiple_sc_hosts(self, zone=None):
        zone = zone or self.zone
        try:
            schost_property = self.tester.property_manager.get_property(service_type=Euproperty_Type.storage,partition=zone,name='sanhost')
            hosts = str(schost_property.value).split(',')
        except EupropertyNotFoundException:
            return False
        if len(hosts) > 1:
            self.debug('Multiple san hosts detected on this systems partition:' +str(zone))
            return True
        else:
            self.debug('Multiple san hosts not detected on this systems partition:' +str(zone))
            return False

    def pre_test_check_should_run_nc_multipath_tests_on_this_system(self,zone=None):
        zone = zone or self.zone
        if self.zone_has_multiple_nc_paths(zone=zone):
            return True
        if self.memo_use_multipathing_check():
            raise Exception('Multipathing enabled in Memo field, but multiple paths not detected in "ncpaths" property')
        raise SkipTestException('Multiple paths not detected, nor was "USE_MULTIPATHING" flag set in config, exiting w/o running tests')


    def pre_test_check_should_run_sc_multipath_tests_on_this_system(self,zone=None):
        zone = zone or self.zone
        if self.zone_has_multiple_sc_paths(zone=zone):
            return True
        if self.memo_use_multipathing_check():
            raise Exception('Multipathing enabled in Memo field, but multiple paths not detected in "scpaths" property')
        raise SkipTestException('Multiple paths not detected, nor was "USE_MULTIPATHING" flag set in config, exiting w/o running tests')

    def pre_test_check_should_run_sc_multihosts_tests_on_this_system(self,zone=None):
        zone = zone or self.zone
        if self.zone_has_multiple_sc_hosts(zone=zone):
            return True
        raise SkipTestException('Multiple san hosts not detected, exiting w/o running tests')





    def create_controller_for_each_node(self):
        node_list =  self.tester.service_manager.get_all_node_controllers()
        for node in node_list:
            add_to_list = True
            for pc in self.path_controllers:
                if pc.host == node.hostname:
                         add_to_list = False
            if add_to_list:
                paths = self.get_nc_paths_by_node(node)
                path_controller = Path_Controller(node=node, sp_ip_list=paths)
                self.path_controllers.append(path_controller)

    def clear_rules_on_all_nodes(self):
        self.status('Clearing eutester rules on all nodes...')
        self.create_controller_for_each_node()
        for pc in self.path_controllers:
            self.status('Clearing all rules on: ' + str(pc.host) )
            pc.clear_all_eutester_rules()




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
        blocked_paths = "CURRENTLY BLOCKED:" + str(path_controller.get_blocked_string())
        return blocked_paths + ", TEST STATUS:" + status


    def cycle_method_run_guest_io_for_time(self):
        time_run = int(time.time() - self.test_start_time)
        time_remaining = int(self.timed_test_period - time_run)
        if time_remaining > 0:
            status = 'TIME REMAINING IN TEST:' + str(time_remaining)

        else:
            time_remaining = 0
            status = self.stopped_status
        return status



    def cycle_method_loop_over_paths_twice(self):
        self.debug('Looping over each path twice')

    def clear_all_rules_on_controller(self, controller, timeout=60):
        controller.clear_all_eutester_rules(timeout=timeout)

    def cleanup(self, instances=True):
        '''
        Attempts to remove all rules on nodes which were used in test and
        clean up resources created during this test...
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

    def get_test_instance(self):
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
        self.path_controller = instance.path_controller
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


    def get_nc_paths_by_instance(self,instance=None, iface=False):
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

    def get_nc_paths_by_node(self, node, iface=False):
        paths = []
        partition = node.partition.name
        ncpaths_property = self.tester.property_manager.get_property(service_type=Euproperty_Type.storage,partition=partition,name='ncpaths')
        for path in str(ncpaths_property.value).split(','):
            for part in path.split(':'):
                if re.search('iface', part):
                    if iface:
                        paths.append(part)
                elif not iface:
                    paths.append(part)
        return paths

    def get_sc_sanhosts_by_sc(self, sc):
        partition = sc.partition
        sanhost_property = self.tester.property_manager.get_storage_sanhost_value(partition=partition)
        if not sanhost_property:
            tb = self.tester.get_traceback()
            raise Exception('\n' + str(tb) + 'San host property not found for sc:' + str(sc.hostname))
        return sanhost_property.split(',')

    def get_sc_paths_by_sc(self, sc, iface=False):
        paths = []
        partition = sc.partition
        scpaths_property = self.tester.property_manager.get_property(service_type=Euproperty_Type.storage,partition=partition,name='scpaths')
        for path in str(scpaths_property.value).split(','):
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
            paths = self.get_nc_paths_by_instance(instance=instance)
            path_controller = Path_Controller(node=node, sp_ip_list=paths)
        if not path_controller in self.path_controllers:
            self.path_controllers.append(path_controller)
        instance.path_controller = path_controller
        instance.node = node
        return path_controller


    def get_existing_test_volumes(self, tagkey=None):
        volumes = []
        if self.args.volume_id:
            volumes = self.tester.get_volumes(status='available',volume_id=str(self.args.volume_id))
            if not volumes:
                raise Exception('Failed to fetch volume from id provided:' +str(self.args.volume_id))
        else:
            tagkey = tagkey or self.test_tag
            volumes = self.tester.get_volumes(status='available', filters={'tag-key':str(tagkey)})
        return volumes

    def get_test_volumes(self, count=1):
        '''
        Attempt to retrieve a list of volumes created by this test, or a previous run of this test and in available state.
        If the test can not recycle enough test volumes, it will create new ones so 'count' number of test volumes
        can be returned.

        :param count: int representing the number of test volumes desired.
        '''
        volumes = []
        if count == 1 and self.volume:
            self.volume.update()
            if self.volume.status == 'available':
                return [self.volume]
        volumes = self.get_existing_test_volumes()
        if len(volumes) >= count:
            volumes = volumes[0:count]
        elif len(volumes) < count:
            new_volumes = self.tester.create_volumes(self.zone, size=self.size, count=(count-len(volumes)))
            for volume in new_volumes:
                volume.add_tag(str(self.test_tag))
            volumes.extend(new_volumes)
        for volume in volumes:
            if volume not in self.volumes:
                self.volumes.append(volume)
        self.volume = volumes[0]
        return volumes

    def attach_test_volume(self,volume=None):
        volume = volume or self.volume
        try:
            self.instance.attach_volume(volume, timeout=90)
        except ec2ops.VolumeStateException, vse:
            self.status("This is a temp work around for testing, this is to avoid bug euca-5297"+str(vse),
                        testcolor=TestColor.get_canned_color('failred'))
            time.sleep(10)
            self.debug('Monitoring volume post VolumeStateException...')
            volume.eutest_attached_status = None
            self.tester.monitor_euvolumes_to_status([volume],status='in-use',attached_status='attached',timeout=90)


    def mount_volume_and_create_test_file(self, force_mkfs=True):
        mount_point = self.instance.mount_attached_volume(volume=self.volume,force_mkfs=force_mkfs)
        mount_point = str(mount_point).rstrip('/')+'/'
        test_file_path = mount_point+ 'testfile'
        self.instance.sys('touch ' + test_file_path, code=0)
        self.test_file_path = test_file_path

    def get_mpath_info_for_instance_vol(self, instance, vol):
        if not hasattr(instance, 'node'):
            instance.node = self.get_node_instance_is_running_on(instance)
        info = instance.node.get_instance_multipath_dev_info_for_instance_ebs_volume(instance, vol)
        return info

    def print_mpath_info_for_instance_vol(self, instance, vol, mute=False):
        info = "\n".join(self.get_mpath_info_for_instance_vol(instance, vol))
        line = "\n-----------------------------------------------------------------------------------\n"
        header = "\nMPATH INFO --> INSTANCE:" + str(instance.id) + ", VOLUME:" + str(vol.id) + "\n"
        buf = line + header + info + line
        if not mute:
            self.debug(buf, linebyline=False)
        return (buf)

    def sftp_test_io_script_to_instance(self):
        local_script_path =str(self.args.io_script_path)
        remote_script_path = str(os.path.basename(local_script_path))
        self.instance.ssh.sftp_put(local_script_path,remote_script_path)
        self.remote_script_path = remote_script_path


    def setup_instance_volume_and_script(self):
        self.get_test_instance()
        self.get_test_volumes()
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
        try:
            self.stdscr = curses.initscr()
        except Exception, e:
            self.debug('No term cababilties? Curses could not init:' +str(e))
        try:
            signal.signal(signal.SIGWINCH, self.sigwinch_handler)
            now = time.time()
            self.test_start_time = now
            out = self.instance.ssh.cmd(cmd,
                                  verbose=False,
                                  cb=self.remote_ssh_io_script_monitor_cb,
                                  cbargs=[None,None,None,None,now, now, 'Starting', None ])
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
            self.test_end_time = time.time()
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
                                        status,
                                        mpath_status):
        ret = SshCbReturn(stop=False, settimer=self.inter_io_timeout)
        return_buf = ""
        now = time.time()
        path_controller = self.instance.path_controller
        remaining_iterations = self.max_path_iterations- path_controller.total_path_iterations
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
        printout = False
        #Pace cycle checks
        if now - cycle_check_time >= 5:
            status = self.current_cycle_method()
            cycle_check_time = now
            try:
                printout = True
                mpath_status = self.print_mpath_info_for_instance_vol(self.instance, self.volume)
            except Exception, e:
                mpath_status = str(e)

        status_str = 'STATUS:' + str(status)

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
                           + str(completed_iterations) + "\n" \
                           + str(remaining_iterations_str) + "\n" \
                           + str(time_remaining) + "\n" \
                           + str(status_str) + "\n" \
                           + str(mpath_status) + "\n" \
                           + "ret buf:" + str(return_buf) \
                           + "\n-------------------------------------------------\n"


            if remaining_iterations <= 0 or status == self.stopped_status:
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
                elif printout:
                    self.debug(debug_string +
                               str('--------------------------------------------------------------------------------'))
        except Exception, e:
            tb = self.tester.get_traceback()
            debug_string = str(tb) + '\nError caught by remote_ssh_io_monitor_cb:'+str(e)
            self.tear_down_curses()
            self.errormsg(debug_string)
            ret.stop = True
            ret.statuscode=69
            pass
        finally:
            ret.nextargs = [ write_value, write_rate,read_rate, last_read, time.time(), cycle_check_time, status, mpath_status]
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

    def test1_check_volume_io_on_guest_while_blocking_clearing_all_paths_once(self,clean_on_exit=True):
        test_list = []
        errmsg = ''
        self.pre_test_check_should_run_nc_multipath_tests_on_this_system()
        try:
            #Setup and connect to instance, create + attach vol, format vol, scp io script, create test dir/file.
            self.setup_instance_volume_and_script()

            self.max_path_iterations=1
            #Run the remote io script on the test instance, monitor all script output via local call back method
            self.run_remote_script_and_monitor()
        except Exception, e:
            tb = self.tester.get_traceback()
            errmsg = "ERROR:\n" + str(tb) + "\n" + str(e)
            self.debug(errmsg)
        finally:
            if clean_on_exit:
                try:
                    for pc in self.path_controllers:
                        pc.clear_all_eutester_rules()
                    self.instance.terminate_and_verify()
                except Exception, ie:
                    errmsg += '\n' + str(ie)
            if errmsg:
                raise Exception(errmsg)



    def test2_attach_volume_while_a_single_path_is_down(self, wait_after_block=60, mb=1, clean_on_exit=True):
        single_path = None
        length = mb * 1048576
        errmsg = ''
        path_controller = None
        self.pre_test_check_should_run_nc_multipath_tests_on_this_system()
        try:
            self.status('Get test instance to run test...')
            self.get_test_instance()
            path_controller =  self.instance.path_controller
            if len(path_controller.sp_ip_list) > 1:
                single_path = path_controller.sp_ip_list[1]
            else:
                raise Exception('Not enough paths to shut one down for test')
            self.status('Getting volume for use in test...')
            self.get_test_volumes()
            self.status('Checking paths to make sure none are currently blocked...')
            if path_controller.get_blocked_paths():
                self.debug('Clearing blocked paths and sleeping for recovery period:' +
                           str(self.path_recovery_interval) + ' seconds')
                path_controller.clear_all_eutester_rules(timeout=120)
                time.sleep(self.path_recovery_interval)
            self.status('Blocking single path: "' + str(single_path) + '" before attaching volume...')
            path_controller.block_path(single_path)
            self.status('Path is blocked waiting ' + str(wait_after_block) + 'seconds before attach...')
            time.sleep(wait_after_block)
            self.status('Path is blocked, attaching volume...')
            self.attach_test_volume()
            self.print_mpath_info_for_instance_vol(self.instance, self.volume)

            self.status('Mounting volume and creating guest side test env...')

            #self.mount_volume_and_create_test_file()
            #self.sftp_test_io_script_to_instance()
            self.status('Attempting to run some basic io on guest volume...')
            self.instance.vol_write_random_data_get_md5(self.volume, length=length, overwrite=True)
            self.status('Remote io monitor script done, success. Attempting to detach volume now...')
            self.instance.detach_euvolume(self.volume)
        except Exception, e:
            tb = self.tester.get_traceback()
            errmsg = "\n" + str(tb) + "\nERROR: " + str(e)
            self.errormsgg(errmsg)
        finally:
            if clean_on_exit:
                self.status('Tearing down instance after test...')
                try:
                    if path_controller:
                        path_controller.clear_all_eutester_rules()
                    else:
                        for pc in self.path_controllers:
                            pc.clear_all_eutester_rules()
                    self.instance.terminate_and_verify()
                except Exception, ie:
                    errmsg += '\n' + str(ie)
            if errmsg:
                raise Exception(errmsg)

    def test3_attach_volume_while_a_single_path_is_in_process_of_failing(self, clean_on_exit=True):
        single_path = None
        errmsg = ''
        path_controller = None
        self.pre_test_check_should_run_nc_multipath_tests_on_this_system()
        try:
            self.status('Get test instance to run test...')
            self.get_test_instance()
            path_controller =  self.instance.path_controller
            if len(path_controller.sp_ip_list) > 1:
                single_path = path_controller.sp_ip_list[1]
            else:
                raise Exception('Not enough paths to shut one down for test')
            self.status('Getting volume for use in test...')
            self.get_test_volumes()
            self.status('Checking paths to make sure none are currently blocked...')
            if path_controller.get_blocked_paths():
                self.debug('Clearing blocked paths and sleeping for recovery period:' +
                           str(self.path_recovery_interval) + ' seconds')
                path_controller.clear_all_eutester_rules(timeout=120)
                time.sleep(self.path_recovery_interval)
            self.status('Blocking single path: "' + str(single_path) + '" before attaching volume...')
            path_controller.block_path(single_path)
            self.status('Path is blocked, immediately attaching volume while path is in process of failing...')
            self.attach_test_volume()
            self.print_mpath_info_for_instance_vol(self.instance, self.volume)
            self.status('Mounting volume and creating guest side test env...')
            self.mount_volume_and_create_test_file()
            self.sftp_test_io_script_to_instance()
            self.status('Attempting to run some basic io on guest volume...')
            self.instance.vol_write_random_data_get_md5(self.volume, length=1048576, overwrite=True)
            self.status('Remote io done, detaching...')
            self.instance.detach_euvolume(self.volume)
        except Exception, e:
            tb = self.tester.get_traceback()
            errmsg = "\n" + str(tb) + "\nERROR: " + str(e)
            self.errormsg(errmsg)
        finally:
            if clean_on_exit:
                self.status('Tearing down instance after test...')
                try:
                    if path_controller:
                        path_controller.clear_all_eutester_rules()
                    else:
                        for pc in self.path_controllers:
                            pc.clear_all_eutester_rules()
                    self.instance.terminate_and_verify()
                except Exception, ie:
                    errmsg += '\n' + str(ie)
            if errmsg:
                raise Exception(errmsg)



    def test4_detach_volume_with_single_path_down_after_attached(self, wait_after_block=60, clean_on_exit=True):
        single_path = None
        errmsg = ''
        path_controller = None
        self.pre_test_check_should_run_nc_multipath_tests_on_this_system()
        try:
            self.status('Get test instance to run test...')
            self.get_test_instance()
            path_controller =  self.instance.path_controller
            if len(path_controller.sp_ip_list) > 1:
                single_path = path_controller.sp_ip_list[1]
            else:
                raise Exception('Not enough paths to shut one down for test')
            self.status('Getting volume for use in test...')
            self.get_test_volumes()
            self.status('Checking paths to make sure none are currently blocked...')
            if path_controller.get_blocked_paths():
                self.debug('Clearing blocked paths and sleeping for recovery period:' +
                           str(self.path_recovery_interval) + ' seconds')
                path_controller.clear_all_eutester_rules(timeout=120)
                time.sleep(self.path_recovery_interval)

            self.status('Attaching test volume while all paths are up...')
            self.attach_test_volume()
            self.print_mpath_info_for_instance_vol(self.instance, self.volume)
            self.status('Mounting volume and creating guest side test env...')
            self.mount_volume_and_create_test_file()
            self.sftp_test_io_script_to_instance()
            self.status('Attempting to run some basic io on guest volume...')
            self.instance.vol_write_random_data_get_md5(self.volume, length=1048576, overwrite=True)
            self.status('Remote write/read done')
            self.status('Blocking single path: "' + str(single_path) + '" before detaching volume:'
                        + str(self.volume.id) + '...')
            path_controller.block_path(single_path)
            self.status('Waiting ' + str(wait_after_block) + ' seconds after blocking for path to go down...')
            time.sleep(wait_after_block)
            self.status('Detaching volume while path is down...')
            self.instance.detach_euvolume(self.volume)

        except Exception, e:
            tb = self.tester.get_traceback()
            errmsg = "\n" + str(tb) + "\nERROR: " + str(e)
            self.errormsg(errmsg)
        finally:
            if clean_on_exit:
                self.status('Tearing down instance after test...')
                try:
                    if path_controller:
                        path_controller.clear_all_eutester_rules()
                    else:
                        for pc in self.path_controllers:
                            pc.clear_all_eutester_rules()
                    self.instance.terminate_and_verify()
                except Exception, ie:
                    errmsg += '\n' + str(ie)
            if errmsg:
                raise Exception(errmsg)


    def test5_attach_volume_while_a_single_path_is_down_run_io_monitor(self, wait_after_block=60, mb=1, clean_on_exit=True):
        single_path = None
        length = mb * 1048576
        errmsg = ''
        path_controller = None
        self.pre_test_check_should_run_nc_multipath_tests_on_this_system()
        try:
            self.status('Get test instance to run test...')
            self.get_test_instance()
            path_controller =  self.instance.path_controller
            if len(path_controller.sp_ip_list) > 1:
                single_path = path_controller.sp_ip_list[1]
            else:
                raise Exception('Not enough paths to shut one down for test')
            self.status('Getting volume for use in test...')
            self.get_test_volumes()
            self.status('Checking paths to make sure none are currently blocked...')
            if path_controller.get_blocked_paths():
                self.debug('Clearing blocked paths and sleeping for recovery period:' +
                           str(self.path_recovery_interval) + ' seconds')
                path_controller.clear_all_eutester_rules(timeout=120)
                time.sleep(self.path_recovery_interval)
            self.status('Blocking single path: "' + str(single_path) + '" before attaching volume...')
            path_controller.block_path(single_path)
            self.status('Path is blocked waiting ' + str(wait_after_block) + 'seconds before attach...')
            time.sleep(wait_after_block)
            self.status('Path is blocked, attaching volume...')
            self.attach_test_volume()
            self.print_mpath_info_for_instance_vol(self.instance, self.volume)
            self.status('Mounting volume and creating guest side test env...')

            self.mount_volume_and_create_test_file()
            self.sftp_test_io_script_to_instance()
            self.status('Attempting to run some basic io on guest volume...')
            self.run_remote_script_and_monitor()
            #self.instance.vol_write_random_data_get_md5(self.volume, length=length, overwrite=True)
            self.status('Remote io monitor script done, success. Attempting to detach volume now...')
            self.instance.detach_euvolume(self.volume)
        except Exception, e:
            tb = self.tester.get_traceback()
            errmsg = "\n" + str(tb) + "\nERROR: " + str(e)
            self.errormsg(errmsg)
        finally:
            if clean_on_exit:
                self.status('Tearing down instance after test...')
                try:
                    if path_controller:
                        path_controller.clear_all_eutester_rules()
                    else:
                        for pc in self.path_controllers:
                            pc.clear_all_eutester_rules()
                    self.instance.terminate_and_verify()
                except Exception, ie:
                    errmsg += '\n' + str(ie)
            if errmsg:
                raise Exception(errmsg)



    def test6_attach_vol_while_up_and_attach_vol_while_down_detach_both_cases(self,
                                                                              wait_after_block=60,
                                                                              vols_before_block=3,
                                                                              vols_after_block=2,
                                                                              clean_on_exit=True):
        '''
        Attaches 'vols_before_block' number of volumes while paths are not blocked. Then blocks a single path
        and attaches 'vols_after_block' number of volumes while a single path has been blocked.
        Detaches a volume attached before blocking as well as a volume attached after blocking from the instance.
        Clears all paths and detaches all remaining volumes from the instance.
        terminates instance.
        '''

        single_path = None
        before_block = []
        after_block = []
        errmsg = ''
        path_controller = None
        self.pre_test_check_should_run_nc_multipath_tests_on_this_system()
        try:
            self.status('Get test instance to run test...')
            self.get_test_instance()
            path_controller =  self.instance.path_controller
            if len(path_controller.sp_ip_list) > 1:
                single_path = path_controller.sp_ip_list[1]
            else:
                raise Exception('Not enough paths to shut one down for test')
            self.status('Getting volume for use in test...')
            volumes = self.get_test_volumes(count=int(vols_after_block + vols_before_block))
            self.tester.show_volumes(volumes)
            after_block = copy.copy(volumes)
            self.status('Checking paths to make sure none are currently blocked...')
            if path_controller.get_blocked_paths():
                self.debug('Clearing blocked paths and sleeping for recovery period:' +
                           str(self.path_recovery_interval) + ' seconds')
                path_controller.clear_all_eutester_rules(timeout=120)
                time.sleep(self.path_recovery_interval)

            for x in xrange(0, vols_before_block):
                volume = after_block.pop()
                before_block.append(volume)
                self.status('Attaching test volume ' + str(x+1) + ' of ' +str(vols_before_block) + ' while all paths are up...')
                self.attach_test_volume(volume)
                self.print_mpath_info_for_instance_vol(self.instance, volume)
                self.status('Attempting to run some basic io on guest volume...')
                self.instance.vol_write_random_data_get_md5(volume, length=1048576, overwrite=True)
                self.status('Remote write/read done for volume:' +str(volume.id))
            self.status('Attached all ' + str(vols_before_block) + ' volumes before blocking a path')
            self.tester.show_volumes(volumes)
            if after_block:
                self.status('Blocking single path: "' + str(single_path) + "...")
                path_controller.block_path(single_path)
                self.status('Waiting ' + str(wait_after_block) + ' seconds after blocking for path to go down...')
                time.sleep(wait_after_block)
                #Iterate through remaining volumes in list, rename
                for volume in after_block:
                    self.status('Attaching test volume ' + str(after_block.index(volume)) + ' of ' +str(len(after_block)) +
                                'while path:' + str(single_path) + " is down")
                    self.attach_test_volume(volume)
                    self.print_mpath_info_for_instance_vol(self.instance, volume)
                    self.status('Attempting to run some basic io on guest volume...')
                    self.instance.vol_write_random_data_get_md5(volume, length=1048576, overwrite=True)
                    self.status('Remote write/read done for volume:'  + str(volume.id) )
            self.tester.show_volumes(volumes)
            self.status('Detaching a volume while path is down...')
            detach_vols = []
            #Grab a volume from each list to detach
            if before_block:
                detach_vols.append(before_block.pop())
            if after_block:
                detach_vols.append(after_block.pop())
            self.status('Detaching volume(s) from before and after blocking a path(s)')
            for volume in detach_vols:
                self.instance.detach_euvolume(volume)
            if before_block or after_block:
                detach_vols = []
                if before_block:
                    detach_vols.append(before_block.pop())
                if after_block:
                    detach_vols.append(after_block.pop())
                self.status('Clearing blocked paths to detach remaining volumes')
                self.status('Checking paths to make sure none are currently blocked...')
                if path_controller.get_blocked_paths():
                    self.debug('Clearing blocked paths and sleeping for recovery period:' +
                               str(self.path_recovery_interval) + ' seconds')
                    path_controller.clear_all_eutester_rules(timeout=120)
                    time.sleep(self.path_recovery_interval)
                    for volume in detach_vols:
                        self.instance.detach_euvolume(volume)
            before_block.extend(after_block)
            self.tester.show_volumes(volumes)
            self.status('terminating instance with ' + str(len(before_block)) + ' volumes attached')

        except Exception, e:
            tb = self.tester.get_traceback()
            errmsg = "\n" + str(tb) + "\nERROR: " + str(e)
            self.errormsg(errmsg)
        finally:
            if clean_on_exit:
                self.status('Tearing down instance after test...')
                try:
                    if path_controller:
                        path_controller.clear_all_eutester_rules()
                    else:
                        for pc in self.path_controllers:
                            pc.clear_all_eutester_rules()
                    self.instance.terminate_and_verify()
                except Exception, ie:
                    errmsg += '\n' + str(ie)
            if errmsg:
                raise Exception(errmsg)

    def test7_test_storage_controller_sanhost_fallback(self,zone=None, wait_for_host=120):
        zone = zone or self.zone
        errmsg=""
        self.pre_test_check_should_run_sc_multihosts_tests_on_this_system(zone)
        self.status('Attempting to get enabled sc and sanhosts from zone:' +str(zone))
        sc = self.get_enabled_storage_controller_for_zone(zone=zone)
        sanhosts = self.get_sc_sanhosts_by_sc(sc)
        if not len(sanhosts) > 1:
            raise SkipTestException('Skipping test - Did not find > 1 host in sanhost property:' + str(sanhosts))
        pc = Path_Controller(node=sc,sp_ip_list=sanhosts)
        if pc.get_blocked_paths():
            pc.clear_all_eutester_rules()
            time.sleep(60)
        self.status('Attempting to iterate through list of sanhosts, block host, create vol, then clear host...')
        hostcount=0
        try:
            for host in sanhosts:
                hostcount += 1
                self.status('Attempting to block host: ' + str(host) + ' count(' + str(hostcount) + '/' + str(len(sanhosts)) + ')')
                pc.block_path(host)
                volume = self.tester.create_volume(zone=zone, size=1)
                self.tester.delete_volume(volume=volume, timeout=300)
                self.status('Done with host:' + str(host) + ', clearing rules and sleeping for ' + str(wait_for_host) +' seconds')
                pc.clear_all_eutester_rules()
                time.sleep(wait_for_host)
            self.status('Success - Created a volume while blocking network i/o to each sanhost')
            self.debug('Make sure all paths are unblocked on SC...')
        except Exception, e:
            tb = self.tester.get_traceback()
            errmsg += '\n' + str(tb) + '\n Caught error:' + str(e)
            self.debug(errmsg, linebyline=False)
        finally:
            try:
                pc.clear_all_eutester_rules()
            except Exception, ce:
                errmsg += '\n' + str(ce)
            if errmsg:
                raise Exception(errmsg)


    def create_local_test_volume_checksum(self, instance):
        gb =1073741824
        mb = 1048576
        self.status('Getting a unique md5 sum for volume...')
        vol = self.get_test_volumes()[0]
        instance.attach_volume(volume=vol)
        dd_dict = instance.random_fill_volume(vol,length=mb)
        wrote1 = int(dd_dict['dd_bytes'])
        dd_dict2 = instance.dd_monitor(ddif='/dev/zero', ddof=vol.guestdev, ddbytes= (gb - wrote1), ddseek=dd_dict['dd_bytes'] )
        wrote2 = int(dd_dict2['dd_bytes'])
        instance.get_dev_md5(vol.guestdev, length=(wrote1+wrote2), timeout=90)
        self.testvol_w_checksum = vol
        return vol

    def test8_test_storage_controller_path_fail_then_create_snapshot(self,):
        errmsg = ""
        self.pre_test_check_should_run_sc_multipath_tests_on_this_system()
        self.status('Get test instance to run test...')
        instance = self.get_test_instance()
        zone = str(instance.placement)
        self.status('Attempting to get enabled sc and scpaths from zone:' +str(zone))
        sc = self.get_enabled_storage_controller_for_zone(zone=zone)
        paths = self.get_sc_paths_by_sc(sc)
        pc = Path_Controller(node=sc,sp_ip_list=paths)
        self.status('Clearing all eutester rules on: ' + str(pc.host))
        if pc.get_blocked_paths():
            pc.clear_all_eutester_rules()
            time.sleep(60)
        vol = self.testvol_w_checksum or self.create_local_test_volume_checksum(instance=instance)
        paths_to_block = copy.copy(pc.sp_ip_list)
        dont_block = paths_to_block.pop()
        paths_to_block_string =",".join(paths_to_block)
        self.status('Unblocked:' + str(dont_block) + ', Blocking paths:' + str(paths_to_block_string) + ', on SC:' + str(pc.host))
        try:
            for path in paths_to_block:
                pc.block_path(path)
            self.status('Creating Snapshot with path ' + str(paths_to_block_string) + ', blocked...')
            test_snap = self.tester.create_snapshots(volume=vol, wait_on_progress=40, monitor_to_completed=True)[0]
            self.status('Created snapshot, now verifying snapshot integrity from volume md5 check...')
            self.status('Creating volume from test snapshot...')
            vol_from_snap = self.tester.create_volume(zone=self.zone, snapshot=test_snap)
            self.status('Attaching volume created from test snapshot to verify md5sum against original...')
            instance.attach_volume(volume=vol_from_snap)
            instance.md5_attached_euvolume(vol_from_snap, length=vol.md5len)
            if vol.md5 != vol_from_snap.md5:
                raise Exception('Vol created from snapshot md5(' + str(vol_from_snap.md5)+'/' + str(vol_from_snap.md5len) +
                                ') != original volume(' + str(vol.md5) + '/' + str(vol.md5len) + ')')
            else:
                self.debug('SUCCESS: Vol created from snapshot md5(' + str(vol_from_snap.md5)+'/' + str(vol_from_snap.md5len) +
                           ') == original volume(' + str(vol.md5) + '/' + str(vol.md5len) + ')')
        except Exception, e:
            tb = self.tester.get_traceback()
            errmsg += '\n' + str(tb) + '\n Caught error:' + str(e)
            self.debug(errmsg,linebyline=False)
        finally:
            try:
                pc.clear_all_eutester_rules()
            except Exception, ce:
                errmsg += '\n' + str(ce)
            if errmsg:
                raise Exception(errmsg)


    def test9_test_storage_controller_path_fail_while_create_snapshot_in_progress(self):
        errmsg=""
        self.pre_test_check_should_run_sc_multipath_tests_on_this_system()
        self.status('Get test instance to run test...')
        instance = self.get_test_instance()
        zone = str(instance.placement)
        self.status('Attempting to get enabled sc and scpaths from zone:' +str(zone))
        sc = self.get_enabled_storage_controller_for_zone(zone=zone)
        paths = self.get_sc_paths_by_sc(sc)
        if not len(paths) > 1:
            raise SkipTestException('Skipping test - Did not find > 1 path in scpaths property:' + str(paths))
        pc = Path_Controller(node=sc,sp_ip_list=paths)
        self.status('Clearing all eutester rules on: ' + str(pc.host))
        if pc.get_blocked_paths():
            pc.clear_all_eutester_rules()
            time.sleep(60)
        self.status('Getting volume with unique checksum...')
        vol = self.testvol_w_checksum or self.create_local_test_volume_checksum(instance=instance)
        path_to_block = pc.sp_ip_list[0]
        self.status('Creating snapshot, then monitoring to at least 1% progress before blocking path...')
        snap = self.tester.create_snapshots(volume=vol, wait_on_progress=40, monitor_to_completed=False)[0]
        self.tester.monitor_eusnaps_to_completed(snaps=[snap],monitor_to_progress=1)
        snap.update()
        self.status('Snap progress'+ str(snap.progress) +', Blocking path:' + str(path_to_block) + ', on SC:' + str(pc.host))
        try:
            pc.block_path(path_to_block)
            self.status('Monitoring snapshot to completed state...')
            self.tester.monitor_eusnaps_to_completed(snaps=[snap])
            self.status('Created snapshot, now verifying snapshot integrity from volume md5 check...')
            self.status('Creating volume from test snapshot...')
            vol_from_snap = self.tester.create_volume(zone=self.zone, snapshot=snap)
            self.status('Attaching volume created from test snapshot to verify md5sum against original...')
            instance.attach_volume(volume=vol_from_snap)
            instance.md5_attached_euvolume(vol_from_snap, length=vol.md5len)
            if vol.md5 != vol_from_snap.md5:
                raise Exception('Vol created from snapshot md5(' + str(vol_from_snap.md5)+'/' + str(vol_from_snap.md5len) +
                                ') != original volume (' + str(vol.md5) + '/' + str(vol.md5len) + ')')
            else:
                self.debug('SUCCESS: Vol created from snapshot md5(' + str(vol_from_snap.md5)+'/' + str(vol_from_snap.md5len) +
                           ') == original volume(' + str(vol.md5) + '/' + str(vol.md5len) + ')')
        except Exception, e:
            tb = self.tester.get_traceback()
            errmsg += '\n' + str(tb) + '\n Caught error:' + str(e)
            self.debug(errmsg, linebyline=False)
        finally:
            try:
                pc.clear_all_eutester_rules()
            except Exception, ce:
                errmsg += '\n' + str(ce)
            if errmsg:
                raise Exception(errmsg)


    def sc_test_suite(self):
        '''
        SC test suite includes testing dev mapper multipath during snapshot creation, as well as sanhost fallback tests
        '''
        self.cycle_paths = True
        test_list = []
        test_list.append(self.create_testunit_from_method(self.test7_test_storage_controller_sanhost_fallback))
        test_list.append(self.create_testunit_from_method(self.test8_test_storage_controller_path_fail_then_create_snapshot))
        test_list.append(self.create_testunit_from_method(self.test9_test_storage_controller_path_fail_while_create_snapshot_in_progress))
        return test_list

    def test_suite(self):
        '''
        Full test suite includes both NC and SC tests
        '''
        test_list = []
        test_list.extend(self.nc_test_suite())
        test_list.extend(self.sc_test_suite())
        return test_list

    def nc_test_suite(self):
        '''
        NC test suite includes testing volume attach, detach, and i/o operations during different stages of path fail over
        and recovery.
        '''
        self.cycle_paths = True
        test_list = []
        #test_list.append(self.create_testunit_from_method(self.pre_test_check_should_run_multipath_tests_on_this_system, eof=True))
        test_list.append(self.create_testunit_from_method(self.test1_check_volume_io_on_guest_while_blocking_clearing_all_paths_once, eof=True))
        test_list.append(self.create_testunit_from_method(self.test2_attach_volume_while_a_single_path_is_down))
        test_list.append(self.create_testunit_from_method(self.test3_attach_volume_while_a_single_path_is_in_process_of_failing))
        test_list.append(self.create_testunit_from_method(self.test4_detach_volume_with_single_path_down_after_attached))
        test_list.append(self.create_testunit_from_method(self.test5_attach_volume_while_a_single_path_is_down_run_io_monitor))
        test_list.append(self.create_testunit_from_method(self.test6_attach_vol_while_up_and_attach_vol_while_down_detach_both_cases))
        return test_list

if __name__ == "__main__":
    testcase = Mpath_Suite()

    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    if testcase.args.run_suite:
        unit_list = testcase.test_suite()
    else:
        test_names = testcase.args.tests or ['test1_check_volume_io_on_guest_while_blocking_clearing_all_paths_once']
        ### Convert test suite methods to EutesterUnitTest objects
        unit_list = [ ]
        for test in test_names:
            unit_list.append(testcase.create_testunit_by_name(test))

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,eof=False,clean_on_exit=True)
    sys.exit(result)









