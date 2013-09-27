#!/usr/bin/python
from eutester.eutestcase import EutesterTestCase, EutesterTestUnit, EutesterTestResult
from testcases.cloud_user.images.windows.windowstests import WindowsTests
from eutester.euconfig import EuConfig
from eutester.machine import Machine


machine=None
testcase = EutesterTestCase()

testcase.setup_parser(testname='load_windows_image.py', 
                      description='Loads a windows image from either a remote url or local file path', 
                      emi=False,
                      testlist=False)

testcase.parser.add_argument('--url',help='URL containing remote windows image to create EMI from', default=None)
testcase.parser.add_argument('--file',dest='image_file_path', help='File path to create windows EMI from', default=None)
testcase.parser.add_argument('--workip',help='The IP of the machine that the operation will be performed on', default=None)
testcase.parser.add_argument('--destpath',help='The path on the workip, that this operation will be performed on', default='/disk1/storage')
testcase.parser.add_argument('--urlpass', dest='wget_password',help='Password needed to retrieve remote url', default=None)
testcase.parser.add_argument('--urluser',dest='wget_user', help='Username needed to retrieve remote url', default=None)
testcase.parser.add_argument('--gigtime',dest='time_per_gig', help='Time allowed per gig size of image to be used', default=300)
testcase.parser.add_argument('--interbundletime',dest='inter_bundle_timeout', help='Inter-bundle timeout', default=120)
testcase.parser.add_argument('--virtualization_type', help='bucketname', default=None)
testcase.parser.add_argument('--bucket',dest='bucketname', help='bucketname', default=None)

args = testcase.get_args()

if (not args.url and not args.image_file_path) or (args.url and args.image_file_path):
    raise Exception('Must specify either a URL or FILE path to create Windows EMI from')
if args.workip:
    machine = Machine(hostname=args.workip,password=args.password)

WinTests = testcase.do_with_args(WindowsTests,work_component=machine)

if args.image_file_path:
    test = testcase.create_testunit_from_method(WinTests.create_windows_emi_from_file)
else:
    test = testcase.create_testunit_from_method(WinTests.create_windows_emi_from_url)

testcase.run_test_case_list([test], eof=True, clean_on_exit=False, printresults=True)


