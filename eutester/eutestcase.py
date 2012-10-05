
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
    #list of defined color schemes to add to
    whiteonblue='\33[1;37;44m'
    red='\033[m'
    failred='\033[101m'
    blueongrey='\33[1;34;47m'
    redongrey='\33[1;31;47m'
    blinkwhiteonred='\33[1;5;37;41m'
    
    reset = '\033[0m'  
    
    @classmethod
    def get_color_from_string(cls,color):
        try:
            return TestColor.__dict__[color]
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
        testcase =  EutesterTestUnit(method, args, kwargs)
        testcase.eof = eof
        return testcase
    
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
            print '{0}. {1}'.format(count, thing)
        for name, value in self.kwargs.items():
            print '{0} = {1}'.format(name, value)
        
        try:
            start = time.time()
            if not self.args:
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
            print TestColor.failred+buf+TestColor.reset
            self.error = str(e)
            self.result = EutesterTestResult.failed
            if self.eof:
                raise e
            else:
                pass
        finally:
            self.time_to_run = int(time.time()-start)
        
                
class EutesterTestCase():

    def __init__(self,name=None, debugmethod=None):
        self.name = name 
        if not self.name:
                callerfilename=inspect.getouterframes(inspect.currentframe())[1][1]
                self.name = os.path.splitext(os.path.basename(callerfilename))[0]  
                                   
    def setup_parser(self,
                   testname=None, 
                   description=None,
                   emi=True,
                   credpath=True,
                   password=True,
                   config=True,
                   configblocks=True,
                   ignoreblocks=True,
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
        :param emi: Flag to provide the emi command line argument/option for providing an image emi id
        
        :type credpath: boolean
        :param credpath: Flag to provide the credpath command line argument/option for providing a local path to creds
        
        :type password: boolean
        :param password: Flag to provide the password command line argument/option for providing password 
        used in establishing machine ssh sessions
        
        :type config: boolean
        :param config: Flag to provide the config file command line argument/option for providing path to config file
        
        :type configblocks: string list
        :param configblocks: Flag to provide the configblocks command line arg/option used to provide list of 
                             configuration blocks to read from
                             Note: By default if a config file is provided the script will only look for blocks; 'globals', and the filename of the script being run.
        
        :type ignoreblocks: string list
        :param ignoreblocks: Flag to provide the configblocks command line arg/option used to provide list of 
                             configuration blocks to ignore if present in configfile
                             Note: By default if a config file is provided the script will look for blocks; 'globals', and the filename of the script being run
 
        :type testlist: string list
        :param testlist: Flag to provide the testlist command line argument/option for providing a list of testnames to run
        '''
        testname = testname or self.name or 'TEST NAME'
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
            parser.add_argument('--ingnoreblocks', nargs='+',
                                help="Config blocks to ignore, ie:'globals', 'my_scripts_name', etc..", default=[])
        if testlist:
            parser.add_argument('--tests', nargs='+', 
                                help="test cases to be executed", default= ['run_test_suite'])   
        self.parser = parser  
        return parser
    
    def setup_debugmethod(self,name=None):
        try:
            self.debugmethod = self.tester.debug
        except:
            name = name or self.__class__.__name__
            logger = Eulogger(identifier=str(name))
            self.debugmethod = logger.log.debug

    def debug(self,msg,traceback=1,color=None):
        '''
        Description: Method for printing debug
        
        type msg: string
        param msg: Mandatory string buffer to be printed in debug message
        
        type traceback: integer
        param traceback: integer value for what frame to inspect to derive the originating method and method line number
        '''
        try:
            if not self.debugmethod:
                self.setup_debugmethod()
        except:
            self.setup_debugmethod()
            
        colorprefix=""
        colorreset=""
        if color:
            colorprefix = TestColor.get_color_from_string(color) or color
            colorreset = str(TestColor.reset)
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
        for line in msg.split("\n"):
            self.debugmethod("("+str(cur_method)+":"+str(lineno)+"): "+colorprefix+line.strip()+colorreset )
            
            
    def create_testcase_from_method(self,method,eof=False, *args, **kwargs):
        '''
        Description: Convenience method calling EutesterTestUnit. 
                     Creates a EutesterTestUnit object from a method and set of arguments to be fed to that method
        
        type method: method
        param method: The underlying method for this object to wrap, run and provide information on
        
        type args: list of arguments
        param args: the arguments to be fed to the given 'method'
        '''   
        testunit = EutesterTestUnit(method, *args, **kwargs).eof = eof
        testunit.eof = eof
        return testunit 
    
    def status(self,msg,traceback=2, b=0,a=0 ,testcolor=None):
        '''
        Description: Convenience method to format debug output
        
        type msg: string
        param msg: The string to be formated and printed via self.debug
        
        type traceback: integer
        param traceback: integer value for what frame to inspect to derive the originating method and method line number
        
        type b: integer
        param b:number of blank lines to print before msg
        
        type a: integer
        param a:number of blank lines to print after msg
        '''
        alines = ""
        blines = ""
        for x in xrange(0,b):
            blines=blines+"\n"
        for x in xrange(0,a):
            alines=alines+"\n"
        line = "-------------------------------------------------------------------------"
        out = blines+line+"\n"+msg+"\n"+line+alines
        self.debug(out, traceback=traceback, color=testcolor)  
        
    def startmsg(self,msg=""):
        msg = "- STARTING - " + msg
        self.status(msg, traceback=3,testcolor=TestColor.whiteonblue)
        
    def endsuccess(self,msg=""):
        msg = "- SUCCESS ENDED - " + msg
        self.status(msg, traceback=3,testcolor=TestColor.whiteonblue)
        self.debug("\n\n")
      
    def endfailure(self,msg=""):
        msg = "- FAILED - " + msg
        self.status(msg, traceback=3,testcolor=TestColor.failred)
        self.debug("\n\n")  
    
    def resultdefault(self,msg):
        self.debug(msg,traceback=2,color=TestColor.blueongrey)
    
    def resultfail(self,msg):
        self.debug(msg,traceback=2, color=TestColor.redongrey)
        
    def resulterr(self,msg):
        self.debug(msg,traceback=2, color=TestColor.failred)
    
    def get_pretty_args(self,testunit):
        buf = "End on Failure :" +str(testunit.eof)
        if testunit.args:
            for key in testunit.args:
                buf += "\n"+str(key)+" : "+str(testunit.args[key])
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
        '''
        exitcode = 0
        self.testlist = list 
        try:
            for test in list:
                argbuf =self.get_pretty_args(test)
                self.startmsg(str(test.description)+argbuf)
                self.debug('Running list method:'+str(test.name))
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
            self.status("RUN TEST CASE LIST DONE...")
            if printresults:
                try:
                    self.print_test_list_results(list=list)
                except:pass
            try:
                 if clean_on_exit:
                    self.clean_method()
            except: pass
            
        return exitcode
    
    def clean_method(self):
        self.debug("Implement this method")

    def print_test_list_results(self,list=None,printmethod=None):
        '''
        Description: Prints a formated list of results for a list of EutesterTestUnits
        
        type list: list
        param list: list of EutesterTestUnits
        
        type printmethod: method
        param printmethod: method to use for printing test result output. Default is self.debug
        '''
        if list is None:
            list=self.testlist
            
        if not printmethod:
            printmethod = self.resultdefault
            printfailure = self.resultfail
            printerr = self.resulterr
        else:
            printfailure = printerr = printmethod
           
        for testcase in list:           
            printmethod('-----------------------------------------------')
            pmethod = printfailure if not testcase.result == EutesterTestResult.passed else printmethod
            pmethod(str("TEST:"+str(testcase.name)).ljust(50)+str(" RESULT:"+testcase.result).ljust(10)+str(' Time:'+str(testcase.time_to_run)).ljust(0))
            if testcase.result == EutesterTestResult.failed:
                printerr('Error:'+str(testcase.error))
    
    #@classmethod
    def get_parser(self):
        '''
        Description: Convenience method used to create set of default argparse arguments
        Soon to be replaced by setup_parser()
        '''
        parser = argparse.ArgumentParser(prog="testcase.py",
                                     description="Test Case Default Option Parser")
        parser.add_argument('--emi', 
                            help="pre-installed emi id which to execute these tests against", default=None)
        parser.add_argument('--credpath', 
                            help="path to credentials", default=None)
        parser.add_argument('--password', 
                            help="password to use for machine root ssh access", default='foobar')
        parser.add_argument('--config',
                           help='path to config file', default='../input/2btested.lst')         
        parser.add_argument('--tests', nargs='+', 
                            help="test cases to be executed", 
                            default= ['run_test_suite'])
        return parser
    
    
    def run_method_by_name(self,name, obj=None,*args, **kwargs):
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
        return self.run_with_args(meth, *args, **kwargs)
        
        
        
    
    def create_testunit_by_name(self, name, obj=None, eof=False, *args,**kwargs):
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
        testunit = EutesterTestUnit(meth, eof=eof, *args, **kwargs)
        return testunit

        
    def get_args(self,sections=[]):
        '''
        Description: Method will attempt to retrieve all command line arguments presented through local 
        testcase's 'argparse' methods, as well as retrieve all EuConfig file arguments. All arguments 
        will be combined into a single namespace object held locally at 'testcase.args'. Note: cli arg 'config'
        must be provided for config file valus to be store in self.args. 
        
        :type sections: list
        :param sections: list of EuConfig sections to read configuration values from, and store in self.args.
        
        :rtype: arparse.namespace obj
        :returns: namespace object with values from cli and config file arguements 
        '''
        confblocks=['globals']
        if self.name:
            confblocks.append(self.name)
        if not self.parser:
            self.setup_parser()
        #first get command line args to see if there's a config file
        args = self.parser.parse_args()
        #if a config file was passed, combine the config file and command line args into a single namespace object
        if args and ('config' in args.__dict__) and  args.config:
            
            #Check to see if there's explicit config sections to read
            if 'configblocks' in args.__dict__:
                confblocks = confblocks +args.configblocks
            #Check to see if there's explicit config sections to ignore
            if 'ignoreblocks' in args.__dict__:
                for block in args.ignoreblocks:
                    if block in confblocks:
                        confblocks.remove(block)
            #build out a namespace object from the config file first
            cf = argparse.Namespace()
            conf = EuConfig(filename=args.config)
            #If globals are still in our confblocks, add globals first if the section is present in config
            if 'globals' in confblocks:
                if conf.config.has_section('globals'):
                    for item in conf.config.items('globals'):
                        cf.__setattr__(str(item[0]), item[1])
                    confblocks.remove('globals')
            #No iterate through remaining config block in file and add to args...
            for section in confblocks:
                if conf.config.has_section(section):
                    for item in conf.config.items(section):
                        cf.__setattr__(str(item[0]), item[1])
            #Now make sure any conflicting args provided on the command line take precedence over config file args
            for val in args._get_kwargs():
                cf.__setattr__(str(val[0]), val[1])
            args = cf
        #Legacy script support: level set var names for config_file vs configfile vs config and credpath vs cred_path
        try:
            args.config_file = args.config
            args.configfile = args.config
        except: pass
        try:
            args.cred_path = args.credpath
        except: pass
        self.args = args
        return args
        
    
    def run_with_args(self, meth, *args, **kwargs):
        '''
        Description: Convenience method used to wrap the provided method 'meth' and populate meth's positional 
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
        tc_args = self.args
        cmdargs={}
        vars = []
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
            raise Exception("create_with_args: Could not find varnames for passed method of type:"+str(type(meth)))
        vars = f_code.co_varnames
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
        
                    
            
            
    