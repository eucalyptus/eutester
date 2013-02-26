'''
Created on Nov 22, 2011

@author: clarkmatthew


Test Case qa TBD Add User to Account:
            a: Admin user can login and add a user to their account (verify the user is viewable to admin)
            b: Admin user can set password for the new user
            c: New User can login via new user path  (setting their own email, passwd, etc) and eventually login. 
            
'''
import unittest, time
from eucaweb import Eucaweb
from eucaweb import euwebuser, euwebglobals
#import time, sys,random
#globals

class Qa_Add_User_Tests(unittest.TestCase):
    def __init__(self, 
                 eucagui=None, #eucawebdriver object
                 euadmin=None, #euwebuser object
                 acctadmin=None, #euwebuser object
                 newuser=None, #euwebuser object
                 results=[]): #buffer for results summary
        if (eucagui is None):
            print "qa_29: euca webdriver is null at init"
            self.gui = Eucaweb()
            self.wg = self.gui.wg
        else:
            self.gui = eucagui
            self.wg = eucagui.wg
        self.euadmin = euadmin
        self.acctadmin = acctadmin
        if (newuser is not None):
            self.newuser = newuser
        else:
            #create a random user which should fail
            self.newuser = euwebuser.Euwebuser()
        self.results = results
        
    #a: Admin user can login and add a user to their account (verify the user is viewable to admin)
    def test_tbda_acct_admin_can_add_new_user(self, acctadmin,newuser):
        try:
            gui = self.gui
            gui.driverRestart()
            gui.goLoginPage()
            gui.login(acctadmin.account, acctadmin.user, acctadmin.passwd)
            gui.addUserToAccount(acctadmin.account, newuser.user)
        except Exception, e:
            raise Exception("test_tbda_acct_admin_can_add_new_user failed:"+str(e))
    
    
    #b: Admin user can set password for the new user
    def test_tbda_acct_admin_set_new_user_password(self,acctadmin,newuser):
        try:
            gui = self.gui
            gui.driverRestart()
            gui.goLoginPage()
            gui.login(acctadmin.account, acctadmin.user, acctadmin.passwd)
            gui.changeUserPassword(acctadmin.account, newuser.user, acctadmin.passwd, newuser.passwd)
        except Exception, e:
            raise Exception("test_tbda_acct_admin_set_new_user_password failed:"+str(e))
    
    #c: New User can login via new user path  (setting their own email, passwd, etc) and eventually login. 
    def test_tbda_newuser_verify_first_time_login(self,newuser):
        try:
            print "try first time login with user:"
            newuser.printUser()
            gui = self.gui
            gui.driverRestart()
            gui.goLoginPage()
            try:
                gui.login(newuser.account,newuser.user, newuser.passwd)
            except:
                print "First time Log in went to pop up instead, good"
                gui.userFirstTimeLogin(newuser.email, newuser.passwd, newuser.passwd, newuser.passwd)
                gui.verifyUserLinkPresent(newuser.user, newuser.account)
                print "First time login succeeded"
            else:
                raise Exception("Initial Login succeeded without popup?")
        except Exception, e:
            raise Exception("test_tbda_newuser_verify_first_time_login failed:"+str(e))
        
        
    def runAllTests(self,results=None, euadmin=None, newuser=None, acctadmin=None):
            if(results is None):
                results = self.results
            if (newuser is None):
                newuser = self.newuser
            if (acctadmin is None):
                acctadmin = self.acctadmin
            if (euadmin is None):
                euadmin = self.euadmin
            
            self.wg.testCase(results, self.test_tbda_acct_admin_can_add_new_user, acctadmin, newuser)
            self.wg.testCase(results, self.test_tbda_acct_admin_set_new_user_password,acctadmin, newuser)
            self.wg.testCase(results, self.test_tbda_newuser_verify_first_time_login, newuser)
            
            
    def printResults(self, results):
            self.wg.printResults(results)   
    
    
    
    
    
    
        