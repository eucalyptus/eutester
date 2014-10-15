#!/usr/bin/python
import inspect
import json
import os
import re
import sys
import time
from BeautifulSoup import BeautifulSoup
from eucaops import Eucaops, S3ops, Machine
from eutester.sshconnection import CommandExitCodeException
from eutester.eutestcase import EutesterTestCase



# Install and configure Riak CS for Eucalyptus
# /install_riak_cs.py --config /path/to/config --password foobar --template-path "/path/to/templates/"

class InstallRiak(EutesterTestCase):
    def __init__(self, **kwargs):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--admin-name", dest='admin_name', default=None)
        self.parser.add_argument("--admin-email", dest='admin_email', default=None)
        self.parser.add_argument("--template-path", dest='template_path', default=None,
                                 help='path to riak templates, default is '
                                      '<eutester_dir>/testcases/cloud_admin/riak_cs/templates/')
        self.parser.add_argument("--riak-cs-port", default="9090")
        self.parser.add_argument("--bare-machines", dest='bare_machines', default=None,
                                 help='Comma delimited list of hosts to install riak on')
        self.parser.add_argument("--machine-password", dest='machine_password', default=None,
                                 help='password used to log into remote machines when '
                                      'installing riak')
        self.parser.add_argument("--walrus-fallback", dest='walrus_fallback', default=True,
                                 help='Allow test to configure system for Walrus in the case'
                                      'Riak fails to install or a riak component(s) is not listed')
        self.parser.add_argument("--basho-url", dest='basho_url',
                                 default='http://yum.basho.com/gpg/basho-release-6-1.noarch.rpm',
                                 help="default basho repo")
        self.get_args()
        # Allow __init__ to get args from __init__'s kwargs or through command line parser...
        for kw in kwargs:
            print 'Setting kwarg:'+str(kw)+" to "+str(kwargs[kw])
            self.set_arg(kw ,kwargs[kw])
        self.show_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config,password=self.args.password)
        self.machines = []
        if self.args.bare_machines:
            b_machines = self.args.bare_machines
            if not isinstance(b_machines, list) and isinstance(b_machines, str):
                b_machines = b_machines.split(',')
            else:
                raise ValueError('Unknown type for machine arg:"{0}", type:"{1}"'
                                 .format(b_machines, type(b_machines)))
            for mach in b_machines:
                if not isinstance(mach, Machine):
                    if not self.args.machine_password:
                        raise ValueError('Must provide machine password for machine list')
                    mach = Machine(str(mach).strip(), password=self.args.machine_password)
                self.machines.append(mach)
        else:
            try:
                self.machines = self.tester.get_component_machines("riak")
            except IndexError as ex:
                self.tester.info("No Riak component found in component specification. ")

                if self.args.walrus_fallback:
                    self.tester.info('walrus_fallback set to True, attempting to configure for'
                                     'walrus...')
                    self.configure_eucalyptus_for_walrus()
                else:
                    raise
        self.template_dir = self.args.template_path or os.path.join(self._get_script_filepath(),
                                                                    'templates/')
        self.primary_machine = None
        self.user_dict = None
        self.args.admin_name = self.args.admin_name or 'testuser_' + str(int(time.time()))
        self.args.admin_email = self.args.admin_email or self.args.admin_name +'@testemail'

    def clean_method(self):
        pass

    def InstallRiakCS(self):
        if not self.machines:
            try:
                self.machines = self.tester.get_component_machines("riak")
            except IndexError as ex:
                self.tester.info("No Riak component found in component specification. ")
                if self.args.walrus_fallback:
                    self.tester.info('walrus_fallback set to True, attempting to configure for'
                                     'walrus...')
                    return self.configure_eucalyptus_for_walrus()
                else:
                    raise
        try:
            self.status('Install riak, riak-cs and stanchion on machines...')
            self.InstallRiakMachines()
            self.status('Creating initial user...')
            self.SetupInitalUser()
            self.status('Running bucket test to validate install...')
            self.create_testuser_id_bucket()
            self.status('Configuring Eucalyptus for Riak...')
            self.configure_eucalyptus_for_riak()
        except:
            self.debug('Error during Riak installation...')
            raise

    def InstallRiakMachines(self, machines=None):
        """
        This is where the test description goes
        """
        machines = machines or self.machines
        sync_host = None

        for machine in machines:
            if not isinstance(machine, Machine):
                raise ValueError('InstallRiakCS pass non Machine() type: "{0}", type:"{1}"'
                                 .format(machine, type(machine)))
            # Check if basho repo is installed to avoid yum exit code failure...
            try:
                machine.sys('rpm -qa -qf {0} | xargs yum list installed'
                            .format(self.args.basho_url), code=0)
            except CommandExitCodeException:
                machine.sys("yum install -y {0}".format(self.args.basho_url), code=0, timeout=600)
            machine.sys("yum install -y riak", code=0, timeout=600)
            machine.sys("yum install -y stanchion", code=0, timeout=600)
            machine.sys("yum install -y riak-cs", code=0, timeout=600)
            self.riak_cs_version = machine.sys("riak-cs version", code=0)
            machine_ulimit = machine.sys('ulimit -n', code=0)
            if ( machine_ulimit.pop() != '65536'):
                machine.sys('echo "ulimit -n 65536" >> /root/.bashrc', code=0)
            for component in ['riak', 'stanchion', 'riak-cs']:
                for config_file in ["app.config", "vm.args"]:
                    local_file = self.template_dir + config_file + "." + component + ".template"
                    remote_file = "/etc/" + component + "/" + config_file
                    machine.sftp.put(local_file, remote_file)
                    machine.sys("sed -i s/IPADDRESS/" + machine.hostname + "/g " + remote_file,
                                code=0)
                    machine.sys("sed -i s/RIAKCSPORT/" + self.args.riak_cs_port + "/g " +
                                remote_file, code=0)
                    machine.sys("sed -i s/RIAKCSVERSION/" + str(self.riak_cs_version[0]) + "/g " +
                                remote_file, code=0)
            self.riak_stop(machine)
            self.stanchion_stop(machine)
            self.riak_cs_stop(machine)
            self.riak_start(machine)
            self.stanchion_start(machine)
            self.riak_cs_start(machine)
            if not sync_host:
                sync_host = self.GetNodeName(machine)
                self.primary_machine = machine
                self.debug('Waiting for host to sync...')
                time.sleep(20)
            else:
                try:
                    machine.sys('riak-admin member-status | grep ' + sync_host, code=0)
                except CommandExitCodeException:
                    machine.sys('riak-admin cluster join {0}'.format(sync_host), code=0)
                    machine.sys('riak-admin cluster plan && riak-admin cluster commit')


    def riak_is_running(self, machine):
        try:
            machine.sys('riak ping', code=0)
            return True
        except CommandExitCodeException:
            return False

    def stanchion_is_running(self, machine):
        try:
            machine.sys('stanchion ping', code=0)
            return True
        except CommandExitCodeException:
            return False

    def riak_cs_is_running(self, machine):
        try:
            machine.sys('riak-cs ping', code=0)
            return True
        except CommandExitCodeException:
            return False

    def riak_start(self, machine, timeout=30):
        if not self.riak_is_running(machine):
            machine.sys('riak start')
        self.tester.wait_for_result(callback=self.riak_is_running, result=True, timeout=timeout,
                                    machine=machine)

    def riak_stop(self, machine):
        if self.riak_is_running(machine):
            machine.sys('riak stop')

    def riak_cs_start(self, machine, timeout=30):
        if not self.riak_cs_is_running(machine):
            machine.sys('riak-cs start')
        self.tester.wait_for_result(callback=self.riak_cs_is_running, result=True, timeout=timeout,
                                    machine=machine)

    def riak_cs_stop(self, machine):
        if self.riak_cs_is_running(machine):
            machine.sys('riak-cs stop')

    def stanchion_start(self, machine, timeout=30):
        if not self.stanchion_is_running(machine):
            machine.sys('stanchion start')
        self.tester.wait_for_result(callback=self.stanchion_is_running, result=True,
                                    timeout=timeout, machine=machine)

    def stanchion_stop(self, machine):
        if self.stanchion_is_running(machine):
            machine.sys('stanchion stop')

    def GetNodeName(self, machine):
        out = machine.sys('riak-admin status | grep nodename', code=0)
        nodename = out[0].split(':').pop().strip().strip("'")
        return nodename

    def get_member_status(self, machine):
        out = machine.sys('riak-admin member-status', code=0)


    def SetupInitalUser(self, machine=None, email=None, name=None, show=True):
        machine = machine or self.primary_machine
        email = email or self.args.admin_email
        name= name or self.args.admin_name
        response_json = machine.sys('curl -H \'Content-Type: application/json\' -X POST http://' +
                                    machine.hostname + ':' + self.args.riak_cs_port +
                                    '/riak-cs/user --data \'{"email":"' + email +'", '
                                    '"name":"' + name +'"}\'', code=0)[0]

        user_dict = json.loads(response_json)
        self.user_dict = user_dict
        if show:
            buf = "#Test User Info:\n"
            for key in user_dict:
                buf += '{0}="{1}"'.format(key, user_dict[key])
            self.debug(buf)
        return self.user_dict

    def _get_script_filepath(self):
        fp = None
        try:
            fp = os.path.dirname(inspect.getfile(inspect.currentframe()))
        except Exception, e:
            print 'Could not get file path due to error:'  + str(e)
        return fp

    def create_testuser_id_bucket(self, machine=None, user_dict=None):
        machine = machine or self.primary_machine
        user_dict = user_dict or self.user_dict
        cs_tester = S3ops(endpoint=machine.hostname, aws_access_key_id=user_dict["key_id"],
                          aws_secret_access_key=user_dict["key_secret"], port=int(self.args.riak_cs_port))
        test_time = str(int(time.time()))
        bucket_name = "riak-test-bucket-" + test_time
        key_name = "riak-test-key-" + test_time
        bucket = cs_tester.create_bucket(bucket_name)
        cs_tester.upload_object(bucket_name, key_name, contents=user_dict["id"])
        key = cs_tester.get_objects_by_prefix(bucket_name, key_name).pop()
        key_contents = key.read()
        cs_tester.debug("Uploaded Key contents: " + key_contents + "  Original:" + user_dict["id"])
        assert key_contents == user_dict["id"]


    def configure_eucalyptus_for_riak(self, tester=None, machine=None, user_dict=None):
        tester = tester or self.tester
        user_dict = user_dict or self.user_dict
        machine = machine or self.primary_machine
        if not user_dict:
            raise ValueError('Empty user dict provided')
        assert isinstance(machine, Machine), 'None Machine() type provided, type:"{0}"'\
            .format(type(machine))
        assert isinstance(tester, Eucaops), 'Non eucaops tester obj provided, type:"{0}"'\
            .format(type, tester)
        self.tester.info("Configuring OSG to use RiakCS backend")
        self.tester.modify_property("objectstorage.providerclient","riakcs")

        endpoint = machine.hostname + ":" + self.args.riak_cs_port
        self.tester.info("Configuring OSG to use s3 endpoint: " + endpoint)
        self.tester.modify_property("objectstorage.s3provider.s3endpoint", endpoint)

        self.tester.info("Configuring OSG to use s3 access key: " + user_dict["key_id"])
        self.tester.modify_property("objectstorage.s3provider.s3accesskey", user_dict["key_id"])

        self.tester.info("Configuring OSG to use s3 secret key: " + user_dict["key_secret"][-4:])
        self.tester.modify_property("objectstorage.s3provider.s3secretkey",user_dict["key_secret"])


    def configure_eucalyptus_for_walrus(self, tester=None):
        tester = tester or self.tester
        try:
            self.tester.get_component_machines("ws")
            self.tester.info("No RIAK component found. Configuring OSG to use walrus backend");
            self.tester.modify_property("objectstorage.providerclient", "walrus");
        except IndexError as ex:
            self.tester.info("No Walrus component found in component specification. "
                             "Skipping installation")
            raise

            
if __name__ == "__main__":
    testcase = InstallRiak()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["InstallRiakCS"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list)
    sys.exit(result)

