
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
from eutester.eulogger import Eulogger
from eutester.euconfig import EuConfig
import StringIO
import copy

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
        self.args = args
        self.kwargs = kwargs
        self.name = str(method.__name__)
        self.result=EutesterTestResult.not_run
        self.time_to_run=0
        self.description=self.get_test_method_description()
        self.eof=False
        self.error = ""
        print "Creating testunit:"+str(self.name)+", args:"
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
        Attempts to derive test unit description for the registered test method
        '''
        desc = "\nMETHOD:"+str(self.name)+", TEST DESCRIPTION:\n"
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
    
    def run(self):
        '''
        Description: Wrapper which attempts to run self.method and handle failures, record time.
        '''
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
        except Exception, e:
            out = StringIO.StringIO()
            traceback.print_exception(*sys.exc_info(),file=out)
            out.seek(0)
            buf = out.read()
            print TestColor.get_canned_color('failred')+buf+TestColor.reset
            self.error = str(e)
            self.result = EutesterTestResult.failed
            if self.eof:
                raise e
            else:
                pass
        finally:
            self.time_to_run = int(time.time()-start)
        
                
class EutesterTestCase(unittest.TestCase):
    color = TestColor()

    def __init__(self,name=None, debugmethod=None, use_default_file=True, default_config='eutester.conf'):
        return self.setuptestcase(name=name, debugmethod=debugmethod, use_default_file=use_default_file, default_config=default_config)
        
    def setuptestcase(self, name=None, debugmethod=None, use_default_file=True, default_config='eutester.conf' ):
        self.name = name 
        if not self.name:
            callerfilename=inspect.getouterframes(inspect.currentframe())[1][1]
            self.name = os.path.splitext(os.path.basename(callerfilename))[0]  
        self.debugmethod = debugmethod
        if not self.debugmethod:
            self.setup_debugmethod(name)
        if not hasattr(self,'testlist'): self.testlist = []
        if not hasattr(self,'configfiles'): self.configfiles=[]
        self.default_config = default_config 
        self.use_default_file = use_default_file
        if use_default_file:
            #first add $USERHOME/.eutester/eutester.conf if it exists
            self.default_config=self.get_default_userhome_config(fname=default_config)
            if self.default_config:
                self.configfiles.append(self.default_config)
        if not hasattr(self,'args'): self.args=argparse.Namespace()
        self.show_self()
                

                                   
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
                   testlist=True):
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
        
        :type use_color: flag
        :param use_color: Flag to enable/disable use of ascci color codes in debug output. 
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
                                help="password to use for machine root ssh access", default='foobar')
        if config:
            parser.add_argument('--config',
                                help='path to config file', default='../input/2btested.lst')   
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
        if color: 
            parser.add_argument('--use_color', dest='use_color', action='store_true', default=False)
        self.parser = parser  
        return parser
    
    def disable_color(self):
        self.use_color = False
    
    def enable_color(self):
        self.use_color = True
        
        
    def setup_debugmethod(self,name=None):
            name = name if name else self.name if hasattr(self,'name') else self.__class__.__name__
            print "Setting up debug method using name:"+str(name)
            logger = Eulogger(identifier=str(name))
            self.debugmethod = logger.log.debug

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
            
   
            
    def create_testunit_from_method(self,method,eof=False, autoarg=True, *args, **kwargs):
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
        msg = "- STARTING TESTUNIT:  - " + msg
        self.status(msg, traceback=3,testcolor=TestColor.get_canned_color('whiteonblue'))
        
    def endsuccess(self,msg=""):
        msg = "- SUCCESS ENDED - " + msg
        self.status(msg, traceback=2,a=1, testcolor=TestColor.get_canned_color('whiteonblue'))
      
    def endfailure(self,msg="" ):
        msg = "- FAILED - " + msg
        self.status(msg, traceback=2,a=1,testcolor=TestColor.get_canned_color('failred'))
    
    def resultdefault(self,msg,printout=True,color='blueongrey'):
        if printout:
            self.debug(msg,traceback=2,color=TestColor.get_canned_color('blueongrey'),linebyline=False)
        msg = TestColor.get_canned_color(color)+str(msg)+TestColor.reset
        return msg
    
    def resultfail(self,msg,printout=True, color='redongrey'):
        if printout:
            self.debug(msg,traceback=2, color=TestColor.get_canned_color('redongrey'),linebyline=False)
        msg = TestColor.get_canned_color(color)+str(msg)+TestColor.reset
        return msg
        
    def resulterr(self,msg,printout=True,color='failred'):
        self.debug(msg,traceback=2, color=TestColor.get_canned_color(color),linebyline=False)
    
    def get_pretty_args(self,testunit):
        buf =  "End on Failure :" +str(testunit.eof)
        buf += "\nPassing ARGS:\n"
        buf += "---------------------\n"
        varnames = self.get_meth_kwarg_names(testunit.method)
        if testunit.args:
            for count,arg in enumerate(testunit.args):
                buf += str(varnames[count+1])+" : "+str(arg)+"\n"
        if testunit.kwargs:
            for key in testunit.kwargs:
                buf += str(key)+" : "+str(testunit.kwargs[key])+"\n"
            buf += "---------------------\n"
        return buf
    
    def run_test_case_list(self, list, eof=True, clean_on_exit=True, printresults=True):
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
        exitcode = 0
        self.testlist = list 
        start = time.time()
        tests_ran=0
        test_count = len(list)
        try:
            for test in list:
                tests_ran += 1
                startbuf = ""
                argbuf =self.get_pretty_args(test)
                startbuf += str(test.description)+str(argbuf)
                startbuf += 'Running list method: "'+str(test.name)+'"'
                self.startmsg(startbuf)
                try:
                    test.run()
                    self.endsuccess(str(test.name))
                except Exception, e:
                    exitcode = 1
                    self.debug('Testcase:'+ str(test.name)+' error:'+str(e))
                    if eof or (not eof and test.eof):
                        self.endfailure(str(test.name))
                        raise e
                    else:
                        self.endfailure(str(test.name))
                        
        finally:
            elapsed = int(time.time()-start)
            msgout =  "RUN TEST CASE LIST DONE:\n"
            msgout += "Ran "+str(tests_ran)+"/"+str(test_count)+" tests in "+str(elapsed)+" seconds\n"
            self.status(msgout)
            if printresults:
                try:
                    self.print_test_list_results(list=list)
                except:pass
            try:
                 if clean_on_exit:
                    self.clean_method()
            except: pass
            
        return exitcode
    
    def has_arg(self,arg):
        arg = str(arg)
        if hasattr(self,'args'):
            if arg in self.args:
                return True
        return False
         
    def get_arg(self,arg):
        if self.has_arg(arg):
            return getattr(self.args,str(arg))
        return None
    
    def add_arg(self,arg,value):
        if self.has_arg(arg):
            raise Exception("Arg"+str(arg)+'already exists in args')
        else:
            self.args.__setattr__(arg,value)
    
    def set_arg(self,arg, value):
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
        self.debug("Implement this method")

    def print_test_list_results(self,list=None,printmethod=None):
        '''
        Description: Prints a formated list of results for a list of EutesterTestUnits
        
        :type list: list
        :param list: list of EutesterTestUnits
        
        :type printmethod: method
        :param printmethod: method to use for printing test result output. Default is self.debug
        '''
        if list is None:
            list=self.testlist
            
        if not printmethod:
            printbuf=True
            printmethod = self.resultdefault
            printfailure = self.resultfail
            printerr = self.resulterr
        else:
            printfailure = printerr = printmethod
            
        if printbuf :
            for testcase in list:
                buf =  ""
                buf += '-----------------------------------------------'
                pmethod = printfailure if not testcase.result == EutesterTestResult.passed else printmethod
                buf +=  pmethod(str("TEST:"+str(testcase.name)).ljust(50)+str(" RESULT:"+testcase.result).ljust(10)+str(' Time:'+str(testcase.time_to_run)).ljust(0),printout=False)
                if testcase.result == EutesterTestResult.failed:
                        buf += printerr('Error:'+str(testcase.error), printout=False)
        else:
            for testcase in list:           
                printmethod('-----------------------------------------------')
                pmethod = printfailure if not testcase.result == EutesterTestResult.passed else printmethod
                pmethod(str("TEST:"+str(testcase.name)).ljust(50)+str(" RESULT:"+testcase.result).ljust(10)+str(' Time:'+str(testcase.time_to_run)).ljust(0))
                if testcase.result == EutesterTestResult.failed:
                    printerr('Error:'+str(testcase.error))
    
    
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
        
        
        
    
    def create_testunit_by_name(self, name, obj=None, eof=False, autoarg=True, *args,**kwargs ):
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
        obj = obj or self
        meth = getattr(obj,name)
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
        
        
        if self.use_default_file and self.default_config:
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
        self.show_self()
        return args
    
        
    
    def get_default_userhome_config(self,fname='eutester.conf'):
        '''
        Description: Attempts to fetch the file 'fname' from the current user's home dir. 
        Returns path to the user's home dir default eutester config file. 
        
        :type fname: string
        :param fname: the eutester default config file name
        
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
        args= args or self.args if hasattr(self,'args') else None
        argbuf = str("TEST ARGS:").ljust(25)+"        "+str("VALUE:")
        argbuf += str("\n----------").ljust(25)+"        "+str("------")
        if args:
            for val in args._get_kwargs():
                argbuf += '\n'+str(val[0]).ljust(25)+" --->:  "+str(val[1])
            self.status(argbuf)
            
    
    def populate_testunit_with_args(self,testunit,namespace=None):
        self.debug("Attempting to populate testunit:"+str(testunit.name)+", with testcase.args...")
        args_to_apply = namespace or self.args
    
        testunit_obj_args =  copy.copy(testunit.kwargs)
        self.debug("Testunit keyword args:"+str(testunit_obj_args))
        
        #Get all the var names of the underlying method the testunit is wrapping
        method_args = self.get_meth_arg_names(testunit.method)
        self.debug("Got method args:"+str(method_args))
       
            
        #Add the var names of the positional args provided in testunit.args to check against later
        #Append to the known keyword arg list
        for x,arg in enumerate(testunit.args):
            testunit_obj_args.append([method_args[x+1]])
        
        self.debug("test unit toal args:"+str(testunit_obj_args))
        #populate any global args which do not conflict with args already contained within the test case
        #first populate matching method args with our global testcase args taking least precedence
        for apply_val in args_to_apply._get_kwargs():
            for methvar in method_args:
                if methvar == apply_val[0]:
                    self.debug("Found matching arg for:"+str(methvar))
                    #Don't overwrite existing testunit args/kwargs that have already been assigned
                    if apply_val[0] in testunit_obj_args:
                            self.debug("Skipping populate because testunit already has this arg:"+str(methvar))
                            break
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
        
        
    def get_method_fcode(self, meth):
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
    
    def get_meth_arg_names(self,meth):
        fcode = self.get_method_fcode(meth)
        varnames = fcode.co_varnames[0:fcode.co_argcount]
        return varnames
    
    def get_meth_kwarg_names(self,meth):
        return self.get_meth_arg_names(meth)
        '''
        fcode = self.get_method_fcode(meth)
        varnames = fcode.co_varnames[fcode.co_argcount:len(fcode.co_varnames)]
        return varnames
        '''
    def get_meth_varnames(self,meth):
        fcode = self.get_method_fcode(meth)
        return fcode.co_varnames
        

        
            
    
