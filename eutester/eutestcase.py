
import unittest
import inspect
import time
import gc
import argparse

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
    
    
    
class EutesterTestCase(unittest.TestCase):
    '''
    Convenience class to run wrap individual methods, and run and store and access results.
    '''
    def __init__(self,method, eof=True, *args):
        self.method = method
        self.args = args
        self.name = str(method.__name__)
        self.result=EutesterTestResult.not_run
        self.time_to_run=0
        self.eof=True
        self.error = ""
    
    def create_testcase_from_method(self,method, *args):
        testcase =  EutesterTestCase(method, args)
        return testcase
    
    def run(self):
        try:
            start = time.time()
            if (self.args) == ((),):
                ret = self.method()
            else:
                ret = self.method(*self.args)
            self.result=EutesterTestResult.passed
            return ret
        except Exception, e:
            self.error = str(e)
            self.result = EutesterTestResult.failed
            if self.eof:
                raise e
            else:
                pass
        finally:
            self.time_to_run = int(time.time()-start)

    def debug(self,msg,traceback=1):
        msg = str(msg)       
        curframe = None
        '''
        for x in xrange(0,100):
            frame = inspect.currentframe(x)
            print "trying frame["+str(x)+"]"
            if frame.f_back is None:
                print "this frame is none, will use frame["+str(x-1)+"] instead"
                break
            else:
                curframe = frame
                lineno = curframe.f_lineno
        '''
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
            
            
    def status(self,msg,traceback=2, b=0,a=0):
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
        
    
    def run_test_case_list(self, list, eof=True, clean_on_exit=True, printresults=True):
        '''
        wrapper to execute a list of ebsTestCase objects
        '''
        try:
            for test in list:
                self.debug('Running list method:'+str(test.name))
                try:
                    test.run()
                except Exception, e:
                    self.debug('Testcase:'+ str(test.name)+' error:'+str(e))
                    if eof:
                        raise e
                    else:
                        pass
        finally:
            try:
                 if clean_on_exit:
                    self.clean_created_resources()
            except: pass
            if printresults:
                try:
                    self.print_test_list_results()
                except:pass
    
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
    