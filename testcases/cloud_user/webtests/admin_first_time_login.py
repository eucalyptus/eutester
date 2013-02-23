'''
Created on Mar 2, 2012

@author: clarkmatthew
'''


import unittest
import time
from eucaweb import Eucaweb
from eucaweb import euwebuser
import eulogger



class AdminFirstTimeLogin(unittest.TestCase):
    def setUp(self):
        self.gui = Eucaweb(configFile='../input/2b_tested.lst', clcpasswd='foobar')
        self.admin = euwebuser.Euwebuser(user="admin", account="eucalyptus", passwd="admin")
        self.wg = self.gui.wg
        
        self.logger = eulogger.Eulogger(name= "user_first_time_login")
        
        self.debug = self.logger.log.debug
        self.critical = self.logger.log.critical
        self.info = self.logger.log.info 
        
    def test_admin_first_time_login(self):
        newuser = self.admin
        gui = self.gui
        try:       
            newuser.printUser()
            #gui.driverRestart()
            gui.goLoginPage()
            try:
                gui.login(newuser.account,newuser.user, newuser.passwd )
            except:
                try: 
                    self.gui.waitForTextOnPage('Login failed')
                except:
                    self.debug("First time Log in went to pop up instead, good")
                    gui.userFirstTimeLogin(newuser.email, newuser.passwd, newpass='foobar')
                
                    self.debug("Entered out form now checking page to see if we logged in correctly")
                    gui.verifyUserLinkPresent(newuser.user, newuser.account)
                    self.debug("First time login for ("+newuser.user+") succeeded")
                else:
                    self.fail("Initial password:"+newuser.passwd+" was rejected")
            else:
                self.fail("Initial Login succeeded without popup, was this really the first time?")
        except Exception, e:
            self.fail("test_admin_first_time_login failed:"+str(e))
            
    def test_blanktest(self):
        self.debug("Running a blank test")
        
    def tearDown(self):
        self.debug("Tearing down...")
        self.gui.tearDown(0)
        
if __name__ == "__main__":
    now = time.time()
    unittest.main()
    elapsed = now - time.time()
    print "Time to execute:"+str(elapsed)
        

        