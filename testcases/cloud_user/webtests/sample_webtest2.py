'''
Created on Nov 16, 2011

@author: clarkmatthew
'''


from eucaweb import Eucaweb, euwebuser, euwebaccount,euwebglobals, webtestcase
import time


    
    
def testrun():
    

        #New User to be added username will be randomly generated account is derived from acctadmin above
        user = euwebuser.Euwebuser(passwd="password", account="matt", user="admin")
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
        