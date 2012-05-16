'''
Created on Nov 21, 2011

@author: clarkmatthew
'''
from eucaweb import Eucaweb, euwebuser 
import time
import qa_account_signup_tests
import qa_login_tests
import qa_add_user_tests


#init globals 

#eucalyptus system admin
euadmin = euwebuser.Euwebuser(account="eucalyptus", user = "admin", passwd = 'foobar')
euadmin.printUser()

##############################################################################
#account admin, this users  randomly generated
acctadmin = euwebuser.Euwebuser(account="random", user="admin", passwd="password", prefix="good")
acctadmin.printUser()

#New User to be added username will be randomly generated account is derived from acctadmin above
newuser = euwebuser.Euwebuser(prefix="newuser", passwd="password", account=acctadmin.account, user="random")
newuser.printUser()

#a throw away user...
rejectuser = euwebuser.Euwebuser(prefix="bad", passwd="password")
newuser.printUser()

#gui = Eucaweb(host="localhost",browser="FIREFOX",clc="192.168.51.9")
gui = Eucaweb(host="localhost",browser="FIREFOX", configFile="2b_tested.lst",clcpasswd="foobar")
results = []

#################################################################################

#load up our tests...
accounttests= qa_account_signup_tests.Qa_Account_SignUp_Tests(eucagui=gui,newuser=newuser,acctadmin=acctadmin, euadmin=euadmin,results = results)
addusertest = qa_add_user_tests.Qa_Add_User_Tests(eucagui=gui, newuser=newuser, acctadmin = acctadmin, euadmin = euadmin, results = results)
logintest = qa_login_tests.Qa_29_Login_Tests( eucagui=gui,validuser = newuser, adminuser = euadmin, results = results)

#now run the tests...
print "Running initial account sign up tests..."
accounttests.runAllTests(results, acctadmin, rejectuser, euadmin)
gui.wg.printResults(results)
print "Running initial add users tests..."
addusertest.runAllTests(results, euadmin, newuser, acctadmin)
gui.wg.printResults(results)
print "now run login tests..."
logintest.runAllTests()
print "Removing users..."
try:
    #clean up
    accounttests.test_tbd_remove_test_account(newuser.account, euadmin)
    accounttests.test_tbd_remove_test_account(rejectuser.account, euadmin)
except Exception, e:
    print "error deleting user:" +str(e) 
    pass
finally:
    gui.wg.printClosing()
    gui.wg.printResults(results)
    print "tests complete, sleeping 60 and killing browser..."
    time.sleep(60)
    gui.tearDown(0)
    print "done"



    



