
import unittest
import inspect
import time
import gc
import argparse
import re
import sys
import traceback

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
    
    
    
class EutesterTestUnit(unittest.TestCase):
    '''
    Description: Convenience class to run wrap individual methods, and run and store and access results.
    
    type method: method
    param method: The underlying method for this object to wrap, run and provide information on 
    
    type args: list of arguments
    param args: the arguments to be fed to the given 'method'
    
    type eof: boolean
    param eof: boolean to indicate whether a failure while running the given 'method' should end the test case exectution. 
    '''
    def __init__(self,method, eof=True, *args):
        self.method = method
        self.args = args
        self.name = str(method.__name__)
        self.result=EutesterTestResult.not_run
        self.time_to_run=0
        self.description=self.get_test_method_description()
        self.eof=True
        self.error = ""
    
    @classmethod
    def create_testcase_from_method(cls, method, *args):
        '''
        Description: Creates a EutesterTestUnit object from a method and set of arguments to be fed to that method
        
        type method: method
        param method: The underlying method for this object to wrap, run and provide information on
        
        type args: list of arguments
        param args: the arguments to be fed to the given 'method'
        '''
        testcase =  EutesterTestUnit(method, args)
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
        
        try:
            start = time.time()
            if (self.args) == ((),):
                ret = self.method()
            else:
                ret = self.method(*self.args)
            self.result=EutesterTestResult.passed
            return ret
        except Exception, e:
            traceback.print_exception(*sys.exc_info())
            self.error = str(e)
            self.result = EutesterTestResult.failed
            if self.eof:
                raise e
            else:
                pass
        finally:
            self.time_to_run = int(time.time()-start)

class EutesterTestCase(unittest.TestCase):

    def debug(self,msg,traceback=1):
        '''
        Description: Method for printing debug
        
        type msg: string
        param msg: Mandatory string buffer to be printed in debug message
        
        type traceback: integer
        param traceback: integer value for what frame to inspect to derive the originating method and method line number
        '''
        
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
            self.tester.debug("("+str(cur_method)+":"+str(lineno)+"): "+line.strip() )
            
            
    def create_testcase_from_method(self,method, *args):
        '''
        Description: Convenience method calling EutesterTestUnit. 
                     Creates a EutesterTestUnit object from a method and set of arguments to be fed to that method
        
        type method: method
        param method: The underlying method for this object to wrap, run and provide information on
        
        type args: list of arguments
        param args: the arguments to be fed to the given 'method'
        '''
        return EutesterTestUnit.create_testcase_from_method(method, *args)
        
    def status(self,msg,traceback=2, b=0,a=0):
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
        self.debug(out, traceback=traceback)  
        
    def startmsg(self,msg=""):
        msg = "- STARTING - " + msg
        self.status(msg, traceback=3)
        
    def endsuccess(self,msg=""):
        msg = "- SUCCESS ENDED - " + msg
        self.status(msg, traceback=3)
        self.debug("\n\n")
      
    def endfailure(self,msg=""):
        msg = "- FAILED - " + msg
        self.status(msg, traceback=3)
        self.debug("\n\n")  
    
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
        try:
            for test in list:
                self.startmsg(str(test.description))
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
                        pass
        finally:
            try:
                 if clean_on_exit:
                    self.clean_created_resources()
            except: pass
            if printresults:
                try:
                    self.print_test_list_results(list=list)
                except:pass
        return exitcode
                
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
        if printmethod is None:
            printmethod = self.debug
        for testcase in list:
            printmethod('-----------------------------------------------')
            printmethod(str("TEST:"+str(testcase.name)).ljust(50)+str(" RESULT:"+testcase.result).ljust(10)+str(' Time:'+str(testcase.time_to_run)).ljust(0))
            if testcase.result == EutesterTestResult.failed:
                printmethod('Error:'+str(testcase.error))
    
    @classmethod
    def get_parser(self):
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
    