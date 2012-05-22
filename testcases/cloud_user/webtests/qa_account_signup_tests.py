'''
Created on Nov 11, 2011

@author: clarkmatthew

Test Case qa 26 Account Signup:
        Sign up a new account from the initial page of the WebGUI using the "Sign up Account" button on the top right. Make sure:
            a:New account is created and can not be accessed until approval by sys euadmin.
            b:System euadmin receives the notification. 
            c:System euadmin can approve or reject the application.
             c-a:approve
             c-b:reject
            d:The approval/rejection notification is received by the new account owner.
            e:If approved, the new account owner can confirm the new account and login.
            f:If rejected, the new account is deleted.
            g:Cancel goes back to login page
            
Test Case qa 27 Account Sign up Error cases:
            a: Signup using an already existed account name should show error message.
            b: Invalid account names.
            c: Invalid email addresses.
            d: Cancel goes back to login page
            
Test Case qa 28 Password reset
            a:The user receive password reset notification.
            b:The user can reset password using the link in the email.
            c:The user can login with new password.
            d:User cannot login with old password

Test Case qa 29 Login
            a: Any valid user can login with correct account, user and password.
            b: Any invalid user can not login.
            c: Stay signed in should work. (Do we enforce a timeout?)
            d: Disabled user can not login
            e: Re-enabling a user allows it to login again
            



'''


from eucaweb import Eucaweb
from eucaweb import euwebuser, euwebaccount, euwebglobals
import time, sys,random
import unittest


"""#globals
 
self.wg = euwebglobals.Webui_globals()

admin = euwebuser.Euwebuser(user="admin",account="eucalyptus",email='matt.clark@eucalyptus',passwd="eucaman")
admin.printUser()

acceptuser = euwebuser.Euwebuser(prefix="accept",user="admin")
acceptuser.printUser()

origpassword = acceptuser.passwd


rejectuser = euwebuser.Euwebuser(prefix="reject", user="admin")
rejectuser.printUser()  

canceluser = euwebuser.Euwebuser(prefix="cancel", user="admin")
canceluser.printUser()

newuser = euwebuser.Euwebuser(prefix="newuser")
newuser.printUser()

gui = eucawebdriver.Euguid()
"""

class Qa_Account_SignUp_Tests(unittest.TestCase):

    def __init__(self, 
                 eucagui=None, #eucawebdriver object
                 euadmin=None, #euwebuser object
                 acctadmin=None, #euwebuser object
                 rejectuser=None, #euwebuser object
                 newuser=None, #euwebuser object
                 results=[]): #buffer for results summary
        if (eucagui is None):
            print "qa_29: euca webdriver is null at init"
            self.gui = Eucaweb()
            self.wg = self.gui.wg
        else:
            self.gui = eucagui
            self.wg = eucagui.wg
            
        self.rejectuser = rejectuser    
        self.euadmin = euadmin
        self.newacctadmin =  acctadmin
        self.origpassword = self.newacctadmin.passwd
        if (newuser is not None):
            self.newuser = newuser
        else:
            #create a random user which should fail
            self.newuser = euwebuser.Euwebuser()
        self.results = results
    
    #a:New account is created and can not be accessed until approval by sys euadmin.    
    def timeCount(self,timeout):
        for i in range(timeout):
            print i 
            time.sleep(1)
        
        
    def test_26a_signup_users(self, newacctadmin, rejectuser):    
        print("Starting test A:")    
        #sign up a user...
        try:  
            gui = self.gui
            #start our gui session
            
            #at login page sign up two users to apply for accounts to be used later
            gui.driver.implicitly_wait(30)
            gui.goLoginPage()
            gui.signUpUser(newacctadmin.account, newacctadmin.user, newacctadmin.passwd, newacctadmin.email)
            time.sleep(5)
            gui.signUpUser(rejectuser.account, rejectuser.user, rejectuser.passwd, rejectuser.email)
            print("signup portion looks good, now try logging in prior to account acceptance...")
        except Exception, e:
            print("Caught Error while signing up user:" + str(e))
            gui.driverRestart()
            raise e
        finally:
            gui.driver.implicitly_wait(30)
            
    def test_26a_verify_login_fails(self, newacctadmin): 
        #try to log in, but expect this to fail 
        try:
            gui= self.gui
            gui.driverRestart()
            gui.goLoginPage()
            gui.driver.implicitly_wait(4)
            gui.login(newacctadmin.account, newacctadmin.user, newacctadmin.passwd)
            print("This should have failed!")
        except Exception:
            sys.exc_clear() #clear the current exception
            #This is good
            print("---This is Good, We Expected failure on login here!----")
            pass # continue on
        else:
            raise Exception("Login succeeded where it should have failed")
        finally:
            gui.driver.implicitly_wait(10)
           
     
        
            
    #b:System euadmin receives the notification.
    def test_26b_system_admin_rx_email(self):     
        print("This test is not yet implemented need to confirm email,etc.. (manually for now)")
    
    
    #c:System euadmin can approve or reject the application.
    #f:If rejected, the new account is deleted
    def test_26c_check_accept_user_in_list_registered(self,euadmin, newacctadmin):
        try:
            gui = self.gui
            gui.driver.implicitly_wait(10)
            gui.driverRestart()
            #re user accept user from test a first...
            gui.login(euadmin.account,euadmin.user,euadmin.passwd)
            print('Logged in for test c, now find account')
            account = euwebaccount.Euwebaccount()#new acocunt
            account = gui.getAccountByName(newacctadmin.account)#assign it to our newacctadmin from above
            if (account.status != self.wg.StatusRegistered):
                print("Account ("+account.name+")was not in Registered state!")
                raise Exception("test_c failed, account was not in registered state")
            
        except Exception, e:
            print("test_c_check_accept_user_present_and_registered Failed:\n\t" +str(e))
            time.sleep(10)
            raise e
        
    def test_26c_search_accept_user_verify_registered(self, euadmin, newacctadmin):
            gui = self.gui
            gui.driverRestart()
            gui.login(euadmin.account, euadmin.user, euadmin.passwd)
            #bring this user into focus on accounts page, use search due to selenium bug in
            #the case the table element is not visible (but says it is)
            gui.searchForElementByUrl( self.wg.urlSearchAccountByName+newacctadmin.account)
            print "Click on the account to bring into focus"
            gui.clickButtonXpathAndVerify(self.wg.xAccountsRow1Id,self.wg.rightNavTxt)           
            status = str(gui.getRightNavValueByName(self.wg.AccountsRightNav_RegStatus))
            if (status != self.wg.StatusRegistered):
                print("Account ("+newacctadmin.account+")was not in Registered state!:"+str(status))
                time.sleep(20)
                raise Exception("test_c failed, account was not in registered state")
            
    
        
        
    def test_26c_approve_accept_user(self, euadmin, newacctadmin):
        try:    
            gui = self.gui
            gui.driverRestart()
            gui.login(euadmin.account, euadmin.user, euadmin.passwd)
            #bring this user into focus on accounts page, use search due to selenium bug in
            #the case the table element is not visible (but says it is)
            gui.searchForElementByUrl( self.wg.urlSearchAccountByName+newacctadmin.account)
            print "Click on the account to bring into focus, and then approve..."
            gui.clickButtonXpathAndVerify(self.wg.xAccountsRow1Id,self.wg.rightNavTxt)
            gui.clickAndApproveAccount(True,True)
            gui.driver.refresh()
        except Exception, e:
            time.sleep(20)
            raise Exception("test_c_approve_accept_user Failed:"+str(e))
        
    def test_26c_verify_accept_user_is_approved(self, euadmin, newacctadmin):
        try:
            gui = self.gui
            gui.driverRestart()
            print "\n\n\n\n\n\n\n\n\n\n\nVerify user is approved now..."
            time.sleep(5)
            
            gui.login(euadmin.account,euadmin.user,euadmin.passwd)
            print "\n\nAdmin is now logged in"
            #bring this user into focus on accounts page, since we refresh in the approve state we'll need to find the user again
            #gui.searchForElementByUrl( self.wg.urlSearchAccountByName+newacctadmin.account)
            url = str(self.wg.urlSearchAccountByName+newacctadmin.account)
            print "Our search url is:"+url
            gui.searchForElementByUrl( self.wg.urlSearchAccountByName+newacctadmin.account)    
            print "\n\nWe should be on our user page after search now?"
            print "wait and then click to bring into focus..."
            time.sleep(5)
            gui.clickButtonXpathAndVerify(self.wg.xAccountsRow1Id,self.wg.rightNavTxt)
            print "\n\nUser should be in focus now..., check right nav status"
            time.sleep(5)
            #check the status in the right nav to see if it shows the correct approved state
            status = str(gui.getRightNavValueByName(self.wg.AccountsRightNav_RegStatus))
            print "Got our status from right nav:"+status
            if (status != self.wg.StatusApproved):
                raise Exception("Status in right nav is not"+self.wg.StatusApproved)
            print "Accept User is approved-PASS"
        except Exception, e:
            print("test_c_verify_accept_user_is_approved Failed:\n\t" +str(e))
            print "Holding Browser open for a delayed period..."
            time.sleep(200)
            raise e
    
    def test_26c_confirm_accept_via_email_link(self, newacctadmin, euadmin):
        try:
            gui = self.gui
            print "\n\n\n\n\n\nnow see if the email was sent and grab the link..."
            time.sleep(5) #sleep just to give this time just in case...
            gui.confirmAccount(newacctadmin.account)
            print "User should now be confirmed verify accounts page reflects this..."
            gui.driverRestart()      
            gui.login(euadmin.account,euadmin.user,euadmin.passwd)
            print('Logged in to verify account shows confirmed, now find account')
            gui.searchForElementByUrl( self.wg.urlSearchAccountByName+newacctadmin.account)
            time.sleep(1)
            gui.clickButtonXpathAndVerify(self.wg.xAccountsRow1Id,self.wg.rightNavTxt)
            status = str(gui.getRightNavValueByName(self.wg.AccountsRightNav_RegStatus))
            if (status != self.wg.StatusConfirmed):
                print("Account ("+newacctadmin.name+")was not in ("+str(self.wg.StatusConfirmed)+") state!")
                raise Exception("test_c failed, account was not in confirmed state")
        except Exception, e:
            print("test_c_confirm_accpet_via_email_link:\n\t" +str(e))
            print "Holding Browser open for a delayed period..."
            time.sleep(200)
            raise e   
        
            
    def test_26f_verify_reject_user_is_registered_by_list(self, euadmin, rejectuser):
        try:
            print "\n\n\n\n\n\n\n\nNow try rejected user"
            gui = self.gui
            gui.driverRestart()
            gui.login(euadmin.account,euadmin.user,euadmin.passwd)
            account = gui.getAccountByName(rejectuser.account)#assign it to our rejectuser from above
            if (account.status != self.wg.StatusRegistered):
                print("Account ("+account.name+")was not in Registered state!")
                raise Exception("test_c failed, account was not in registered state")
        except Exception, e:
                raise Exception("Failed to verify rejectuser reg status:"+str(e))
    
    def test_26f_search_reject_user_verify_registered(self, euadmin, rejectuser):
            gui = self.gui
            gui.driverRestart()
            gui.login(euadmin.account, euadmin.user, euadmin.passwd)
            #bring this user into focus on accounts page, use search due to selenium bug in
            #the case the table element is not visible (but says it is)
            gui.searchForElementByUrl( self.wg.urlSearchAccountByName+rejectuser.account)
            print "Click on the account to bring into focus"
            gui.clickButtonXpathAndVerify(self.wg.xAccountsRow1Id,self.wg.rightNavTxt)
            status = str(gui.getRightNavValueByName(self.wg.AccountsRightNav_RegStatus))
            if (status != self.wg.StatusRegistered):
                print("Account ("+rejectuser.account+")was not in Registered state!:"+str(status))
                time.sleep(20)
                raise Exception("test_c failed, account was not in registered state")
    
    
    
    def test_26f_reject_user_verify_is_deleted(self, euadmin, rejectuser):
        try:
            gui = self.gui
            gui.driverRestart()
            gui.login(euadmin.account, euadmin.user, euadmin.passwd)
            #bring this user into focus on accounts page
            gui.searchForElementByUrl( self.wg.urlSearchAccountByName+rejectuser.account)
            time.sleep(1)
            gui.clickButtonXpathAndVerify(self.wg.xAccountsRow1Id,self.wg.rightNavTxt)
            
            #click and reject account here
            gui.clickAndApproveAccount(False,True)
            gui.driver.refresh()
            #This account should be removed from the list, expect an exception when looking for it
            try:
                gui.searchForElementByUrl( self.wg.urlSearchAccountByName+rejectuser.account)
            except:
                print"Account has been removed search by url, good:"+rejectuser.account
            else:
                raise Exception("Account("+rejectuser.account+")was not removed list, fail")
            
            try:
                gui.getAccountByName(rejectuser.account)
            except:
                print"Account has been removed from list, good:"+rejectuser.account
            else:
                raise Exception("Account("+rejectuser.account+")was not removed list, fail")
    
        except Exception, e:
            print("Reject user test failed:\n\t" +str(e))
            time.sleep(200)
            raise e
     
            
    #d:The approval/rejection notification is received by the new account owner.
    def test_26d_approval_mail_rx(self):     
        print("This test is not yet implemented need to confirm email,etc.. (manually for now)")
        print("see test 26c for partial approval email check")
                
        
    #e:If approved, the new account owner can confirm the new account and login.
    def test_26e_confirmed_account_login(self, newacctadmin):
        try:
            gui = self.gui
            gui.goLoginPage()
            gui.login(newacctadmin.account, newacctadmin.user, newacctadmin.passwd)
            print "Accept user logged in after approval: good"
        except Exception, le:
            print "Failed to log in the accepted user after approval"
            raise le
        
    
            
    
    
    
    def test_27a_signup_existing_account(self, newacctadmin):
        print "\n\n\n\ntest_27a_signup_existing account..."
        gui = self.gui
        gui.driverRestart()
        gui.goLoginPage()
        try:
            gui.signUpUser(newacctadmin.account, newacctadmin.user, newacctadmin.passwd, newacctadmin.email,expect=self.wg.AccountSignUpError)
        except:
            raise Exception("Error signing up existing account:"+newacctadmin.account)
            
    def getBadChar(self):
        clist = ['#','$','@','!','^','&','*']
        clen = len(clist)
        badchar = clist[random.randint(0,clen)-1]
        return str(badchar)
    
    
    def test_27b_signup_invalid_account_name(self):
        gui = self.gui
        gui.driverRestart()
        gui.goLoginPage()
        badname="badname"+self.getBadChar()
        baduser = euwebuser.Euwebuser(account=badname)
        baduser.printUser()
        try:
            gui.signUpUser(baduser.account, baduser.user, baduser.passwd, baduser.email, expect=self.wg.AccountSignUpInvalidName)
        except Exception, e:
            raise Exception("Error signing up invalid account name("+baduser.account+")"+str(e))
        
    def test_27c_signup_invalid_account_email(self):
        gui = self.gui
        gui.driverRestart()
        gui.goLoginPage()
        bademail="bademail"
        baduser = euwebuser.Euwebuser(email=bademail)
        baduser.printUser()
        try:
            gui.signUpUser(baduser.account, baduser.user, baduser.passwd, baduser.email, expect=self.wg.AccountSignUpInvalidEmail)
        except Exception, e:
            raise Exception("Error signing up invalid account email("+baduser.email+")"+str(e))
    
    def test_27b_signup_invalid_account_passwd(self):
        gui = self.gui
        gui.driverRestart()
        gui.goLoginPage()    
        gui.driverRestart()
        gui.goLoginPage()
        shortpass="shrt"
        baduser = euwebuser.Euwebuser(passwd=shortpass)
        baduser.printUser()
        try:
            gui.signUpUser(baduser.account, baduser.user, baduser.passwd, baduser.email, expect=self.wg.AccountSignUpPassTooShort)
        except  Exception, e:
            raise Exception("No error found when signing up invalid account email("+baduser.email+")"+str(e))
        
    #g:Cancel goes back to login page
    def test_27d_cancel_goes_back_to_login_page(self):
        try:
            gui = self.gui
            gui.driverRestart()
            gui.goLoginPage()
            canceluser = euwebuser.Euwebuser()
            gui.signUpUser(canceluser.account, canceluser.user, canceluser.passwd, canceluser.email)
            gui.driver.find_element_by_link_text("Signup Account").click()
            gui.driver.find_element_by_link_text("Cancel").click()
            gui.waitForTextOnPage("Password")
        except Exception, ge:
            print "Cancel on signup user failed"
            raise ge
        
    
    def test_28ab_user_passwd_reset_request(self,user):
        try:
            gui = self.gui
            gui.driverRestart()
            gui.goLoginPage()
            gui.requestPasswordReset(user.user, user.account, user.email)
        except Exception, e:
            raise Exception("test_28a_user_passwd_reset_request failed:" +str(e))
    
    def test_28ab_user_passwd_reset_via_emailed_link(self,user):
        newpass = "newpass"
        try:
            gui = self.gui
            gui.driverRestart()
            gui.changePassword(user.user, user.account, newpass)
            user.passwd = newpass
        except Exception, e:
            raise Exception("test_28a_userpasswd_reset_via_email_link failed:" + str(e))
        
    def test_28c_login_using_new_password(self,user):
        try:
            gui = self.gui
            gui.driverRestart()
            gui.login(user.account, user.user, user.passwd)
        except Exception, e:
            raise Exception("test_28a_login_new_password failed:" +str(e))
        
    def test_28d_login_using_old_password(self,user):
        try:
            gui = self.gui
            gui.driverRestart()
            #login with the global password stored from above
            gui.login(user.account, user.user, self.origpassword)
        except:
            print "Login Failed, good"
        else:
            raise Exception("Log in succeeded using old password should have failed")  
    def test_tbd_remove_test_account(self,delacctname, euadmin):
        try: 
            gui = self.gui
            gui.driverRestart()
            gui.login(euadmin.account, euadmin.user, euadmin.passwd)
            gui.deleteAccount(delacctname)
            print "Account ("+delacctname+") deleted"
        except Exception, e:
            raise Exception("test_tbd_remove_test_account failed:" +str(e) )
        
    """    
    def testCase(results, method, *args):
        name = method.__name__
        tstr = "TESTCASE("+name+")"
        print "\n\n\n\n\n\n\n\n\n\n\nRunning " + tstr
        time.sleep(10)
        try: 
            method(*args)
            print  tstr+": PASSED"
            results.append((tstr," PASSED", ""))
        except Exception, e:
            reason = str(e)
            print tstr+": FAILED:" +reason
            results.append((tstr," FAILED", reason))
    
    def printResults(results):
        print "\n\n\n"
        for test in results:
            name,res,reason = test
            print '{0:25} ==> {1:6}:{2}'.format(name,res,reason)
            #print  "Test:"+str(name)," :"+str(res)+" :"+reason
    """    
    
    def runAllTests(self,tests,newacctadmin, rejectuser, euadmin):
        self.wg.testCase(tests,self.test_26a_signup_users,newacctadmin, rejectuser)
        self.wg.testCase(tests,self.test_26a_verify_login_fails,newacctadmin)
        self.wg.testCase(tests,self.test_26b_system_admin_rx_email)
        #tests c
        self.wg.testCase(tests, self.test_26c_check_accept_user_in_list_registered, euadmin,newacctadmin)
        self.wg.testCase(tests, self.test_26c_search_accept_user_verify_registered,euadmin,newacctadmin)
        self.wg.testCase(tests, self.test_26c_approve_accept_user,euadmin,newacctadmin)
        self.wg.testCase(tests, self.test_26c_verify_accept_user_is_approved,euadmin,newacctadmin)
        self.wg.testCase(tests, self.test_26c_confirm_accept_via_email_link,newacctadmin,euadmin)
        self.wg.testCase(tests, self.test_26d_approval_mail_rx)
        self.wg.testCase(tests, self.test_26e_confirmed_account_login,newacctadmin)   
        self.wg.testCase(tests, self.test_26f_verify_reject_user_is_registered_by_list,euadmin,rejectuser)
        self.wg.testCase(tests, self.test_26f_search_reject_user_verify_registered,euadmin,rejectuser)
        self.wg.testCase(tests, self.test_26f_reject_user_verify_is_deleted,euadmin,rejectuser)
        #negative tests
        self.wg.testCase(tests, self.test_27a_signup_existing_account, newacctadmin) 
        #invalid sign up fields
        self.wg.testCase(tests, self.test_27b_signup_invalid_account_name)
        self.wg.testCase(tests, self.test_27b_signup_invalid_account_passwd)
        self.wg.testCase(tests, self.test_27c_signup_invalid_account_email)
        self.wg.testCase(tests, self.test_27d_cancel_goes_back_to_login_page)
        
        #password reset tests
        self.wg.testCase(tests, self.test_28ab_user_passwd_reset_request, newacctadmin)
        self.wg.testCase(tests, self.test_28ab_user_passwd_reset_via_emailed_link, newacctadmin)
        self.wg.testCase(tests, self.test_28c_login_using_new_password, newacctadmin)
        self.wg.testCase(tests, self.test_28d_login_using_old_password, newacctadmin)
    
        
        def printResults(self,results):
            self.wg.printResults(results)



    

