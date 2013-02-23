'''
Created on Nov 21, 2011

@author: clarkmatthew


Test Case qa 29 Login
            a: Any valid user can login with correct account, user and password.
            b: Any invalid user can not login.
            c: Stay signed in should work. (Do we enforce a timeout?)
            d: Disabled user can not login
            e: Re-enabling a user allows it to login again


'''

import unittest, time
from eucaweb import Eucaweb
from eucaweb import euwebuser, euwebglobals
#import time, sys,random
#globals

class Qa_29_Login_Tests(unittest.TestCase):
    def __init__(self, 
                 eucagui=None, #eucawebdriver object
                 adminuser=None, #euwebuser object
                 validuser=None, #euwebuser object
                 invaliduser=None, #euwebuser object
                 results=[]): #buffer for results summary
        if (eucagui is None):
            print "qa_29: euca webdriver is null at init"
        else:
            self.gui = eucagui
            self.wg = eucagui.wg
        self.user = validuser
        self.admin = adminuser
        if (invaliduser is not None):
            self.baduser = invaliduser
        else:
            #create a random user which should fail
            self.baduser = euwebuser.Euwebuser()
        self.results = results
        
        
        
        
    #login a valid user
    def qa_29_login_valid_user(self, user, expect=""):
        print "login valid user:"+str(user.user)
        print "using user:"
        user.printUser()
        try:    
            self.gui.driverRestart()
            self.gui.goLoginPage()
            self.gui.login(user.account, user.user, user.passwd)
        except Exception, e:
            raise Exception("qa_29_login_valid_user failed:"+str(e))
        
    #attempt to login an invalid user, expect exception
    def qa_29_login_invalid_user(self, user, expect=""):
        print "login invalid user:"+str(user.user)
        try:
            self.gui.driverRestart()
            self.gui.goLoginPage()
            self.gui.login(user.account, user.user, user.passwd)
        except:
            print("Invalid user failed to login:Pass")
        else:
            raise Exception("qa_29-Invalid user was able to login?")
    
    #login a valid user, navigate away from our site, return and verify
    def qa_29_verify_user_stays_signed_in(self,user,expect="",url=""):
        print "verify user stays logged in:" +str(user.user)
        if (url == ""):
            url = "www.eucalyptus.com"
        try:
            #first reset browser and login
            self.gui.driverRestart()
            self.gui.goLoginPage()
            self.gui.login(user.account, user.user, user.passwd)
            #now navigate away
            self.gui.driver.get(url)
            self.gui.driver.get("about:blank")
            self.gui.driver.get(self.gui.clcurl)
            #no verify that when returning to the home page the user specific link is present indicating they're still logged in
            self.gui.verifyUserLinkPresent(user.user, user.account)
        except Exception, e:
            raise Exception("qa_29 verify user stays logged in failed:"+str(e))
            
        
            
    def qa_29_verify_user_is_enabled(self,admin,user):
        print "verify user is enabled using:"
        print "account admin user:"
        admin.printUser()
        print "user to be enabled"
        user.printUser()
        
        try:
            #create an empty user
            testuser = euwebuser.Euwebuser(makerandom=False)
            self.gui.driverRestart()
            self.gui.goLoginPage()
            self.gui.login(admin.account, admin.user, admin.passwd)
            #search for user, should produce a table with only this user in it
            self.gui.searchForUser(user.user, user.account)
            #user should be the 1st and only row of the current table
            #get the states from the table row first
            testuser = self.gui.getUserRowValuesByXpath(self.wg.xUsersRow1)
            state = str(testuser.enabled)
            print "user enabled state from table: "+state
            if (state != self.wg.xUserEnabledTxt):
                raise Exception("qa29 verify user enabled-table state:"+state+"is not"+self.wg.xUserEnabledTxt)
            print "now check the right nav state, bring the user into focus first..."
            #user the testuser id to verify the button loads the page , now that we have the id value
            self.gui.clickButtonXpathAndVerify(self.wg.xUsersRow1Id, testuser.id)
            print "button is clicked, user should be highlighted"
            time.sleep(1)
            checkboxstate = self.gui.getRightNavValueByName(self.wg.UsersRightNav_Enabled)
            if (checkboxstate != "on"):
                raise Exception("qa29 verify user enabled-checkbox state:"+checkboxstate+"is not on")
            
        except Exception, e:
            raise Exception("qa_29 verify user is disabled failed:"+str(e))
        
        
    def qa_29_verify_disabling_an_enabled_user(self,admin,user):
        try:
            self.gui.driverRestart()
            self.gui.goLoginPage()
            self.gui.login(admin.account, admin.user, admin.passwd)
            self.gui.searchForUser(user.user, user.account)
            #user should be the 1st and only row of the current table
            #get the states from the table row first
            testuser = self.gui.getUserRowValuesByXpath(self.wg.xUsersRow1)
            state = str(testuser.enabled)
            if (state != self.wg.xUserEnabledTxt):
                raise Exception("qa_29_verify_disabling_an_enabled_user already disabled, state:"+state)
            #disable the user, this should do all the verifying for us
            self.gui.enableDisableUser(user.user, user.account, False)
        except Exception, e:
            raise Exception("qa_29 verify user is disabled failed:"+str(e))
        
        
    def qa_29_verify_disabled_user_cant_login(self, user):
        print "qa_29_verify_disabled_user_cant_login:\nUsing User:"
        user.printUser()
        try:
            self.gui.driverRestart()
            self.gui.goLoginPage()
            self.gui.login(user.account, user.user, user.passwd)
        except:
            print "verified disabled user can not login: pass"
        else:
            raise Exception("qa_29 disabled user was able to login:fail")
        
    def qa_29_verify_enabling_a_disabled_user(self,admin,user):
        print "qa_29_verify_enabling_a_disabled_user\nUsing users:"
        print "Adminuser:"
        admin.printUser()
        print "User:"
        user.printUser()
        try:
            self.gui.driverRestart()
            self.gui.goLoginPage()
            self.gui.login(admin.account, admin.user, admin.passwd)
            #disable the user, this should do all the verifying for us
            self.gui.enableDisableUser(user.user, user.account, True)
        except Exception, e:
            raise Exception("qa_29 verify user is disabled failed:"+str(e))
        
    def qa_29_verify_re_enabled_user_can_login(self,user):
        print "using user:"
        user.printUser()
        try:    
            self.gui.driverRestart()
            self.gui.goLoginPage()
            self.gui.login(user.account, user.user, user.passwd)
        except Exception, e:
            raise Exception("qa_29_login_re_enabled_user failed:"+str(e))
        
    def runAllTests(self,results=None, admin=None, user=None, baduser=None):
        if(results is None):
            results = self.results
        if (user is None):
            user = self.user
        if (baduser is None):
            baduser = self.baduser
        if (admin is None):
            admin = self.admin
        
        self.wg.testCase(results, self.qa_29_login_valid_user,  user)
        self.wg.testCase(results, self.qa_29_login_invalid_user, baduser)
        self.wg.testCase(results, self.qa_29_verify_user_stays_signed_in, user)
        self.wg.testCase(results, self.qa_29_verify_user_is_enabled, admin, user)
        self.wg.testCase(results, self.qa_29_verify_disabling_an_enabled_user, admin, user)
        self.wg.testCase(results, self.qa_29_verify_disabled_user_cant_login, user)
        self.wg.testCase(results, self.qa_29_verify_enabling_a_disabled_user, admin, user)
        self.wg.testCase(results, self.qa_29_verify_re_enabled_user_can_login, user)

    def printResults(self, results):
        self.wg.printResults(results)
        
        
