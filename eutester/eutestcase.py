
import unittest
import inspect
import time
import gc
import argparse
import re
import sys
import os
import types
import traceback
import random
import string
from eutester.eulogger import Eulogger
from eutester.euconfig import EuConfig
import StringIO
import copy
from eutester.timer import Timer
import uuid

'''
This is the base class for any test case to be included in the Eutester repo. It should include any
functionality that we expected to be repeated in most of the test cases that will be written.

Currently included:
 - Debug method
 - Allow parameterized test cases
 - Method to run test case
 - Run a list of test cases
 - Start, end and current status messages
 - Enum class for possible test results
 
Necessary to work on:
 - Argument parsing
 - Metric tracking (need to define what metrics we want
 - Standardized result summary
 - Logging standardization
 - Use docstring as description for test case
 - Standardized setUp and tearDown that provides useful/necessary cloud resources (ie group, keypair, image)
'''


class EutesterTestResult():
    '''
    standardized test results
    '''
    not_run="not_run"
    passed="passed"
    failed="failed"
    
class TestColor():
    reset = '\033[0m'
    #formats
    formats={'reset':'0',
             'bold':'1',
             'dim':'2',
             'uline':'4',
             'blink':'5',
             'reverse':'7',
             'hidden':'8',
             }
    
    foregrounds = {'black':30,
                   'red':31,
                   'green':32,
                   'yellow':33,
                   'blue':34,
                   'magenta':35,
                   'cyan':36,
                   'white':37,
                   'setasdefault':39}
    
    backgrounds = {'black':40,
                   'red':41,
                   'green':42,
                   'yellow':43,
                   'blue':44,
                   'magenta':45,
                   'cyan':46,
                   'white':47,
                   'setasdefault':49}
    
    #list of canned color schemes, for now add em as you need 'em?
    canned_colors ={'reset' : '\033[0m', #self.TestColor.get_color(fg=0)
                    'whiteonblue' : '\33[1;37;44m', #get_color(fmt=bold, fg=37,bg=44)
                    'whiteongreen' : '\33[1;37;42m',
                    'red' : '\33[31m', #TestColor.get_color(fg=31)
                    'failred' : '\033[101m', #TestColor.get_color(fg=101) 
                    'blueongrey' : '\33[1;34;47m', #TestColor.get_color(fmt=bold, fg=34, bg=47)#'\33[1;34;47m'
                    'redongrey' : '\33[1;31;47m', #TestColor.get_color(fmt=bold, fg=31, bg=47)#'\33[1;31;47m'
                    'blinkwhiteonred' : '\33[1;5;37;41m', #TestColor.get_color(fmt=[bold,blink],fg=37,bg=41)#
                    }
    
    @classmethod
    def get_color(cls,fmt=0,fg='', bg=''):
        '''
        Description: Method to return ascii color codes to format terminal output. 
        Examples:
                blinking_red_on_black = get_color('blink', 'red', 'blue')
                bold_white_fg = get_color('bold', 'white, '')
                green_fg = get_color('','green','')
                
                print bold_white_fg+"This text is bold white"+TestColor.reset
        :type fmt: color attribute
        :param fmt: An integer or string that represents an ascii color attribute. see TestColor.formats
        
        :type fg: ascii foreground attribute
        :param fg: An integer or string that represents an ascii foreground color attribute. see TestColor.foregrounds
        
        :type bg: ascii background attribute
        :param bg: An integer or string that represents an ascii background color attribute. see TestColor.backgrounds
        '''
        
        fmts=''
        if not isinstance(fmt, types.ListType):
            fmt = [fmt]
        for f in fmt:
            if isinstance(f,types.StringType):
                f = TestColor.get_format_from_string(f)
            if f:
                fmts += str(f)+';'
        if bg:
            if isinstance(bg,types.StringType):
                bg = TestColor.get_bg_from_string(bg)
            if bg:
                bg = str(bg)
        if fg:
            if isinstance(fg,types.StringType):
                fg = TestColor.get_fg_from_string(fg)
            if fg:
                fg = str(fg)+';'
        
        return '\033['+str(fmts)+str(fg)+str(bg)+'m'
    
    @classmethod
    def get_format_from_string(cls,format):
        if format in TestColor.formats:
            return TestColor.formats[format]
        else:
            return ''
        
    @classmethod
    def get_fg_from_string(cls,fg):
        if fg in TestColor.foregrounds:
            return TestColor.foregrounds[fg]
        else:
            return ''
    @classmethod
    def get_bg_from_string(cls,bg):
        if bg in TestColor.backgrounds:
            return TestColor.backgrounds[bg]
        else:
            return ''
        
    @classmethod
    def get_canned_color(cls,color):
        try:
            return TestColor.canned_colors[color]
        except:
            return ""    
    
    
    
    
class EutesterTestUnit():
    '''
    Description: Convenience class to run wrap individual methods, and run and store and access results.
    
    type method: method
    param method: The underlying method for this object to wrap, run and provide information on 
    
    type args: list of arguments
    param args: the arguments to be fed to the given 'method'
    
    type eof: boolean
    param eof: boolean to indicate whether a failure while running the given 'method' should end the test case exectution. 
    '''
    def __init__(self,method, *args, **kwargs):
        self.method = method
        self.method_possible_args = EutesterTestCase.get_meth_arg_names(self.method)
        self.args = args
        self.kwargs = kwargs 
        self.name = str(method.__name__)
        self.result=EutesterTestResult.not_run
        self.time_to_run=0
        if self.kwargs.get('html_anchors', False):
            self.anchor_id = str(str(time.ctime())
                                + self.name
                                + "_"
                                + str( ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for x in range(3)))
                                + "_"
                                ).replace(" ","_")
            self.error_anchor_id = "ERROR_" + self.anchor_id
        self.description=self.get_test_method_description()
        self.eof=False
        self.error = ""
        print "Creating testunit:" + str(self.name)+", args:"
        for count, thing in enumerate(args):
            print '{0}. {1}'.format(count, thing)
        for name, value in kwargs.items():
            print '{0} = {1}'.format(name, value)
    
    @classmethod
    def create_testcase_from_method(cls, method, eof=False, *args, **kwargs):
        '''
        Description: Creates a EutesterTestUnit object from a method and set of arguments to be fed to that method
        
        type method: method
        param method: The underlying method for this object to wrap, run and provide information on
        
        type args: list of arguments
        param args: the arguments to be fed to the given 'method'
        '''
        testunit =  EutesterTestUnit(method, args, kwargs)
        testunit.eof = eof
        return testunit
       
    def set_kwarg(self,kwarg,val):
        self.kwargs[kwarg]=val
         
    def get_test_method_description(self):
        '''
        Description:
        Attempts to derive test unit description for the registered test method.
        Keys off the string "Description:" preceded by any amount of white space and ending with either
        a blank line or the string "EndDescription". This is used in debug output when providing info to the
        user as to the method being run as a testunit's intention/description.  
        '''

        desc = "\nMETHOD:"+str(self.name) + ", TEST DESCRIPTION:\n"
        ret = []
        add = False
        try:
            doc = str(self.method.__doc__)
            if not doc or not re.search('Description:',doc):
                try:
                    desc = desc+"\n".join(self.method.im_func.func_doc.title().splitlines())
                except:pass
                return desc
            has_end_marker = re.search('EndDescription', doc)
            
            for line in doc.splitlines():
                line = line.lstrip().rstrip()
                if re.search('^Description:',line.lstrip()):
                    add = True
                if not has_end_marker:
                    if not re.search('\w',line):
                        if add:
                            break
                        add = False
                else:
                    if re.search('^EndDescription'):
                        add = False
                        break
                if add:
                    ret.append(line)
        except Exception, e:
            print('get_test_method_description: error'+str(e))
        if ret:
            desc = desc+"\n".join(ret)
        return desc
    
    def run(self, eof=None):
        '''
        Description: Wrapper which attempts to run self.method and handle failures, record time.
        '''
        if eof is None:
            eof = self.eof
        for count, thing in enumerate(self.args):
            print 'ARG:{0}. {1}'.format(count, thing)
        for name, value in self.kwargs.items():
            print 'KWARG:{0} = {1}'.format(name, value)
        
        try:
            start = time.time()
            if not self.args and not self.kwargs:
                ret = self.method()
            else:
                ret = self.method(*self.args, **self.kwargs)
            self.result=EutesterTestResult.passed
            return ret
        except SkipTestException, se:
            print TestColor.get_canned_color('failred') + \
                  "TESTUNIT SKIPPED:" + str(self.name) + "\n" + str(se) + TestColor.reset
            self.error = str(se)
            self.result = EutesterTestResult.not_run
        except Exception, e:
            buf = '\nTESTUNIT FAILED: ' + self.name
            if self.kwargs.get('html_anchors',False):
                buf += "<font color=red> Error in test unit '" + self.name + "':\n"
            out = StringIO.StringIO()
            traceback.print_exception(*sys.exc_info(),file=out)
            out.seek(0)
            buf += out.read()
            if self.kwargs.get('html_anchors',False):
                buf += ' </font>'
                print '<a name="' + str(self.error_anchor_id) + '"></a>'
            print TestColor.get_canned_color('failred') + buf + TestColor.reset
            self.error = str(e)
            self.result = EutesterTestResult.failed
            if eof:
                raise e
            else:
                pass
        finally:
            self.time_to_run = int(time.time()-start)
        
                
class EutesterTestCase(unittest.TestCase):
    color = TestColor()

    def __init__(self,name=None, debugmethod=None, log_level='debug', logfile=None, logfile_level='debug'):
        return self.setuptestcase(name=name, debugmethod=debugmethod, logfile=logfile, logfile_level=logfile_level)
        
    def setuptestcase(self,
                      name=None,
                      debugmethod=None,
                      use_default_file=False,
                      default_config='eutester.conf',
                      log_level='debug',
                      logfile=None,
                      logfile_level='debug'):
        self.name = self._testMethodName = name
        self.log_level = log_level
        self.logfile = logfile
        self.logfile_level = logfile_level
        if not self.name:
            callerfilename=inspect.getouterframes(inspect.currentframe())[1][1]
            self.name = os.path.splitext(os.path.basename(callerfilename))[0]  
            self._testMethodName = self.name
            print "setuptestname:"+str(name)
        if not hasattr(self,'args'): self.args=argparse.Namespace()
        self.debugmethod = debugmethod
        if not self.debugmethod:
            self.setup_debugmethod(logfile=self.logfile, logfile_level=self.logfile_level)
        #For QA output add preformat tag
        self.debug('<pre>')
        if not hasattr(self,'testlist'): self.testlist = []
        self.list = None
        if not hasattr(self,'configfiles'): self.configfiles=[]
        self.default_config = default_config 
        self.use_default_file = use_default_file
        if use_default_file:
            #first add $USERHOME/.eutester/eutester.conf if it exists
            self.default_config=self.get_default_userhome_config(fname=default_config)
            if self.default_config:
                self.configfiles.append(self.default_config)
        self.show_self()
                
    def compile_all_args(self):
        self.setup_parser()
        self.get_args()


                                   
    def setup_parser(self,
                   testname=None, 
                   description=None,
                   emi=True,
                   zone=True,
                   vmtype=True,
                   keypair=True,
                   credpath=True,
                   password=True,
                   config=True,
                   configblocks=True,
                   ignoreblocks=True,
                   color=True,
                   testlist=True,
                   userdata=True,
                   instance_user=True,
                   stdout_log_level=True,
                   logfile_level=True,
                   logfile=True,
                   instance_password=True,
                   region=True):
        '''
        Description: Convenience method to setup argparse parser and some canned default arguments, based
        upon the boolean values provided. For each item marked as 'True' this method will add pre-defined 
        command line arguments, help strings and default values. This will then be available by the end script 
        as an alternative to recreating these items on a per script bassis. 
    
        :type testname: string
        :param testname: Name used for argparse (help menu, etc.)
        
        :type description: string
        :param description: Description used for argparse (help menu, etc.)
        
        :type emi: boolean
        :param emi: Flag to present the emi command line argument/option for providing an image emi id via the cli
        
        :type zone: boolean
        :param zone: Flag to present the zone command line argument/option for providing a zone via the cli
        
        :type vmtype: boolean
        :param vmtype: Flag to present the vmtype command line argument/option for providing a vmtype via the cli
        
        :type keypair: boolean
        :param kepair: Flag to present the keypair command line argument/option for providing a keypair via the cli
        
        :type credpath: boolean
        :param credpath: Flag to present the credpath command line argument/option for providing a local path to creds via the cli
        
        :type password: boolean
        :param password: Flag to present the password command line argument/option for providing password 
        used in establishing machine ssh sessions
        
        :type config: boolean
        :param config: Flag to present the config file command line argument/option for providing path to config file
        
        :type configblocks: string list
        :param configblocks: Flag to present the configblocks command line arg/option used to provide list of 
                             configuration blocks to read from
                             Note: By default if a config file is provided the script will only look for blocks; 'globals', and the filename of the script being run.
        
        :type ignoreblocks: string list
        :param ignoreblocks: Flag to present the configblocks command line arg/option used to provide list of 
                             configuration blocks to ignore if present in configfile
                             Note: By default if a config file is provided the script will look for blocks; 'globals', and the filename of the script being run
 
        :type testlist: string list
        :param testlist: Flag to present the testlist command line argument/option for providing a list of testnames to run
        
        :type userdata: boolean
        :param userdata: Flag to present the userdata command line argument/option for providing userdata to instance(s) within test
        
        :type instance_user: boolean
        :param instance_user: Flag to present the instance_user command line argument/option for providing an ssh username for instance login via the cli
        
        :type instance_password: boolean
        :param instance_password: Flag to present the instance_password command line argument/option for providing a ssh password for instance login via the cli
        
        :type use_color: flag
        :param use_color: Flag to enable/disable use of ascci color codes in debug output.

        :param stdout_log_level: boolean flag to present the --log_leveel command line option to set stdout log level

        :param logfile_level: boolean flag to present the --logfile_level command line option to set the log file log level

        :param logfile: boolean flag to present the --logfile command line option to set the log file path to log to

        :param region: boolean flag to present the --region command line option to set the region for the test to use
        '''
        
        testname = testname or self.name 
        
        description = description or "Test Case Default Option Parser Description"
        #create parser
        parser = argparse.ArgumentParser( prog=testname, description=description)
        #add some typical defaults:
        if emi:
            parser.add_argument('--emi', 
                                help="pre-installed emi id which to execute these tests against", default=None)
        if credpath:
            parser.add_argument('--credpath', 
                                help="path to credentials", default=None)
        if password:
            parser.add_argument('--password', 
                                help="password to use for machine root ssh access", default=None)
        if config:
            parser.add_argument('--config',
                                help='path to config file', default=None)
        if configblocks:
            parser.add_argument('--configblocks', nargs='+',
                                help="Config sections/blocks in config file to read in", default=[])
        if ignoreblocks:
            parser.add_argument('--ignoreblocks', nargs='+',
                                help="Config blocks to ignore, ie:'globals', 'my_scripts_name', etc..", default=[])
        if testlist:
            parser.add_argument('--tests', nargs='+', 
                                help="test cases to be executed", default = [])  
        if keypair:
            parser.add_argument('--keypair',
                                help="Keypair to use in this test", default=None)
        if zone:
            parser.add_argument('--zone',
                                help="Zone to use in this test", default=None)
        if vmtype:
            parser.add_argument('--vmtype',
                                help="Virtual Machine Type to use in this test", default='c1.medium')
        if userdata:
            parser.add_argument('--user-data',
                                help="User data string to provide instance run within this test", default=None)
        if instance_user:
            parser.add_argument('--instance-user',
                                help="Username used for ssh login. Default:'root'", default='root')
        if instance_password:
            parser.add_argument('--instance-password',
                                help="Password used for ssh login. When value is 'None' ssh keypair will be used and not username/password, default:'None'", default=None)
        if region:
            parser.add_argument('--region',
                help="Use AWS region instead of Eucalyptus", default=None)
        if color:
            parser.add_argument('--use_color', dest='use_color', action='store_true', default=False)
        if stdout_log_level:
            parser.add_argument('--log_level',
                                help="log level for stdout logging", default='debug')
        if logfile:
            parser.add_argument('--logfile',
                                help="file path to log to (in addtion to stdout", default=None)
        if logfile_level:
            parser.add_argument('--logfile_level',
                                help="log level for log file logging", default='debug')
        parser.add_argument('--html-anchors', dest='html_anchors', action='store_true',
                                help="Print HTML anchors for jumping through test results", default=False)
        self.parser = parser  
        return parser
    
    def disable_color(self):
        self.set_arg('use_color', False)
        self.use_color = False
    
    def enable_color(self):
        self.set_arg('use_color', True)
        self.use_color = True
        

    def setup_debugmethod(self, testcasename=None, log_level=None, logfile=None, logfile_level=None):
        print "setup_debugmethod: \ntestcasename:"+ str(testcasename) \
                                + '\nlog_level:'+str(log_level) \
                                + '\nlogfile:' +str(logfile) \
                                + '\nlogfile_level:' +str(logfile_level)
        name = testcasename or self.name

        if not logfile and self.has_arg('logfile'):
            logfile = self.args.logfile
        logfile = logfile or self.logfile

        if self.has_arg('logfile_level'):
            logfile_level = self.args.logfile_level
        logfile_level = logfile_level or self.logfile_level or 'debug'

        if not log_level and self.has_arg('log_level'):
            log_level = self.args.log_level
        log_level = log_level or self.log_level or 'debug'

        print "Starting setup_debugmethod, name:"+str(name)
        print "After populating... setup_debugmethod: testcasename:"+ str(testcasename) \
              + 'log_level:'+str(log_level) \
              + 'logfile:' +str(logfile) \
              + 'logfile_level:' +str(logfile_level)
        if not name:
            if hasattr(self,'name'):
                if isinstance(self.name, types.StringType):
                    name = self.name
            else:
                name = 'EutesterTestCase'
        self.logger = Eulogger(identifier=str(name),stdout_level=log_level, logfile=logfile, logfile_level='debug')
        self.debugmethod = self.logger.log.debug
        if not self.has_arg('logger'):
            self.add_arg('logger',self.logger)
        if not self.has_arg('debug_method'):
            self.add_arg('debug_method', self.debug)

    def debug(self,msg,traceback=1,color=None, linebyline=True):
        '''
        Description: Method for printing debug
        
        type msg: string
        param msg: Mandatory string buffer to be printed in debug message
        
        type traceback: integer
        param traceback: integer value for what frame to inspect to derive the originating method and method line number
        
        type color: TestColor color
        param color: Optional ascii text color scheme. See TestColor for more info. 
        '''
        try:
            if not self.debugmethod:
                self.setup_debugmethod()
        except:
            self.setup_debugmethod()

        if self.has_arg("use_color"):
            self.use_color = bool(self.args.use_color)
        else:
            self.use_color = False
            
        colorprefix=""
        colorreset=""
        #if a color was provide
        if color and self.use_color:
            colorprefix = TestColor.get_canned_color(color) or color
            colorreset = str(TestColor.get_canned_color('reset'))
        msg = str(msg)       
        curframe = None    
        curframe = inspect.currentframe(traceback)
        lineno = curframe.f_lineno
        self.curframe = curframe
        frame_code  = curframe.f_code
        frame_globals = curframe.f_globals
        functype = type(lambda: 0)
        funcs = []
        for func in gc.get_referrers(frame_code):
            if type(func) is functype:
                if getattr(func, "func_code", None) is frame_code:
                    if getattr(func, "func_globals", None) is frame_globals:
                        funcs.append(func)
                        if len(funcs) > 1:
                            return None
            cur_method= funcs[0].func_name if funcs else ""
        if linebyline:
            for line in msg.split("\n"):
                self.debugmethod("("+str(cur_method)+":"+str(lineno)+"): "+colorprefix+line.strip()+colorreset )
        else:
            self.debugmethod("("+str(cur_method)+":"+str(lineno)+"): "+colorprefix+str(msg)+colorreset )

    def run_test_list_by_name(self, list, eof=None):
        unit_list = []
        for test in list:
            unit_list.append( self.create_testunit_by_name(test) )

        ### Run the EutesterUnitTest objects
        return self.run_test_case_list(unit_list,eof=eof)

    def create_testunit_from_method(self,method, *args, **kwargs):
        '''
        Description: Convenience method calling EutesterTestUnit. 
                     Creates a EutesterTestUnit object from a method and set of arguments to be fed to that method
        
        :type method: method
        :param method: The underlying method for this object to wrap, run and provide information on
        
        :type eof: boolean
        :param eof: Boolean to indicate whether this testunit should cause a test list to end of failure
        
        :type autoarg: boolean
        :param autoarg: Boolean to indicate whether to autopopulate this testunit with values from global testcase.args
        
        :type args: list of positional arguments
        :param args: the positional arguments to be fed to the given testunit 'method'
        
        :type kwargs: list of keyword arguements 
        :param kwargs: list of keyword 
        
        :rtype: EutesterTestUnit
        :returns: EutesterTestUnit object
        '''   
        eof=False
        autoarg=True
        methvars = self.get_meth_arg_names(method)
        #Pull out value relative to this method, leave in any that are intended to be passed through
        if 'autoarg' in kwargs:
            if 'autoarg' in methvars:
                autoarg = kwargs['autoarg']
            else:
                autoarg = kwargs.pop('autoarg')
        if 'eof' in kwargs:
            if 'eof' in methvars:
                eof = kwargs['eof']
            else:
                eof = kwargs.pop('eof')
        ## Only pass the arg if we need it otherwise it will print with all methods/testunits
        if self.args.html_anchors:
            testunit = EutesterTestUnit(method, *args, html_anchors=self.args.html_anchors ,**kwargs)
        else:
            testunit = EutesterTestUnit(method, *args, **kwargs)
        testunit.eof = eof
        #if autoarg, auto populate testunit arguements from local testcase.args namespace values
        if autoarg:
            self.populate_testunit_with_args(testunit)
        return testunit 
    
    def status(self,msg,traceback=2, b=1,a=0 ,testcolor=None):
        '''
        Description: Convenience method to format debug output
        
        :type msg: string
        :param msg: The string to be formated and printed via self.debug
        
        :type traceback: integer
        :param traceback: integer value for what frame to inspect to derive the originating method and method line number
        
        :type b: integer
        :param b:number of blank lines to print before msg
        
        :type a: integer
        :param a:number of blank lines to print after msg
        
        :type testcolor: TestColor color
        :param testcolor: Optional TestColor ascii color scheme
        '''
        alines = ""
        blines = ""
        for x in xrange(0,b):
            blines=blines+"\n"
        for x in xrange(0,a):
            alines=alines+"\n"
        line = "-------------------------------------------------------------------------"
        out = blines+line+"\n"+msg+"\n"+line+alines
        self.debug(out, traceback=traceback, color=testcolor,linebyline=False)  
        
    def startmsg(self,msg=""):
        self.status(msg, traceback=3,testcolor=TestColor.get_canned_color('whiteonblue'))
        
    def endsuccess(self,msg=""):
        msg = "- UNIT ENDED - " + msg
        self.status(msg, traceback=2,a=1, testcolor=TestColor.get_canned_color('whiteongreen'))

    def errormsg(self,msg=""):
        msg = "- ERROR - " + msg
        self.status(msg, traceback=2,a=1,testcolor=TestColor.get_canned_color('failred'))

    def endfailure(self,msg="" ):
        msg = "- FAILED - " + msg
        self.status(msg, traceback=2,a=1,testcolor=TestColor.get_canned_color('failred'))
    
    def resultdefault(self,msg,printout=True,color='blueongrey'):
        if printout:
            self.debug(msg,traceback=2,color=TestColor.get_canned_color('blueongrey'),linebyline=False)
        msg = self.format_line_for_color(msg, color)
        return msg
    
    def resultfail(self,msg,printout=True, color='redongrey'):
        if printout:
            self.debug(msg,traceback=2, color=TestColor.get_canned_color('redongrey'),linebyline=False)
        msg = self.format_line_for_color(msg, color)
        return msg
        
    def resulterr(self,msg,printout=True,color='failred'):
        if printout:
            self.debug(msg,traceback=2, color=TestColor.get_canned_color(color),linebyline=False)
        msg = self.format_line_for_color(msg, color)
        return msg
    
    def format_line_for_color(self,msg,color):
        if not self.use_color:
            return msg
        end=""
        if msg.endswith('\n'):
            msg = msg.rstrip()
            end="\n"
        msg = TestColor.get_canned_color(color)+str(msg)+TestColor.reset+end
        return msg
    
    def get_pretty_args(self,testunit):
        '''
        Description: Returns a string buf containing formated arg:value for printing later
        
        :type: testunit: Eutestcase.eutestertestunit object
        :param: testunit: A testunit object for which the namespace args will be used
        
        :rtype: string
        :returns: formated string containing args and their values.  
        '''
        
        buf =  "\nEnd on Failure:" +str(testunit.eof)
        buf += "\nPassing ARGS:"
        if not testunit.args and not testunit.kwargs:
            buf += '\"\"\n'
        else:
            buf += "\n---------------------\n"
            varnames = self.get_meth_arg_names(testunit.method)
            if testunit.args:
                for count,arg in enumerate(testunit.args):
                    buf += str(varnames[count+1])+" : "+str(arg)+"\n"
            if testunit.kwargs:
                for key in testunit.kwargs:
                    buf += str(key)+" : "+str(testunit.kwargs[key])+"\n"
            buf += "---------------------\n"
        return buf
    
    def run_test_case_list(self, list, eof=False, clean_on_exit=True, printresults=True):
        '''
        Desscription: wrapper to execute a list of ebsTestCase objects
        
        :type list: list
        :param list: list of EutesterTestUnit objects to be run
        
        :type eof: boolean
        :param eof: Flag to indicate whether run_test_case_list should exit on any failures. If this is set to False it will exit only when
                    a given EutesterTestUnit fails and has it's eof flag set to True. 
        
        :type clean_on_exit: boolean
        :param clean_on_exit: Flag to indicate if clean_on_exit should be ran at end of test list execution. 
        
        :type printresults: boolean
        :param printresults: Flag to indicate whether or not to print a summary of results upon run_test_case_list completion. 
        
        :rtype: integer
        :returns: integer exit code to represent pass/fail of the list executed. 
        '''
        self.testlist = list 
        start = time.time()
        tests_ran=0
        test_count = len(list)
        t = Timer("/tmp/eutester_" + str(uuid.uuid4()).replace("-", ""))
        try:
            for test in list:
                tests_ran += 1
                self.print_test_unit_startmsg(test)
                try:
                    id = t.start()
                    test.run(eof=eof or test.eof)
                    t.end(id, str(test.name))
                except Exception, e:
                    self.debug('Testcase:'+ str(test.name)+' error:'+str(e))
                    if eof or (not eof and test.eof):
                        self.endfailure(str(test.name))
                        raise e
                    else:
                        self.endfailure(str(test.name))
                else:
                    self.endsuccess(str(test.name))
                self.debug(self.print_test_list_short_stats(list))
                        
        finally:
            elapsed = int(time.time()-start)
            msgout =  "RUN TEST CASE LIST DONE:\n"
            msgout += "Ran "+str(tests_ran)+"/"+str(test_count)+" tests in "+str(elapsed)+" seconds\n"
            t.finish()

            if printresults:
                try:
                    self.debug("Printing pre-cleanup results:")
                    msgout += self.print_test_list_results(list=list,printout=False)
                    self.status(msgout)
                except:pass
            try:
                 if clean_on_exit:
                    cleanunit = self.create_testunit_from_method(self.clean_method)
                    list.append(cleanunit)
                    try:
                        self.print_test_unit_startmsg(cleanunit)
                        cleanunit.run()
                    except Exception, e:
                        out = StringIO.StringIO()
                        traceback.print_exception(*sys.exc_info(),file=out)
                        out.seek(0)
                        self.debug("Failure in cleanup: " + str(e) + "\n" + out.read())
                    if printresults:
                        msgout = self.print_test_list_results(list=list,printout=False)
                        self.status(msgout)
            except: 
                pass
            self.testlist = copy.copy(list)
            passed = 0
            failed = 0
            not_run = 0
            for test in list:
                if test.result == EutesterTestResult.passed:
                    passed += 1
                if test.result == EutesterTestResult.failed:
                    failed += 1
                if test.result == EutesterTestResult.not_run:
                    not_run += 1
            total = passed + failed + not_run
            print "passed:"+str(passed)+" failed:" + str(failed) + " not_run:" + str(not_run) + " total:"+str(total)
            if failed:
                return(1)
            else:
                return(0)

    def print_test_unit_startmsg(self,test):
        startbuf = ''
        if self.args.html_anchors:
            link = '<a name="' + str(test.anchor_id) + '"></a>\n'
            startbuf += '<div id="myDiv" name="myDiv" title="Example Div Element" style="color: #0900C4; font: Helvetica 12pt;border: 1px solid black;">'
            startbuf += str(link)
        startbuf += "STARTING TESTUNIT: " + test.name
        argbuf = self.get_pretty_args(test)
        startbuf += str(test.description)+str(argbuf)
        startbuf += 'Running list method: "'+str(self.print_testunit_method_arg_values(test))+'"'
        if self.args.html_anchors:
            startbuf += '\n </div>'
        self.startmsg(startbuf)
    
    def has_arg(self,arg):
        '''
        Description: If arg is present in local testcase args namespace, will return True, else False
        
        :type arg: string
        :param arg: string name of arg to check for.

        :rtype: boolean
        :returns: True if arg is present, false if not
        '''
        arg = str(arg)
        if hasattr(self,'args'):
            if self.args and (arg in self.args):
                return True
        return False
         
    def get_arg(self,arg):
        '''
        Description: Fetchs the value of an arg within the local testcase args namespace. If the arg
        does not exist, None will be returned. 
        
        :type arg: string
        :param arg: string name of arg to get.
        
        :rtype: value
        :returns: Value of arguement given, or None if not found
        '''
        if self.has_arg(arg):
            return getattr(self.args,str(arg))
        return None
    
    def add_arg(self,arg,value):
        '''
        Description: Adds an arg 'arg'  within the local testcase args namespace and assigns it 'value'. 
        If arg exists already in testcase.args, then an exception will be raised. 
        
        :type arg: string
        :param arg: string name of arg to set. 
        
        :type value: value
        :param value: value to set arg to
        '''
        if self.has_arg(arg):
            raise Exception("Arg"+str(arg)+'already exists in args')
        else:
            self.args.__setattr__(arg,value)
    
    def set_arg(self,arg, value):
        '''
        Description: Sets an arg 'arg'  within the local testcase args namespace to 'value'. 
        If arg does not exist in testcase.args, then it will be created. 
        
        :type arg: string
        :param arg: string name of arg to set. 
        
        :type value: value
        :param value: value to set arg to
        '''
        
        if self.has_arg(arg):
            new = argparse.Namespace()
            for val in self.args._get_kwargs():
                if arg != val[0]:
                    new.__setattr__(val[0],val[1])
            new.__setattr__(arg,value)
            self.args = new
        else:
            self.args.__setattr__(arg,value)
    
    
    def clean_method(self):
        raise Exception("Clean_method was not implemented. Was run_list using clean_on_exit?")

    def print_test_list_results(self,list=None, printout=True, printmethod=None):
        '''
        Description: Prints a formated list of results for a list of EutesterTestUnits
        
        :type list: list
        :param list: list of EutesterTestUnits
        
        :type printout: boolean
        :param printout: boolean to flag whether to print using printmethod or self.debug, 
                         or to return a string buffer representing the results output 
        
        :type printmethod: method
        :param printmethod: method to use for printing test result output. Default is self.debug
        '''

        buf = "\nTESTUNIT LIST SUMMARY FOR " + str(self.name) + "\n"
        if list is None:
            list=self.testlist
        if not list:
            raise Exception("print_test_list_results, error: No Test list provided")
        if printmethod is None:
            printmethod = lambda msg: self.debug(msg,linebyline=False)
        printmethod("Test list results for testcase:"+str(self.name))

        for testunit in list:
            buf += self.resultdefault("\n"+ self.getline(80)+"\n", printout=False)
            #Ascii mark up errors using pmethod() so errors are in bold/red, etc...
            pmethod = self.resultfail if not testunit.result == EutesterTestResult.passed else self.resultdefault
            test_summary_line = str(" ").ljust(20) + str("| RESULT: " + str(testunit.result)).ljust(20) + "\n" +\
                                str(" ").ljust(20) + "| TEST NAME: " + str(testunit.name) + "\n" + \
                                str(" ").ljust(20) + str("| TIME : " + str(testunit.time_to_run))


            buf += pmethod(str(test_summary_line),printout=False)
            buf += pmethod("\n" + str(" ").ljust(20) + "| ARGS: "
                           + str(self.print_testunit_method_arg_values(testunit)), printout=False)
            #Print additional line showing error in the failed case...
            if testunit.result == EutesterTestResult.failed:
                    err_sum = "\n".join(str(testunit.error).splitlines()[0:3])
                    test_error_line = 'ERROR:('+str(testunit.name)+'): '\
                                      + str(err_sum) \
                                      + '\n'
                    buf += "\n"+str(self.resulterr(test_error_line, printout=False))
            if testunit.result == EutesterTestResult.not_run:
                err_sum = "\n".join(str(testunit.error).splitlines()[0:3])
                test_error_line = 'NOT_RUN:('+str(testunit.name)+'): ' \
                                  + str(err_sum) \
                                  + '\n'
                buf += "\n"+str(self.resulterr(test_error_line, printout=False))
        buf += self.resultdefault("\n"+ self.getline(80)+"\n", printout=False)
        buf += str(self.print_test_list_short_stats(list))
        buf += "\n"
        if printout:
            printmethod(buf)
        else:
            return buf

        
    def print_test_list_short_stats(self,list,printmethod=None):
        results={}
        mainbuf = "RESULTS SUMMARY FOR '"+str(self.name)+"':\n"
        fieldsbuf = ""
        resultsbuf= ""
        total = 0 
        elapsed = 0
        #initialize a dict containing all the possible defined test results
        fields = dir(EutesterTestResult)
        for fieldname in fields[2:len(fields)]:
            results[fieldname]=0
        #increment values in results dict based upon result of each testunit in list
        for testunit in list:
            total += 1
            elapsed += testunit.time_to_run
            results[testunit.result] += 1
        fieldsbuf += str('| TOTAL').ljust(10)
        resultsbuf += str('| ' + str(total)).ljust(10)
        for field in results:
            fieldsbuf += str('| ' + field.upper()).ljust(10)
            resultsbuf += str('| ' + str(results[field])).ljust(10)
        fieldsbuf += str('| TIME_ELAPSED').ljust(10)
        resultsbuf += str('| '+str(elapsed)).ljust(10)
        mainbuf += "\n"+self.getline(len(fieldsbuf))+"\n"
        mainbuf += fieldsbuf
        mainbuf += "\n"+self.getline(len(fieldsbuf))+"\n"
        mainbuf += resultsbuf
        mainbuf += "\n"+self.getline(len(fieldsbuf))+"\n"
        if printmethod:
            printmethod(mainbuf)
        return mainbuf
    
    @classmethod  
    def get_testunit_method_arg_dict(cls,testunit):
        argdict={}
        spec = inspect.getargspec(testunit.method)
        if isinstance(testunit.method,types.FunctionType):
            argnames = spec.args
        else:
            argnames = spec.args[1:len(spec.args)]
        defaults = spec.defaults or []
        #Initialize the return dict
        for argname in argnames:
            argdict[argname]='<!None!>'
        #Set the default values of the testunits method
        for x in xrange(0,len(defaults)):
            argdict[argnames.pop()]=defaults[len(defaults)-x-1]
        #Then overwrite those with the testunits kwargs values
        for kwarg in testunit.kwargs:
            argdict[kwarg]=testunit.kwargs[kwarg]
        #then add the positional args in if they apply...
        for count, value in enumerate(testunit.args):
            argdict[argnames[count]]=value
        return argdict
    
    @classmethod
    def print_testunit_method_arg_values(cls,testunit):
        buf = testunit.name+"("
        argdict = EutesterTestCase.get_testunit_method_arg_dict(testunit)
        for arg in argdict:
            buf += str(arg)+":"+str(argdict[arg])+","
        buf = buf.rstrip(',')
        buf += ")"
        return buf
        
        
    def getline(self,len):
        buf = ''
        for x in xrange(0,len):
            buf += '-'
        return buf
    
    def run_method_by_name(self,name, obj=None, *args, **kwargs):
        '''
        Description: Find a method within an instance of obj and run that method with either args/kwargs provided or
        any self.args which match the methods varname. 
        
        :type name: string
        :param name: Name of method to look for within instance of object 'obj'
        
        :type obj: class instance
        :param obj: Instance type, defaults to self testcase object
        
        :type args: positional arguements
        :param args: None or more positional arguments to be passed to method to be run
        
        :type kwargs: keyword arguments
        :param kwargs: None or more keyword arguements to be passed to method to be run
        '''
        obj = obj or self
        meth = getattr(obj,name)
        return self.do_with_args(meth, *args, **kwargs)
        
        
        
    
    def create_testunit_by_name(self, name, obj=None, eof=True, autoarg=True, *args,**kwargs ):
        '''
        Description: Attempts to match a method name contained with object 'obj', and create a EutesterTestUnit object from that method and the provided
        positional as well as keyword arguments provided. 
        
        :type name: string
        :param name: Name of method to look for within instance of object 'obj'
        
        :type obj: class instance
        :param obj: Instance type, defaults to self testcase object
        
        :type args: positional arguements
        :param args: None or more positional arguments to be passed to method to be run
        
        :type kwargs: keyword arguments
        :param kwargs: None or more keyword arguements to be passed to method to be run
        '''
        eof=False
        autoarg=True
        obj = obj or self
        meth = getattr(obj,name)
        methvars = self.get_meth_arg_names(meth)


        
        #Pull out value relative to this method, leave in any that are intended to be passed through
        if 'autoarg' in kwargs:
            if 'autoarg' in methvars:
                autoarg = kwargs['autoarg']
            else:
                autoarg = kwargs.pop('autoarg')
        if 'eof' in kwargs:
            if 'eof' in methvars:
                eof = kwargs['eof']
            else:
                eof = kwargs.pop('eof')
        if 'obj' in kwargs:
            if 'obj' in methvars:
                obj = kwargs['obj']
            else:
                obj = kwargs.pop('obj')

        testunit = EutesterTestUnit(meth, *args, **kwargs)
        testunit.eof = eof

        #if autoarg, auto populate testunit arguements from local testcase.args namespace values
        if autoarg:
            self.populate_testunit_with_args(testunit)
            
        return testunit

        
    def get_args(self,use_cli=True, file_sections=[]):
        '''
        Description: Method will attempt to retrieve all command line arguments presented through local 
        testcase's 'argparse' methods, as well as retrieve all EuConfig file arguments. All arguments 
        will be combined into a single namespace object held locally at 'testcase.args'. Note: cli arg 'config'
        must be provided for config file valus to be store in self.args. 
        
        :type use_cli: boolean
        :param use_cli: Boolean to indicate whether or not to create and read from a cli argparsing object
        
        :type use_default_file: boolean
        :param use_default_files: Boolean to indicate whether or not to read default config file at $HOME/.eutester/eutester.conf (not indicated by cli)
        
        :type sections: list
        :param sections: list of EuConfig sections to read configuration values from, and store in self.args.
        
        :rtype: arparse.namespace obj
        :returns: namespace object with values from cli and config file arguements 
        '''
        configfiles=[]
        args=None
        #build out a namespace object from the config file first
        cf = argparse.Namespace()
        
        
        if (hasattr(self, 'use_default_file') and self.use_default_file) and \
                (hasattr(self, 'use_default_config') and self.default_config):
            try:
                configfiles.append(self.default_config)
            except Exception, e:
                self.debug("Unable to read config from file: " + str(e))

        #Setup/define the config file block/sections we intend to read from
        confblocks = file_sections or ['MEMO','globals']
        if self.name:
            confblocks.append(self.name)
        
        if use_cli:
            #See if we have CLI args to read
            if not hasattr(self,'parser') or not self.parser:
                self.setup_parser()
            #first get command line args to see if there's a config file
            cliargs = self.parser.parse_args()
            
        #if a config file was passed, combine the config file and command line args into a single namespace object
        if cliargs:
            #Check to see if there's explicit config sections to read
            if 'configblocks' in cliargs.__dict__:
                confblocks = confblocks +cliargs.configblocks
            #Check to see if there's explicit config sections to ignore
            if 'ignoreblocks' in cliargs.__dict__:
                for block in cliargs.ignoreblocks:
                    if block in confblocks:
                        confblocks.remove(block)
            
            #if a file or list of config files is specified add it to our list...
            if ('config' in cliargs.__dict__) and  cliargs.config:
                for cfile in str(cliargs.config).split(','):
                    if not cfile in configfiles:
                        configfiles.append(cfile)
            #legacy support for config, configfile config_file arg names...
            if ('config_file' in cliargs.__dict__) and  cliargs.config:
                for cfile in str(cliargs.config).split(','):
                    if not cfile in configfiles:
                        configfiles.append(cfile)
            #legacy support for config, configfile config_file arg names...
            if ('configfile' in cliargs.__dict__) and  cliargs.config:
                for cfile in str(cliargs.config).split(','):
                    if not cfile in configfiles:
                        configfiles.append(cfile)

        #store config block list for debug purposes
        cf.__setattr__('configsections',copy.copy(confblocks))
        
        #create euconfig configparser objects from each file. 
        euconfigs = []
        self.configfiles = configfiles
        try:
            for configfile in configfiles:
                euconfigs.append(EuConfig(filename=configfile))
        except Exception, e:
            self.debug("Unable to read config from file: " + str(e))

        for conf in euconfigs:
            cblocks = copy.copy(confblocks)
            #if MEMO field in our config block add it first if to set least precedence
            if 'MEMO' in cblocks:
                if conf.config.has_section('MEMO'):
                    for item in conf.config.items('MEMO'):
                        cf.__setattr__(str(item[0]), item[1])
                    cblocks.remove('MEMO')
            
            #If globals are still in our confblocks, add globals first if the section is present in config
            if 'globals' in cblocks:
                if conf.config.has_section('globals'):
                    for item in conf.config.items('globals'):
                        cf.__setattr__(str(item[0]), item[1])
                    cblocks.remove('globals')
            
            #Now iterate through remaining config block in file and add to args...
            for section in confblocks:
                if conf.config.has_section(section):
                    for item in conf.config.items(section):
                        cf.__setattr__(str(item[0]), item[1])
                        
        if cliargs:
            #Now make sure any conflicting args provided on the command line take precedence over config file args
            for val in cliargs._get_kwargs():
                if (not val[0] in cf ) or (val[1] is not None):
                    cf.__setattr__(str(val[0]), val[1])
            args = cf
        #Legacy script support: level set var names for config_file vs configfile vs config and credpath vs cred_path
        try:
            if 'config' in args:
                args.config_file = args.config
                args.configfile = args.config

        except: pass
        try:
            args.cred_path = args.credpath
        except: pass
        self.args = args
        #finally add the namespace args to args for populating other testcase objs from this one
        if not self.has_arg('args'): args.__setattr__('args',copy.copy(args))
        #Refresh our debug method(s) in the case the args provided give instruction on logging
        self.setup_debugmethod()
        self.show_self()
        return args
    
        
    
    def get_default_userhome_config(self,fname='eutester.conf'):
        '''
        Description: Attempts to fetch the file 'fname' from the current user's home dir. 
        Returns path to the user's home dir default eutester config file. 
        
        :type fname: string
        :param fname: the eutester default config file name
        
        :rtype: string
        :returns: string representing the path to 'fname', the default eutester conf file. 
        
        '''
        try:
            def_path = os.getenv('HOME')+'/.eutester/'+str(fname)
        except: return None
        try:
            os.stat(def_path)
            return def_path
        except:
            self.debug("Default config not found:"+str(def_path))
            return None
    
    def show_self(self):
        list=[]
        list.append(("NAME:", str(self.name)))
        list.append(('TEST LIST:', str(self.testlist)))
        list.append(('CONFIG FILES:', self.configfiles))
        argbuf=""
        argbuf = str("TESTCASE INFO:").ljust(25)        
        argbuf += str("\n----------").ljust(25)
        for val in list:
            argbuf += '\n'+str(val[0]).ljust(25)+" --->:  "+str(val[1])
        self.status(argbuf)
        self.show_args()
        
        
        
        
        
    def show_args(self,args=None):
        '''
        Description: Prints args names and values for debug purposes. 
                     By default will use the local testcase.args, else args can be provided. 
        
        :type args: namespace object
        :param args: namespace object to be printed,by default None will print local testcase's args.
        '''
        args= args or self.args if hasattr(self,'args') else None
        argbuf = str("TEST ARGS:").ljust(25)+"        "+str("VALUE:")
        argbuf += str("\n----------").ljust(25)+"        "+str("------")
        if args:
            for val in args._get_kwargs():
                argbuf += '\n'+str(val[0]).ljust(25)+" --->:  "+str(val[1])
            self.status(argbuf)
            
    
    def populate_testunit_with_args(self,testunit,namespace=None):
        '''
        Description: Checks a given test unit's available positional and key word args lists for matching
                     values contained with the given namespace, by default will use local testcase.args. 
                     If testunit's underlying method has arguments matching the namespace provided, then those
                     args will be applied to the testunits args referenced when running the testunit. 
                     Namespace values will not be applied/overwrite testunits, if the testunit already has conflicting
                     values in it's args(positional) list or kwargs(keyword args) dict.
        :type: testunit: Eutestcase.eutestertestunit object
        :param: testunit: A testunit object for which the namespace values will be applied 
        
        :type: namespace: namespace obj
        :param: namespace: namespace obj containing args/values to be applied to testunit. None by default will use local
                            testunit args. 
        '''
        self.debug("Attempting to populate testunit:"+str(testunit.name)+", with testcase.args...")
        args_to_apply = namespace or self.args
        if not args_to_apply:
            return
        testunit_obj_args = {}
        
        #copy the test units key word args
        testunit_obj_args.update(copy.copy(testunit.kwargs))
        self.debug("Testunit keyword args:"+str(testunit_obj_args))
        
        #Get all the var names of the underlying method the testunit is wrapping
        method_args = self.get_meth_arg_names(testunit.method)
        offset = 0 if isinstance(testunit.method,types.FunctionType) else 1
        self.debug("Got method args:"+str(method_args))
       
            
        #Add the var names of the positional args provided in testunit.args to check against later
        #Append to the known keyword arg list
        for x,arg in enumerate(testunit.args):
            testunit_obj_args[method_args[x+offset]] = arg
        
        self.debug("test unit total args:"+str(testunit_obj_args))
        #populate any global args which do not conflict with args already contained within the test case
        #first populate matching method args with our global testcase args taking least precedence
        for apply_val in args_to_apply._get_kwargs():
            for methvar in method_args:
                if methvar == apply_val[0]:
                    self.debug("Found matching arg for:"+str(methvar))
                    #Don't overwrite existing testunit args/kwargs that have already been assigned
                    if apply_val[0] in testunit_obj_args:
                            self.debug("Skipping populate because testunit already has this arg:"+str(methvar))
                            continue
                    #Append cmdargs list to testunits kwargs
                    testunit.set_kwarg(methvar,apply_val[1]) 
                    #testunit.kwargs[methvar]=apply_val[1]
       
       
        
    
    def do_with_args(self, meth, *args, **kwargs):
        '''
        Description: Convenience method used to wrap the provided instance_method, function, or object type 'meth' and populate meth's positional 
        and keyword arguments with the local testcase.args created from the CLI and/or config file, as well as
        the *args and **kwargs variable length arguments passed into this method. 
        
        :type meth: method
        :param meth: A method or class initiator to wrapped/populated with this testcase objects namespace args
        
        :type args: positional arguments
        :param args: None or more values representing positional arguments to be passed to 'meth' when executed. These will
                     take precedence over local testcase obj namespace args
        
        :type kwargs: keyword arguments
        :param kwargs: None or more values reprsenting keyword arguments to be passed to 'meth' when executed. These will
                     take precedence over local testcase obj namespace args and positional args
        '''
        
        if not hasattr(self,'args'):
            raise Exception('TestCase object does not have args yet, see: get_args and setup_parser options')
        tc_args = self.args
        cmdargs={}
        f_code = self.get_method_fcode(meth)
        vars = self.get_meth_arg_names(meth)
        self.debug("do_with_args: Method:"+str(f_code.co_name)+", Vars:"+str(vars))
        
        #first populate matching method args with our global testcase args...
        for val in tc_args._get_kwargs():
            for var in vars:
                if var == val[0]:
                    cmdargs[var]=val[1]
        #Then overwrite/populate with any given positional local args...
        for count,arg in enumerate(args):
            cmdargs[vars[count+1]]=arg
        #Finall overwrite/populate with any given key word local args...
        for name,value in kwargs.items():
            for var in vars:
                if var == name:
                    cmdargs[var]=value
        self.debug('create_with_args: running '+str(f_code.co_name)+"("+str(cmdargs).replace(':','=')+")")
        return meth(**cmdargs)            
        
    @classmethod
    def get_method_fcode(cls, meth):
        f_code = None
        #Find the args for the method passed in...
        #Check for object/class init...
        if isinstance(meth,types.ObjectType):
            try:
                f_code = meth.__init__.__func__.func_code
            except:pass   
        #Check for instance method...
        if isinstance(meth,types.MethodType):
            try:
                f_code = meth.im_func.func_code
            except:pass    
        #Check for function...
        if isinstance(meth,types.FunctionType):
            try:
                f_code = meth.func_code
            except:pass
        if not f_code:
            raise Exception("get_method_fcode: Could not find function_code for passed method of type:"+str(type(meth)))
        return f_code
    
    @classmethod
    def get_meth_arg_names(cls,meth):
        '''
        Description: Return varnames within argcount        
        :type:meth: method
        :param: meth: method to fetch arg names for
        
        :rtype: list
        :returns: list of strings representing the varnames within argcount for this method
        '''
        fcode = cls.get_method_fcode(meth)
        varnames = fcode.co_varnames[0:fcode.co_argcount]
        return varnames



class SkipTestException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)
            
    
