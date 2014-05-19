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
# Author: vic.iglesias@eucalyptus.com
import select
import threading
import time
import eulogger
from eutester import Eutester
from eutester.euconfig import EuConfig
import sshconnection
import re
import os
import sys
import tempfile
from repoutils import RepoUtils

class DistroName:
    ubuntu = "ubuntu"
    rhel = "rhel"
    centos = "centos"
    fedora = "fedora"
    debian = "debian"
    vmware = "vmware"

class DistroRelease:
    def __init__(self, distro_name, distro_number,  distro_release = "", package_manager= None):
        self.name = distro_name
        self.number = distro_number
        self.release = distro_release
        self.package_manager = package_manager
        
class Distro:
    ubuntu_lucid = DistroRelease(DistroName.ubuntu,"10.04",  "lucid",  package_manager="apt")
    ubuntu_precise = DistroRelease(DistroName.ubuntu,  "12.04", "precise",  package_manager="apt")
    debian_squeeze = DistroRelease(DistroName.debian, "6", "squeeze",  package_manager="apt")
    debian_wheezy = DistroRelease(DistroName.debian, "7", "wheezy",  package_manager="apt")
    rhel_6 = DistroRelease(DistroName.rhel, "6",  package_manager="yum")
    centos_6 = DistroRelease(DistroName.centos, "6",  package_manager="yum")
    rhel_5 = DistroRelease(DistroName.rhel, "5",  package_manager="yum")
    centos_5 = DistroRelease(DistroName.centos, "5",  package_manager="yum")
    fedora_18 = DistroRelease(DistroName.fedora, "18",  package_manager="yum")
    vmware_5 = DistroRelease(DistroName.vmware, "5")
    vmware_4 = DistroRelease(DistroName.vmware, "4")

    @classmethod
    def get_distros(Distro):
        distros = []
        for distro in Distro.__dict__:
            if isinstance(Distro.__dict__[distro], DistroRelease):
                distros.append(Distro.__dict__[distro])
        return distros
        
    

class Machine:
    def __init__(self, 
                 hostname, 
                 distro="", 
                 distro_ver="", 
                 arch="", 
                 source="", 
                 components="", 
                 connect=True, 
                 password=None, 
                 keypath=None, 
                 username="root", 
                 timeout=120,
                 retry=2,
                 debugmethod=None, 
                 verbose = True ):
        
        self.hostname = hostname
        self.distro_ver = distro_ver
        self.arch = arch
        self.source = source
        self.components = components
        self.connect = connect
        self.password = password
        self.keypath = keypath
        self.username = username
        self.timeout = timeout
        self.retry = retry
        self.debugmethod = debugmethod
        self.verbose = verbose
        self._distroname = distro
        self.log_threads = {}
        self.log_buffers = {}
        self.log_active = {}
        self.wget_last_status = 0
        if self.debugmethod is None:
            logger = eulogger.Eulogger(identifier= str(hostname) + ":" + str(components))
            self.debugmethod = logger.log.debug
        self._ssh = None
        self._sftp = None
        self._distro = None
        self._repo_utils = None
        self._package_manager = None
        self._config = None

    @property
    def distro(self):
        # If we were given a conf file, and have an ssh/sftp session,
        # attempt to populate eucalyptus_conf into
        # a euconfig object for this machine...
        if not self._distro:
            self._distro = self._get_distro(distro_name=self._distroname,
                                            distro_release=self.distro_ver)
        return self._distro

    @distro.setter
    def distro(self, new_distro):
        self._distro = new_distro

    @property
    def repo_utils(self):
        if not self._repo_utils:
            if self.distro and self.distro.package_manager is not None:
                self._repo_utils = RepoUtils(self, self.distro.package_manager)
        return self._repo_utils

    @repo_utils.setter
    def repo_utils(self, new_repotutils):
        self._repo_utils = new_repotutils

    @property
    def package_manager(self):
        if not self._package_manager:
            if self.distro and self.distro.package_manager is not None:
                self._package_manager = self.repo_utils.package_manager
        return self._package_manager

    @package_manager.setter
    def package_manager(self, new_package_manager):
        self._package_manager = new_package_manager

    @property
    def config(self):
        if not self._config:
            self._config = self.get_eucalyptus_conf()
        return self._config

    @config.setter
    def config(self, new_config):
        self._config = new_config

    @property
    def ssh(self):
        if not self._ssh:
            if self.connect:
                self._ssh = sshconnection.SshConnection(
                    self.hostname,
                    keypath=self.keypath,
                    password=self.password,
                    username=self.username,
                    timeout=self.timeout,
                    retry=self.retry,
                    debugmethod=self.debugmethod,
                    verbose=True)
        return self._ssh

    @ssh.setter
    def ssh(self, newssh):
        self._ssh = newssh

    @property
    def sftp(self):
        if not self._sftp:
            self._sftp = self.ssh.connection.open_sftp()
        return self._sftp

    @sftp.setter
    def sftp(self, newsftp):
        self._sftp = newsftp

    @property
    def eucalyptus_conf(self):
        if hasattr(self.config, 'eucalyptus_conf'):
            return self.config.eucalyptus_conf
        return None

    def get_distro_info_from_machine(self):
        if not self.ssh:
            raise Exception('Need SSH connection to retrieve distribution info from machine')
        ret_dict = {'distro': '', 'release': ''}
        out = self.sys('cat /etc/*-release',code=0)
        for line in out:
            if not ret_dict['distro']:
                if re.search('red hat', line, re.IGNORECASE):
                    ret_dict['distro'] = DistroName.rhel
                else:
                    for distro in DistroName.__dict__:
                        if not str(distro).startswith('_') and re.search(distro,line, re.IGNORECASE):
                            ret_dict['distro'] = distro
                            break
            if not ret_dict['release'] and re.search(r"release", line, re.IGNORECASE):
                rel = re.search(r"\d+\.\d+",line)
                if rel:
                     ret_dict['release'] = rel.group()
        if not ret_dict['distro'] or not ret_dict['release']:
            raise Exception('Could not retrieve distro:"' + str(ret_dict['distro']) + '", and release:"' + str(ret_dict['release']) + '"' )
        return ret_dict


    def _get_distro(self, distro_name=None, distro_release=None):
        if not distro_name or not distro_release:
            self.debug('distro_name and/or distro_release were not provided. Attempt to retrieve from ssh...')
            dist_info = self.get_distro_info_from_machine()
            distro_name  = dist_info['distro']
            distro_releae = dist_info['release']
        return self._convert_to_distro(distro_name=distro_name, distro_release=distro_release)

    def _convert_to_distro(self, distro_name, distro_release):
        distro_name = distro_name.lower()
        distro_release = distro_release.lower()
        for distro in Distro.get_distros():
            if re.search( distro.name, distro_name,re.IGNORECASE) and \
                    (re.search( distro.release, distro_release,re.IGNORECASE) or
                         re.search( distro.number, distro_release,re.IGNORECASE)) :
                return distro
        raise Exception("Unable to find distro " + str(distro_name) + " and version "
                        + str(distro_release) + " for hostname " + str(self.hostname))

    def put_templated_file(self, local_src, remote_dest, **kwargs):
        tmp = tempfile.mktemp()
        try:
            Eutester.render_file_template(local_src, tmp, **kwargs)
            self.ssh.sftp_put(tmp, remote_dest)
        finally:
            os.remove(tmp)

    def refresh_ssh(self):
        self.ssh.refresh_connection()
        
    def debug(self,msg):
        """
        Used to print debug, defaults to print() but over ridden by self.debugmethod if not None
        msg - mandatory -string, message to be printed
        """
        if self.verbose is True:
                self.debugmethod(msg)
                
    def refresh_connection(self):
        self.ssh.refresh_connection()

    def reboot(self, force=True):
        if force:
            try:
                self.sys("reboot -f", timeout=3)
            except Exception, e:
                pass
        else:
            try:
                self.sys("reboot", timeout=3)
            except Exception, e:
                pass
    
    def interrupt_network(self, time = 120, interface = "eth0"):
        try:
            self.sys("ifdown " + interface + " && sleep " + str(time) + " && ifup " + interface,  timeout=3)
        except Exception,e:
            pass

    def sys(self, cmd, verbose=True, timeout=120, listformat=True, code=None):
        '''
        Issues a command against the ssh connection to this instance
        Returns a list of the lines from stdout+stderr as a result of the command
        '''
        return self.ssh.sys(cmd, verbose=verbose, timeout=timeout,listformat=listformat, code=code)
    
    def cmd(self, cmd, verbose=True, timeout=120, listformat=False, cb=None, cbargs=[]):
        '''
        Issues a command against the ssh connection to this instance
        returns dict containing:
            ['cmd'] - The command which was executed
            ['output'] - The std out/err from the executed command
            ['status'] - The exit (exitcode) of the command, in the case a call back fires, this status code is unreliable.
            ['cbfired']  - Boolean to indicate whether or not the provided callback fired (ie returned False)
            ['elapsed'] - Time elapsed waiting for command loop to end. 
        cmd - mandatory - string, the command to be executed 
        verbose - optional - boolean flag to enable debug
        timeout - optional - command timeout in seconds 
        listformat -optional - specifies returned output in list of lines, or single string buffer
        cb - optional - call back function, accepting string buffer, returning true false see sshconnection for more info
        '''
        if (self.ssh is not None):
            return self.ssh.cmd(cmd, verbose=verbose, timeout=timeout, listformat=listformat, cb=cb, cbargs=cbargs)
        else:
            raise Exception("Euinstance ssh connection is None")
        
    def sys_until_found(self, cmd, regex, verbose=True, timeout=120, listformat=True):
        '''
        Run a command until output of command satisfies/finds regex or EOF is found. 
        returns dict containing:
            ['cmd'] - The command which was executed
            ['output'] - The std out/err from the executed command
            ['status'] - The exit (exitcode) of the command, in the case a call back fires, this status code is unreliable.
            ['cbfired']  - Boolean to indicate whether or not the provided callback fired (ie returned False)
            ['elapsed'] - Time elapsed waiting for command loop to end.
        cmd - mandatory - string, the command to be executed 
        regex - mandatory - regex to look for
        verbose - optional - boolean flag to enable debug
        timeout - optional - command timeout in seconds 
        listformat -optional - specifies returned output in list of lines, or single string buffer 
        '''
        return self.cmd(cmd, verbose=verbose,timeout=timeout,listformat=listformat,cb=self.str_found_cb, cbargs=[regex, verbose])
        
        
    def str_found_cb(self,buf,regex,verbose,search=True):
        '''
        Return sshcbreturn type setting stop to True if given regex matches against given string buf
        '''
        if verbose:
            self.debug(str(buf))
        return sshconnection.SshCbReturn( stop=self.str_found(buf, regex=regex, search=search))
        
        
    def str_found(self, buf, regex, search=True):
        '''
        Return True if given regex matches against given string
        '''
        if search:
            found = re.search(regex,buf)
        else:
            found = re.match(regex, buf)
        if found:
            return True
        else:
            return False

    def get_eucalyptus_service_pid(self, eucalyptus_service):
        """
        Returns the process id or pid of the eucalyptus service running on this machine. Will return None if not found,
        which may indicate the process is not running or not intended to run on this machine.

        :param eucalyptus_service: eucalyptus-cloud, eucalyptus-cc, eucalyptus-nc
        :return: string representing pid
        """
        pid = None
        paths = ["/var/run/eucalyptus/","/opt/eucalyptus/var/run/eucalyptus/"]
        for path in paths:
            try:
                pid = int(self.sys('cat ' + path + str(eucalyptus_service), code=0)[0].strip())
                break
            except: pass
        if pid is None:
            self.debug("Pid not found at paths: ".join(paths))
        return pid

    def get_eucalyptus_cloud_pid(self):
        """
        :return: Returns the process id for eucalyptus-cloud running on this machine, or None if not found.
        """
        return self.get_eucalyptus_service_pid('eucalyptus-cloud.pid')

    def get_eucalyptus_nc_pid(self):
        """
        :return: Returns the process id for eucalyptus-nc running on this machine, or None if not found.
        """
        return self.get_eucalyptus_service_pid('eucalyptus-nc.pid')

    def get_eucalyptus_cc_pid(self):
        """
        :return: Returns the process id for eucalyptus-cc running on this machine, or None if not found.
        """
        return self.get_eucalyptus_service_pid('eucalyptus-cc.pid')

    def get_uptime(self):
        return int(self.sys('cat /proc/uptime', code=0)[0].split()[1].split('.')[0])

    def get_eucalyptus_cloud_process_uptime(self):
        """
        Attempts to look up the elapsed running time of the PID associated with the eucalyptus-cloud process/service.
        :return: (int) elapsed time in seconds this PID has been running
        """
        pid = self.get_eucalyptus_cloud_pid()
        return self.get_elapsed_seconds_since_pid_started(pid)

    def get_eucalyptus_cc_process_uptime(self):
        """
        Attempts to look up the elapsed running time of the PID associated with the eucalyptus-cc process/service.
        :return: (int) elapsed time in seconds this PID has been running
        """
        pid = self.get_eucalyptus_cc_pid()
        return self.get_elapsed_seconds_since_pid_started(pid)

    def get_eucalyptus_nc_process_uptime(self):
        """
        Attempts to look up the elapsed running time of the PID associated with the eucalyptus-nc process/service.
        :return: (int) elapsed time in seconds this PID has been running
        """
        pid = self.get_eucalyptus_nc_pid()
        return self.get_elapsed_seconds_since_pid_started(pid)

    def get_eucalyptus_cloud_is_running_status(self):
        """
        Checks eucalyptus-cloud service status
        :return: boolean, True if running False if not.
        """
        return self.get_service_is_running_status('eucalyptus-cloud')

    def get_eucalyptus_cc_is_running_status(self):
        """
        Checks eucalyptus-cc service status
        :return: boolean, True if running False if not.
        """
        return self.get_service_is_running_status('eucalyptus-cc')

    def get_eucalyptus_nc_is_running_status(self):
        """
        Checks eucalyptus-nc service status
        :return: boolean, True if running False if not.
        """
        return self.get_service_is_running_status('eucalyptus-nc')


    def get_service_is_running_status(self, service, code=0):
        """
        Checks status of service 'service' on the machine obj.
        :param service: string representing service name
        :return: boolean.
        """
        try:
            self.sys("service " + str(service) + " status", code=0)
            return True
        except sshconnection.CommandExitCodeException:
            return False
        except Exception, e:
            self.debug('Could not get "'+ str(service) + '" service state from machine:'
                       + str(self.hostname) + ", err:"+str(e))

    def get_elapsed_seconds_since_pid_started(self, pid):
        """
        Attempts to parse ps time elapsed since process/pid has been running and return the presented time in
        elapsed number of seconds.
        :param pid: Process id to get elapsed time from
        :return: Elapsed time in seconds that pid has been running
        """
        seconds_min = 60
        seconds_hour = 3600
        seconds_day = 86400
        elapsed = 0
        try:
            if not pid:
                raise Exception('Empty pid passed to get_elapsed_seconds_since_pid_started')
            cmd = "ps -eo pid,etime | grep " + str(pid) + " | awk '{print $2}'"
            self.debug('starting get pid uptime"' + str(cmd) + '"...')
            #expected format: days-HH:MM:SS
            out = self.sys(cmd,code=0)[0]
            out = out.strip()
            if re.search("-", out):
                split_out = out.split("-")
                days =  int(split_out[0])
                time_string = split_out[1]
            else:
                days = 0
                time_string = out

            split_time = time_string.split(':')
            #insert a 0 if hours, and minutes are not present.
            for x in xrange(len(split_time), 3):
                split_time.insert(0,0)

            hours = int(split_time[0] or 0)
            minutes = int(split_time[1] or 0)
            seconds = int(split_time[2] or 0)
            elapsed = seconds + (minutes*seconds_min) + (hours*seconds_hour) + (days*seconds_day)
        except:
            print Eutester.get_traceback()
        return int(elapsed)

    def get_eucalyptus_version(self,versionpath="/etc/eucalyptus/eucalyptus-version"):
        """

        :param versionpath: path to version file
        :return: eucalyptus version string
        """
        try:
            return self.sys('cat ' + versionpath, code=0)[0]
        except Exception, e:
            return self.sys('cat /opt/eucalyptus' + versionpath, code=0)[0]



    def is_file_present(self, filepath):
        try:
            self.get_file_stat(filepath)
        except IOError, io:
            #IOError: [Errno 2] No such file
            if io.errno == 2:
                return False
            else:
                raise io
        return True


    def get_file_stat(self,path):
        return self.sftp.lstat(path)
        
    def get_file_size(self, path):
        return self.sftp.lstat(path).st_size
    
    def get_file_perms_flag(self,path):
        return self.sftp.lstat(path).FLAG_PERMISSIONS 
    
    def get_file_groupid(self, path):
        return self.sftp.lstat(path).st_gid
        
    def get_file_userid(self,path):
        return self.sftp.lstat(path).st_uid
    
    def get_masked_pass(self, pwd, firstlast=True, charcount=True, show=False):
        '''
        format password for printing
        options:
        pwd - string- the text password to format
        firstlast -boolean - show the first and last characters in pwd
        charcount -boolean - print a "*" for each char in pwd, otherwise return fixed string '**hidden**'
        show - boolean - convert pwd to str() and return it in plain text
        '''
        ret =""
        if pwd is None:
            return ""
        if show is True:
            return str(pwd)
        if charcount is False:
            return "**hidden**"
        for x in xrange(0,len(pwd)):
            if (x == 0 or x == len(pwd)) and firstlast:
                ret = ret+pwd[x]
            else:
                ret += "*"

    def mkfs(self, partition, type="ext3"):
        self.sys("mkfs."+ type + " -F " + partition)

    def mount(self, device, path):
        self.sys("mount "+ device + " " + path)

    def chown(self, user, path):
        self.sys("chwon "+ user + ":" + user + " " + path)

    def ping_check(self,host):
        out = self.ping_cmd(host)
        self.debug('Ping attempt to host:'+str(host)+", status code:"+str(out['status']))
        if out['status'] != 0:
            raise Exception('Ping returned error:'+str(out['status'])+' to host:'+str(host))
    
    def ping_cmd(self, host, count=2, pingtimeout=10, commandtimeout=120, listformat=False, verbose=True):
        cmd = 'ping -c ' +str(count)+' -t '+str(pingtimeout)
        if verbose:
            cmd += ' -v '
        cmd = cmd + ' '+ str(host)
        out = self.cmd(cmd, verbose=verbose, timeout=commandtimeout, listformat=listformat)
        if verbose:
            #print all returned attributes from ping command dict
            for item in sorted(out):
                self.debug(str(item)+" = "+str(out[item]) )  
        return out
        
        
    def dump_netfail_info(self,ip=None, mac=None, pass1=None, pass2=None, showpass=True, taillength=50):
        """
        Debug method to provide potentially helpful info from current machine when debugging connectivity issues.
        """
        self.debug('Attempting to dump network information, args: ip:' + str(ip)
                   + ' mac:' + str(mac)
                   + ' pass1:' + self.get_masked_pass(pass1,show=True)
                   + ' pass2:' + self.get_masked_pass(pass2,show=True))
        self.ping_cmd(ip,verbose=True)
        self.sys('arp -a')
        self.sys('dmesg | tail -'+str(taillength))
        self.sys('cat /var/log/messages | tail -'+str(taillength))
        
    def found(self, command, regex, verbose=True):
        """ Returns a Boolean of whether the result of the command contains the regex"""
        result = self.sys(command, verbose=verbose)
        if result is None or result == []:
            return False
        for line in result:
            found = re.search(regex,line)
            if found:
                return True
        return False   
    
    def wget_remote_image(self,
                          url,
                          path=None,
                          dest_file_name=None,
                          user=None,
                          password=None,
                          retryconn=True,
                          timeout=300):
        self.debug('wget_remote_image, url:'+str(url)+", path:"+str(path))
        cmd = 'wget '
        if path:
            cmd = cmd + " -P " + str(path)
        if dest_file_name:
            cmd = cmd + " -O " + str(dest_file_name)
        if user:
            cmd = cmd + " --user " + str(user)
        if password:
            cmd = cmd + " --password " + str(password)
        if retryconn:
            cmd += ' --retry-connrefused '
        cmd = cmd + ' ' + str(url)
        self.debug('wget_remote_image cmd: '+str(cmd))
        ret = self.cmd(cmd, timeout=timeout, cb=self.wget_status_cb )
        if ret['status'] != 0:
            raise Exception('wget_remote_image failed with status:'+str(ret['status']))
        self.debug('wget_remote_image succeeded')
    
    def wget_status_cb(self, buf):
        ret = sshconnection.SshCbReturn(stop=False)
        try:
            buf = buf.strip()
            val = buf.split()[0] 
            if val != self.wget_last_status:
                if re.match('^\d+\%',buf):
                    sys.stdout.write("\r\x1b[K"+str(buf))
                    sys.stdout.flush()
                    self.wget_last_status = val
                else:
                    print buf
        except Exception, e:
            pass
        finally:
            return ret

            
        
    def get_df_info(self, path=None, verbose=True):
        """
        Return df's output in dict format for a given path.
        If path is not given will give the df info for the current working dir used in the ssh
        session this command is executed in (ie: /home/user or /root).
        path - optional -string, used to specifiy path to use in df command. Default is PWD of ssh shelled command
        verbose - optional -boolean, used to specify whether or debug is printed during this command.
        Example:
            dirpath = '/disk1/storage'
            dfout = self.get_df_info(path=dirpath)
            available_space = dfout['available']
            mounted_on = dfout['mounted']
            filesystem = dfout['filesystem']
        """
        ret = {}
        if path is None:
            path = '${PWD}'
        cmd = 'df '+str(path)
        if verbose:
            self.debug('get_df_info cmd:'+str(cmd))
        output = self.sys(cmd, code=0)
        # Get the presented fields from commands output,
        # Convert to lowercase, use this as our dict keys
        fields=[]
        line = 0
        for field in str(output[line]).split():
            fields.append(str(field).lower())
        # Move line forward and gather columns into the dict to be returned
        x = 0 
        line += 1
        # gather columns equal to the number of column headers accounting for newlines...
        while x < (len(fields)-1):
            for value in str(output[line]).split():
                ret[fields[x]]=value
                if verbose:
                    self.debug(str('DF FIELD: '+fields[x])+' = '+str(value))
                x += 1
            line += 1
        return ret
    
    def upgrade(self, package=None, nogpg=False):
        self.package_manager.upgrade(package, nogpg=nogpg)
    
    def add_repo(self, url, name="test-repo"):
        self.package_manager.add_repo(url,name)
    
    def install(self, package, nogpg=False, timeout=300):
        self.package_manager.install(package,nogpg=nogpg)

    def update_repos(self):
        self.package_manager.update_repos()
    
    def get_package_info(self):
        self.package_manager.get_package_info()
    
    def get_installed_packages(self):
        self.package_manager.get_installed_packages()
            
    def get_available(self, path, unit=1):
        """
        Return df output's available field. By default this is KB.
        path - optional -string.
        unit - optional -integer used to divide return value. Can be used to convert KB to MB, GB, TB, etc..
        """
        size = int(self.get_df_info(path=path)['available'])
        return size/unit
    
    def poll_log(self, log_file="/var/log/messages"):
        self.debug( "Starting to poll " + log_file )     
        self.log_channel = self.ssh.connection.invoke_shell()
        self.log_channel.send("tail -f " + log_file + " \n")
        ### Begin polling channel for any new data
        while self.log_active[log_file]:
            ### CLOUD LOG
            rl, wl, xl = select.select([self.log_channel],[],[],0.0)
            if len(rl) > 0:
                self.log_buffers[log_file] += self.log_channel.recv(1024)
            time.sleep(1)
    
    def start_log(self, log_file="/var/log/messages"):
        """Start thread to poll logs"""
        thread = threading.Thread(target=self.poll_log, args=log_file)
        thread.daemon = True
        self.log_threads[log_file]= thread.start()
        self.log_active[log_file] = True
        
    def stop_log(self, log_file="/var/log/messages"):
        """Terminate thread that is polling logs"""
        self.log_active[log_file] = False
        
    def save_log(self, log_file, path="logs"):
        """Save log buffer for log_file to the path to a file"""
        if not os.path.exists(path):
            os.mkdir(path)
        FILE = open( path + '/' + log_file,"w")
        FILE.writelines(self.log_buffers[log_file])
        FILE.close()
        
    def save_all_logs(self, path="logs"):
        """Save log buffers to a file"""
        for log_file in self.log_buffers.keys():
            self.save_log(log_file,path)

    def get_eucalyptus_conf(self,eof=False,verbose=False):
        out = None
        config = None
        use_path = None
        paths = [ "/" , "/opt/eucalyptus" ]
        for path in paths:
            try:
                self.sys('ls '+ str(path) + '/etc/eucalyptus/eucalyptus.conf', code=0, verbose=verbose)
                use_path = path + '/etc/eucalyptus/eucalyptus.conf'
                break
            except:
                pass
        if not use_path:
            out = 'eucalyptus.conf not found on this system'
            if eof:
                raise Exception(out)
            else:
                self.debug(out)
        else:
            try:
                config = EuConfig(filename=use_path, ssh=self.ssh, default_section_name='eucalyptus_conf')
            except Exception, e:
                out = 'Error while trying to create euconfig from eucalyptus_conf:' + str(e)
                if eof:
                    raise Exception(out)
                else:
                    self.debug(out)
        return config


    def __str__(self):
        s  = "+++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
        s += "+" + "Hostname:" + str(self.hostname) + "\n"
        dname = self.distro.name if self.distro else ""
        s += "+" + "Distro: " + str(dname) +"\n"
        s += "+" + "Distro Version: " +  str(self.distro_ver) +"\n"
        s += "+" + "Install Type: " +  str(self.source) +"\n"
        s += "+" + "Components: " +   str(self.components) +"\n"
        s += "+++++++++++++++++++++++++++++++++++++++++++++++++++++"
        return s
