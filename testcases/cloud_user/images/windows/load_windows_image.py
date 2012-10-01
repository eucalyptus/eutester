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
testcase.parser.add_argument('--file',help='File path to create windows EMI from', default=None)
testcase.parser.add_argument('--workip',help='The IP of the machine that the operation will be performed on', default=None)
testcase.parser.add_argument('--destpath',help='The path on the workip, that this operation will be performed on', default='/disk1/storage')
testcase.parser.add_argument('--urlpass',help='Password needed to retrieve remote url', default=None)
testcase.parser.add_argument('--urluser',help='Username needed to retrieve remote url', default=None)
testcase.parser.add_argument('--gigtime',help='Time allowed per gig size of image to be used', default=300)
testcase.parser.add_argument('--interbundletime',help='Inter-bundle timeout', default=120)
testcase.parser.add_argument('--bucket',help='bucketname', default=None)
args = testcase.parser.parse_args()

if (not args.url and not args.file) or (args.url and args.file):
    raise Exception('Must specify either a URL or FILE path to create Windows EMI from')
if args.workip:
    machine = Machine(hostname=args.workip,password=args.password)

WinTests = WindowsTests(config_file = args.config, 
                        cred_path = args.credpath, 
                        password = args.password, 
                        image_path = args.file,
                        url = args.url,
                        destpath= args.destpath,
                        work_component= machine,
                        time_per_gig = args.gigtime,
                        inter_bundle_timeout= args.interbundletime,
                        bucketname = args.bucket)

test = EutesterTestUnit(WinTests.create_windows_emi_from_url, 
                                                args={ 'url':args.url,
                                                      'wget_user':args.urluser,
                                                      'wget_password':args.urlpass})
print 'got args:'
print test.args

testcase.run_test_case_list([test], eof=True, clean_on_exit=False, printresults=True)


