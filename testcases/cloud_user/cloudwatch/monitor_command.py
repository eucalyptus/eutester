#!/usr/bin/python
import subprocess
from eucaops import Eucaops
from eucaops import EC2ops
from eutester.eutestcase import EutesterTestCase
from eutester.sshconnection import CommandExitCodeException

class CloudWatchCustom(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument('-c', '--command', help='Command to monitor')
        self.parser.add_argument('-n', '--namespace', help='Namespace to put data under')
        self.parser.add_argument('-m', '--metric-name', help='Metric name to put data under')
        self.parser.add_argument('-u', '--unit', default=None, help="Unit that the value be returned with")
        self.parser.add_argument('-i', '--interval', default=10, type=int, help='Time between exectutions of the monitoring task')
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        if self.args.region:
            self.tester = EC2ops( credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops( credpath=self.args.credpath, config_file=self.args.config,password=self.args.password)

    def clean_method(self):
        pass

    def MonitorLocal(self):
        while True:
            try:
                output = self.tester.local(self.args.command)
                self.tester.debug(output)
                value = int(output)
                self.tester.put_metric_data(self.args.namespace, self.args.metric_name, value=value, unit=self.args.unit)
            except subprocess.CalledProcessError:
                self.tester.critical("Command exited Non-zero not putting data")
            except ValueError:
                self.tester.critical("Command returned non-integer")
            self.tester.sleep(self.args.interval)

    def MonitorRemotes(self):
        while True:
            for machine in self.tester.get_component_machines():
                try:
                    output = "".join(machine.sys(self.args.command, code=0))
                    self.tester.debug(output)
                    value = int(output)
                    ### Push to Hostname dimension
                    self.tester.put_metric_data(self.args.namespace, self.args.metric_name, unit=self.args.unit,
                                                dimensions={"Hostname": machine.hostname}, value=value)
                    ### Push to aggregate metric as well
                    self.tester.put_metric_data(self.args.namespace, self.args.metric_name, unit=self.args.unit, value=value)
                except CommandExitCodeException:
                    self.tester.critical("Command exited Non-zero not putting data")
                except ValueError:
                    self.tester.critical("Command returned non-integer")
                except Exception, e:
                    self.tester.critical("Unknown failure: " + str(e))
            self.tester.sleep(self.args.interval)



if __name__ == "__main__":
    testcase = CloudWatchCustom()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or [ "MonitorLocal"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)