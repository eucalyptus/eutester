'''
Simple wrapper for tests
'''


import sys, unittest

# The Webtestcase class allows the user to run a basic test that
# displays info about the state of utilities. Results of the test
# will be shown as passed or failed.
class Webtestcase(unittest.TestCase):
    '''
    Simple test outline and utilities
    '''
    # Constructor for Webtestcase class
    def __init__(self, testMethod, name = "", dieOnError=True, logname="", *args):

	# Checks if the test method is identified. Then creates a 		# testcase object with the specified criteria for
	# testMethod, name, and dieOnError
        if (testMethod is None):
            raise Exception("Test Method must be defined")
        else:
            self.testMethod = testMethod
        if (name != ""):
            self.name = str(name)
        else:
            name = str(testMethod.__name__)
        self.dieOnError = dieOnError
        self.log = None
        self.logname = str(logname)
        self.savestdout = sys.stdout
        
        
        
    def redirectToFile(self,filename):
            self.log = open(filename, 'w')
            if (self.log is None):
                raise Exception("Could not create log file")
            sys.stdout =  self.log
            
            
        
    # Runs test and displays "passed" test passes or "failed" if test 	  # fails
    def runTest(self):
        try:
            print "TEST: "+self.name+ "STARTING..."
            if (self.logname != ""):    
                self.setupLog(self.logname)
            self.testMethod()
            print "TEST: "+self.name+" PASSED"
            self.printPassed()
        except Exception, e:
            print "TEST: "+self.name+ " FAILED"
            self.printFailed()
            if (self.dieOnError):
                self.printClosing()
                raise e
        finally:
            sys.stdout = self.savestdout
            
            
        
    
    # Methods for displaying test results     
    def printClosing(self):
        print "\n"
        print ''' 
     _____ _           _ 
    /  __ \ |         (_)
    | /  \/ | ___  ___ _ _ __   __ _ 
    | |   | |/ _ \/ __| | '_ \ / _` |
    | \__/\ | (_) \__ \ | | | | (_| |
     \____/_|\___/|___/_|_| |_|\__, |
                                __/ |
                               |___/ 
    
    '''
        print "\n"



    def printPassed(self):
        print "\n"
        print ''' 
    ______  ___  _____ _____ ___________  
    | ___ \/ _ \/  ___/  ___|  ___|  _  \ 
    | |_/ / /_\ \ `--.\ `--.| |__ | | | | 
    |  __/|  _  |`--. \`--. \  __|| | | | 
    | |   | | | /\__/ /\__/ / |___| |/ /  
    \_|   \_| |_|____/\____/\____/|___/   
    
    '''
        print "\n"
    
    
    def printFailed(self):
        print "\n"
        print '''
    ______ ___  _____ _      ___________ 
    |  ___/ _ \|_   _| |    |  ___|  _  \ 
    | |_ / /_\ \ | | | |    | |__ | | | | 
    |  _||  _  | | | | |    |  __|| | | | 
    | |  | | | |_| |_| |____| |___| |/ /  
    \_|  \_| |_/\___/\_____/\____/|___/  
                                         
    '''
        print "\n"
        
        
        
        
