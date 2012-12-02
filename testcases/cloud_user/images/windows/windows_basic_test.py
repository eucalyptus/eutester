#!/usr/bin/python
from eutester.eutestcase import EutesterTestCase, EutesterTestUnit, EutesterTestResult
from testcases.cloud_user.images.windows.windowstests import WindowsTests
from eutester.euconfig import EuConfig
from eutester.machine import Machine


machine=None
testcase = EutesterTestCase()

testcase.setup_parser(testname='windows_basic_test.py', vmtype=False,
                      description='Run basic functionality test suite against a windows guest')

testcase.parser.add_argument('--vmtype', help='vmtype to use when running windows instance', default='m1.xlarge')
testcase.parser.add_argument('--win_proxy_hostname', help='powershell proxy hostname or ip', default=None)
testcase.parser.add_argument('--win_proxy_username', help='powershell proxy ssh username', default='Administrator')
testcase.parser.add_argument('--win_proxy_password', help='powershell proxy ssh password', default=None) 
testcase.parser.add_argument('--win_proxy_keypath',  help='powershell proxy ssh keypath', default=None)
testcase.parser.add_argument('--fof',  help='freeze on failure, will not clean up test if set', default=False)
testcase.parser.add_argument('--instance_id', dest='instance', help='Instance id. Must be a running instance and keyfile is local to this script', default=None)
testcase.parser.add_argument('--recycle',  help="re-use an instance who's keyfile is local to this test script",dest='recycle', action='store_true', default=None)

args = testcase.get_args()

recycle = testcase.args.recycle if testcase.args.fof is not None else False

if not args.emi: 
    raise Exception("Need a windows EMI to test against")
if not (args.win_proxy_hostname and args.win_proxy_username and (args.win_proxy_password or args.win_proxy_keypath)):
    raise Exception("Need windows proxy hostname, and login credentials")

WinTests = testcase.do_with_args(WindowsTests,work_component=machine)


#WinTests = WindowsTests()
emi = WinTests.tester.get_emi(args.emi)
tests = []

if recycle or args.instance:
   tests.append(testcase.create_testunit_from_method(WinTests.get_windows_instance, eof=True)) 
else:
    tests.append(testcase.create_testunit_from_method(WinTests.test_run_windows_emi, eof=True))
tests.append(testcase.create_testunit_from_method(WinTests.test_get_windows_instance_password, eof=True))
tests.append(testcase.create_testunit_from_method(WinTests.update_proxy_info, eof=True))
tests.append(testcase.create_testunit_from_method(WinTests.test_wait_for_instance_boot))
tests.append(testcase.create_testunit_from_method(WinTests.test_poll_for_rdp_port_status, eof=True))
tests.append(testcase.create_testunit_from_method(WinTests.proxy.ps_login_test, eof=True))
tests.append(testcase.create_testunit_from_method(WinTests.proxy.ps_ephemeral_test))
tests.append(testcase.create_testunit_from_method(WinTests.proxy.ps_hostname_test))
tests.append(testcase.create_testunit_from_method(WinTests.proxy.ps_virtio_test))

testcase.run_test_case_list(tests, clean_on_exit=args.fof, printresults=True)
