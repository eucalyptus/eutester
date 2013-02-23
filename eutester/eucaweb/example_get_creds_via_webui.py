'''
Created on Nov 16, 2011
@author: clarkmatthew



Simple Example script using the eutester web ui classes.

The intention of this script is to download and unzip credentials to a given file by 
interacting with the webui. 

-First a Eucaweb object is created which gives us a selenium interface to work with. 
In this case we do not need a eutester connection to  interact with the cloud outside the webui. 

-A euwebuser is created  with an account name, user name, and password. 
There are webmethods to create new users, but in this script we expect this user
already exists and has previously logged into the webui. 

-To simply access to predefined xpath variables, a euwebglobals object is created. 

-The script navigates to the webui login page, the user logs in, and downloads credentials to a given filename. 

'''


from eucaweb import Eucaweb, euwebuser, euwebaccount,euwebglobals, webtestcase
import time


    
    
def testrun():
    

        #New User to be added username will be randomly generated account is derived from acctadmin above
        user = euwebuser.Euwebuser(passwd="password", account="eucalyptus", user="admin")
        user.printUser()

        wg = euwebglobals.Webui_globals()
        

        #gui = eucawebdriver.Euguid(host="localhost",browser="FIREFOX",clc="192.168.51.9",needEutester=False)
        gui.goLoginPage()
        gui.login(user.account, user.user, user.passwd)
        time.sleep(5)
        gui.downloadCredentials(user.user, user.account, timeout=10, callBackMethod = testMethod, force = False)
     
        time.sleep(30)
        
        gui.tearDown(0)
        

def testMethod(filename):
    creddir= '/tmp/credentialtests'
    print "this is our test method we got filename("+filename+")"
    gui.unzipCredentialsToDir(filename, creddir)
    gui.sourceEucarcFromDir(creddir)
    
    
    
    

if __name__ == '__main__':
    gui = Eucaweb(host="localhost",browser="FIREFOX",clc="192.168.51.9",needEutester=False)
    testrun()
    print "this test is done"
        