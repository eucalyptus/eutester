#!/usr/bin/python

from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
from eutester.machine import Machine
import re
import lxml.objectify
import requests
from argparse import ArgumentError
from requests import HTTPError
import time
import datetime

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
                                         'imaging-worker/commit/',
                                 help='baseurl used to find most recent commit'
                                      'from')
        self.parser.add_argument("--distro", default='centos',
                                 help='Distro name in base_url lookup if used')
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config,password=self.args.password)
        clcs = self.tester.get_component_machines("clc")
        if len(clcs) == 0:
            raise Exception("Unable to find a CLC")
        first_clc = clcs[0]
        assert isinstance(first_clc,Machine)
        self.clc = first_clc
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
        xml = lxml.objectify.fromstring(r.text, lxml.etree.HTMLParser())
        body = xml.find('body')
        for elem in body.xpath('//tr/td/a'):
            if re.search('/$',elem.text):
                dirs.append(elem.text)
        self.debug('Paths found at:"' + str(url) + '", paths:' + str(dirs))
        return dirs

    def ConfigureService(self):
        """
        This test will attempt to add the repo the remote clc and
        execute the install eucalyptus imaging worker, and configure the
        eucalyptus imaging service.
        """
        self.clc.add_repo(url=self.args.img_repo, name="EucaImagingService")
        self.clc.install("eucalyptus-imaging-worker")
        self.clc.sys("source " + self.tester.credpath  + "/eucarc && euca-install-image-worker --install-default" , code=0)

if __name__ == "__main__":
    testcase = ConfigureImagingService()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["ConfigureService"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
