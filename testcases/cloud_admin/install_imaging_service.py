#!/usr/bin/python

from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
from eutester.machine import Machine
from eutester.sshconnection import CommandExitCodeException
import os
import re
import requests
from argparse import ArgumentError
from BeautifulSoup import BeautifulSoup
from logging.handlers import SysLogHandler
from requests import HTTPError
import time
import datetime
import logging
import socket


class ConfigureImagingService(EutesterTestCase):
    def __init__(self):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--img-repo", dest='img_repo', default=None,
                                 help='Repo to install imaging service worker'
                                      'from')
        self.parser.add_argument("--base-url", dest='base_url',
                                 default='http://packages.release.'
                                         'eucalyptus-systems.com/yum/builds/'
                                         'imaging-worker-image/commit/',
                                 help='baseurl used to find most recent commit'
                                      'from')
        self.parser.add_argument("--distro", default=None,
                                 help='Distro name in base_url lookup if used')
        self.parser.add_argument("--worker-keyname", dest='worker_keyname',
                                 default='qa_worker_key',
                                 help='Name used for keypair property. Test '
                                      'will attempt to create the key if it is '
                                      'not found on the system')
        self.parser.add_argument('--ntp-server', dest='ntp_server',
                                 default='0.centos.pool.ntp.org',
                                 help='Worker ntp property string')
        self.parser.add_argument('--zones', default=None,
                                 help='Availability zones imaging service '
                                      'property')
        self.parser.add_argument('--log-server-port', dest='log_server_port',
                                 default=514,
                                 help='log server port for imaging property')
        self.parser.add_argument('--log-server', dest='log_server',
                                 default=None,
                                 help='log server host for imaging property')
        self.parser.add_argument('--task-expiration-hours',
                                 dest='task_expiration_hours',
                                 default=None,
                                 help='task expiration hours for'
                                      ' imaging property')
        self.parser.add_argument('--worker-vmtype', dest='worker_vmtype',
                                 default=None,
                                 help='worker instance type used for'
                                      ' imaging property')

        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops(config_file=self.args.config,
                              password=self.args.password)
        clcs = self.tester.get_component_machines("clc")
        if len(clcs) == 0:
            raise Exception("Unable to find a CLC")
        first_clc = clcs[0]
        assert isinstance(first_clc, Machine)
        self.clc = first_clc
        if self.args.distro is None:
            self.args.distro = self.tester.clc.distro.name
        self.set_repo()




    def clean_method(self):
        pass

    def set_repo(self):
        if self.args.img_repo:
            return
        if not self.args.base_url:
            raise ArgumentError(self.args.img_repo,
                                'Image repo or base_url is required')
        self.args.img_repo = self.get_latest_commit_from_base_url()

    def get_latest_commit_from_base_url(self):
        '''
        Traverse the provided URL, find the latest commit, match the correct
        distro, and release, etc..
        '''
        if not re.search('commit.{0,1}$', self.args.base_url):
            raise ArgumentError('Expected baseurl to end with commit dir')

        #Find latest commit...
        base_url = self.args.base_url
        latest={'timestamp':0, 'count':0, 'commit':None}
        for commit in self._get_dirs_from_body(base_url):
            y, m, d, c = commit.strip('/').split('-')[1:]
            self.debug('commit:{0}, y{1}, m,{2}, d{3}, c{4}'
                       .format(str(commit), y, m, d, c))
            date = "{0}/{1}/{2}".format(d, m, y)
            c = int(c)
            timestamp = time.mktime(
                datetime.datetime.strptime(date, "%d/%m/%Y").timetuple())
            if timestamp >= latest['timestamp']:
                if timestamp == latest['timestamp'] and c <= latest['count']:
                    continue
                latest = {'timestamp':timestamp,
                          'count':c,
                          'commit':commit}
        base_url = base_url + latest['commit']
        #Get the distro
        if (self.args.distro + "/") not in self._get_dirs_from_body(base_url):
            raise ValueError('Distro "' + str(self.args.distro) +
                             '" not found at path:' + str(base_url))
        base_url += self.args.distro + "/"
        #Get the release num
        new_base_url = None
        base_release = self.clc.distro_ver.split('.')[0]
        rel_dirs =  self._get_dirs_from_body(base_url)
        for dir in rel_dirs:
            if re.search('^'+base_release, dir):
                new_base_url = base_url + dir
                break
        if not new_base_url:
            raise RuntimeError(
                'Could find matching release for:' + str(base_release))
        for dir in self._get_dirs_from_body(new_base_url):
            if re.search('x86_64.{0,1}$', dir):
                self.args.base_url = new_base_url + dir
                return self.args.base_url
        raise RuntimeError('Could not find baseurl for image repo from:' +
                            str(self.args.baseurl))

    def _get_dirs_from_body(self, url, retry=3):
        dirs = []
        r = None
        attempt = 0
        while not r and attempt <= retry:
            attempt += 1
            r = requests.get(url)
            try:
                r.raise_for_status()
            except HTTPError as HE:
                self.tester.logger.log.warn('URL:' + str(url) +
                                            ', Attempt:' +
                                            str(attempt) +
                                            "/" + str(retry) +
                                            "HTTP ERROR:" + str(HE))
                if attempt >= retry:
                    raise HE
                time.sleep(1)
        soup = BeautifulSoup(r.text)
        table =soup.find('table')
        rows = table.findAll('tr')
        for row in rows:
            a = row.find('a')
            if a and re.search('/$', a.getText()):
                dirs.append(a.getText())
        self.debug('Paths found at:"' + str(url) + '", paths:' + str(dirs))
        return dirs

    def configure_rsyslog_(self, machine, conf='/etc/rsyslog.conf'):
        '''
        $ModLoad imudp
        $UDPServerRun 514
        $UDPServerAddress 0.0.0.0
        '''
        #Make sure file is at least there
        conf = conf.strip()
        self.debug('checking rsyslog conf file:' + str(conf))
        machine.get_file_stat(conf)
        self._rsyslog_write_value(machine,'$ModLoad imudp',
                                 '\$ModLoad imudp', conf)
        self._rsyslog_write_value(machine, '$UDPServerRun',
                                 '\$UDPServerRun ' +
                                 str(self.args.log_server_port),
                                 conf)
        self._rsyslog_write_value(machine, '$UDPServerAddress',
                                 '\$UDPServerAddress 0.0.0.0', conf)
        machine.sys('service rsyslog restart', code=0)
        machine.sys('iptables -I INPUT -p udp --dport ' +
                    str(self.args.log_server_port) + ' -j ACCEPT', code=0)
        time.sleep(5)
        #Log a message to the server.
        log = logging.getLogger('imaging_setup')
        hdlr = SysLogHandler(address=(machine.hostname, 514),
                             socktype=socket.SOCK_DGRAM)
        log.addHandler(hdlr)
        log.setLevel(logging.DEBUG)
        log.info('EUTESTER Configuring IMAGE SERVICE')


    def _rsyslog_write_value(self, machine, searchkey, new_value, conf):
        try:
            output = machine.sys('cat ' + str(conf) +
                                 " | grep '" + searchkey + "'", code=0)
            for orig_key in output:
                self.debug('Using origkey:' + str(orig_key))
                if not re.search("^#.*." + searchkey, orig_key):
                    machine.sys('perl -p -i -e "s/^*.*' +str(orig_key) + '/\#' +
                            str(orig_key).strip() +
                                '#Commented out by eutester/g" ' + conf,
                            timeout=10, code=0)
        except CommandExitCodeException:
           pass
        machine.sys('echo "' + str(new_value) + '" >> ' + conf, code=0 )


    def configure_service(self):
        """
        This test will attempt to add the repo the remote clc and
        execute the install eucalyptus imaging worker, and configure the
        eucalyptus imaging service.
        """
        self.clc.add_repo(url=self.args.img_repo, name="EucaImagingService")
        self.clc.install("eucalyptus-service-image", nogpg=True,
                         timeout=300)
        self.clc.sys("export EUCALYPTUS=" + str(self.tester.eucapath) +
                     " && source " + self.tester.credpath  +
                     "/eucarc && euca-install-imaging-worker --install-default",
                     code=0)
        #self.tester.property_manager.show_all_imaging_properties()


    def configure_properties(self):
        #Add the keypair for the imaging service/worker (used for debug)
        try:
            self.keypair = self.tester.get_keypair(self.args.worker_keyname)
        except:
            self.keypair = self.tester.add_keypair(self.args.worker_keyname)
            self.tester.clc.sftp.put(self.args.worker_keyname + '.pem',
                                     self.args.worker_keyname + '.pem')
        key_property = self.tester.property_manager.get_euproperty_by_name(
            'imaging_worker_keyname')
        key_property.set(self.keypair.name)
        #Set the imaging service log server host
        if self.args.log_server:
            log_server = self.args.log_server
            self.logger.log.warn('Not configuring rsyslog on server, assume '
                                 'it is already configured')
        else:
            log_server = self.clc.hostname
            self.debug('Attempting to setup rsyslog on clc...')
            self.configure_rsyslog_(self.clc)
        log_server = self.args.log_server or self.clc.hostname
        log_property = self.tester.property_manager.get_euproperty_by_name(
            'imaging_worker_log_server')
        log_property.set(log_server)
        if self.args.log_server_port:
            log_port_property = \
                self.tester.property_manager.get_euproperty_by_name(
                    'imaging_worker_log_server_port')
            log_port_property.set(self.args.log_server_port)
        #Set the imaging service ntp server
        if self.args.ntp_server:
            ntp_property = self.tester.property_manager.get_euproperty_by_name(
                'imaging_worker_ntp_server')
            ntp_property.set(self.args.ntp_server)
        #Set import task expiration if provided
        if self.args.task_expiration_hours:
            task_property = \
                self.tester.property_manager.get_euproperty_by_name(
                    'import_task_expiration_hours')
            task_property.set(self.args.task_expiration_hours)
        #Set worker instance vm type if provided
        if self.args.worker_vmtype:
            task_property = \
                self.tester.property_manager.get_euproperty_by_name(
                    'imaging_worker_instance_type ')
            task_property.set(self.args.worker_vmtype)
        self.tester.property_manager.show_all_imaging_properties()



if __name__ == "__main__":
    testcase = ConfigureImagingService()
    ### Use the list of tests passed from config/command line to determine
    # what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["configure_service"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
