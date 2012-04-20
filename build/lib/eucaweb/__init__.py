'''
Created on Nov 10, 2011
@author: mclark
'''
#from eutester import Eutester
from eucaops import Eucaops
from selenium import webdriver
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
#from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import unittest, time, re, os, signal, commands
from subprocess import call
import euwebglobals, euwebaccount, euwebuser
import eulogger
#import string, random
#import sys, inspect



class Eucaweb(unittest.TestCase):   
    def __init__ (self, host="localhost",
                  browser="Firefox", 
                  clc="", 
                  user="admin", 
                  account="eucalyptus", 
                  adminpasswd="",
                  clcpasswd="", 
                  needEucaops=True,
                  downloadPath="/tmp/eucawebdriver",
                  configFile=""):
        
        self.images = []
        self.loggedIn = False
        self.host = host
        self.browser = str(browser).upper()
        self.clc = clc
        self.clcpasswd = clcpasswd
        self.clcurl = "https://"+clc+":8443/"
        self.user = user
        self.account = account
        self.passwd = adminpasswd
        self.defTimeout = 10
        self.configFile = configFile
        self.needEucaops = needEucaops
        self.errs = []
        self.downloadPath = downloadPath
        if (re.search('/$',self.downloadPath) ):
                self.downloadPath = self.downloadPath.rstrip('/')
        self.wg = euwebglobals.Webui_globals()
        self.setUp()
    
        
    def setUp(self):
        try:
            self.logger = eulogger.Eulogger(name='euca')
            self.log = self.logger.log
            self.printSelf()
            self.log.debug("setUp starting...")
            self.errs = []           
            self.startDriver()            
            if  (self.configFile == "" ):
                fpath = str(os.path.abspath( __file__ ))#get the abs path to file
                thisfile = re.search( '\w+.\w+.$', fpath).group(0) #get thisfile so we can remove it to get abs path
                fpath = str(os.path.abspath( __file__ )).replace(thisfile,"")
                self.configFile = str(fpath)+"2b_tested.lst"                 
            self.printSelf()    
           
            
            if (self.needEucaops):
                try:
                    retcode = call('rm -rf eucarc-*',shell=True)
                    print "removed a local eucarc =" + str(retcode)
                except Exception,e:
                    self.log.debug("couldn't delete the local eucarc")
                    pass
                    
                try:
                    self.eutester = Eucaops(hostname="clc", password=self.clcpasswd,config_file=self.configFile)
                    #self.eutester = Eutester(config_file=self.configFile, password=self.clcpasswd)
                except Exception, ute:
                    self.log.critical("failed to create eutester object within gui...!!:"+str(ute))
                    raise ute
            if (self.clc == ""):
                self.clc = self.eutester.get_clc_ip()
                self.clcurl = "https://"+self.clc+":8443/"
            self.driver.implicitly_wait(10)
            self.base_url = self.clcurl
            bname = self.driver.name
            self.log.debug("Found browser name:" + str(bname))
        except Exception, e:
            self.log.critical("Failed setup!!:\n"+ str(e))
            self.tearDown(0)
            raise e
        
    def startDriver(self):
        #dbg = self.log.debug
        try:
            self.log.critical("STarting driver!!!!!")
            if (self.browser == "FIREFOX" ):
                self.log.debug("using webdriver firefox, setting up custom profile...")
                ffprof = FirefoxProfile()
                #ffprof.accept_untrusted_certs("true")
                ffprof.set_preference("browser.download.folderList", 2)
                ffprof.set_preference("browser.download.dir",self.downloadPath)
                ffprof.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/zip") #to download credentials without "save as" dialog
                ffprof.set_preference("browser.download.manager.showWhenStarting", "false")
                self.driver = webdriver.Firefox(ffprof)
            elif (self.browser == "CHROME" ):
                self.log.debug("using webdriver chrome")
                self.driver = webdriver.Chrome()
            elif (self.browser == "IE" ):
                self.log.debug( "using webdriver IE" )
                self.driver = webdriver.Ie()
            else:
                self.driver = webdriver.Firefox()
        except Exception, de:
            self.log.critical("startDriver error:" + str(de))
            raise de
            
                
        
        
    def printSelf(self):
        self.log.debug( "++++++++++++++++++++++++++++++++++++++++++++++")
        self.log.debug( "configFile: " + str(self.configFile))
        self.log.debug( "host: " + str(self.host))
        self.log.debug( "browser: " + str(self.browser))
        self.log.debug( "clc: " + str(self.clc))
        self.log.debug( "clcpasswd:"+str(self.clcpasswd))
        self.log.debug( "user: " + str(self.user))
        self.log.debug( "account: " + str(self.account))
        self.log.debug( "password: " + str(self.passwd))
        self.log.debug( "needEucaops: " + str(self.needEucaops))
        self.log.debug( "xpathUserLink: " + self.wg.xUserLink)
        self.log.debug( "+++++++++++++++++++++++++++++++++++++++++++++++")
  

    def waitForText(self, xpath, text, retry):
        '''
        Will check current xpath for text supplied for a given number of times
        It appears the find_element_by_path also has a buitl in wait period. 
        This might be referencing the webdriver's "driver.implicitly_wait"value
        '''
        self.log.debug(self.hd("waitForText ("+ str(text) +") starting..."))
        driver = self.driver
     
        for i in range(retry):
            self.log.debug("retry count:"+str(i))
            try:
                cmd = xpath + "[contains(.,'" + text + "')]"
                self.log.debug("Looking for\""+text+"\" in xpath: "+ xpath)
                driver.find_element_by_xpath(cmd)
                self.log.debug("Found text\"" + text + "\" after " + str(i) + " retries")
                return 
                break
            except Exception, e:
                self.log.critical("Did nof find text on pass("+str(i)+":" + str(e))
                time.sleep(1)
                pass
        #else:   
        self.log.critical("Failed to find (" + text + ") after (" + str(retry) + ") tries in xpath (" + xpath + ")")
        raise Exception("Failed to find text("+text+")")
            
    def goLoginPage(self):
        self.log.debug(self.hd("goLoginPage"))
        driver = self.driver
        driver.get(self.clcurl)
        try:
            self.waitForTextOnPage("Password")
        except Exception, e:
            self.log.critical("Password text not found, err:"+ str(e))
            
    
        
    def get(self,url):
        return self.driver.get(url)
       
        
    def getElmByText(self, xpath, text):
        '''
        get web element in given xpath that contains the given text
        '''
        self.log.debug(self.hd("getElmByText:"+str(text)))
        driver = self.driver
        cmd = xpath + "[contains(.,'" + text + "')]"
        self.log.debug("Our xpath: "+ xpath) 
        elm = driver.find_element_by_xpath(cmd)
        self.log.debug("Found text(" + text + ")")
        return elm
    
    
    def hd(self,msg):
        '''
        format 'msg' into a debug header  
        '''
        myHdr = "<<<<( "+msg+" )>>>>"
        '''
        myHdr = "\n+++++++++++++++++++++++++++++++++++++++++++++++\n"    
        myHdr = myHdr+"    "+msg+"\n"
        myHdr = myHdr+"+++++++++++++++++++++++++++++++++++++++++++++++\n"
        '''    
        return myHdr
    
    def login(self,account,user,passwd):
        '''
        Log 'user' into 'account' using password 'passwd'
        '''
        account = str(account)
        user = str(user)
        passwd = str(passwd)
        self.log.debug(self.hd("login (account:"+account+" user:"+user+" passwd:"+passwd+")"))
        
        driver = self.driver
        driver.get(self.clcurl)
        driver.find_element_by_id("accountName").clear()
        driver.find_element_by_id("accountName").send_keys(str(account))
        driver.find_element_by_id("userName").clear()
        driver.find_element_by_id("userName").send_keys(str(user))
        driver.find_element_by_id("password").clear()
        driver.find_element_by_id("password").send_keys(str(passwd))
        driver.find_element_by_css_selector("input[type=\"submit\"]").click()
        # We should be logged in at this point,
        # verify by checking the user@account link at top of page...
        #if (self.verifyUserLinkPresent(user,account) == False):
        
        try:
            self.waitForTextOnPage(user+'@'+account, 3 )
            self.log.debug("USER:"+str(user)+" ACCOUNT:"+account+" LOGGED IN")
        except Exception, e:
            self.log.critical("Failed to verify user link for login (account:"+account+" user:" +user+" passwd:"+passwd+")")
            raise e
            
        
            
            
        
        
    #check entire page aka 
    def waitForTextOnPage(self,searchtext, retry=1):
        '''
        check entire page for a certain text string 'searchtext'
        retry 'retry' amount of times
        '''
        self.log.debug(self.hd("waitForTextOnPage starting, text:("+str(searchtext)+")"))
        xpath = '//*' #search whole page
        try:
            self.waitForText(xpath, searchtext, 1)
            self.log.debug("Found Text:"+ str(searchtext))    
        except Exception, e:
            self.log.debug("Failed to find text (" + searchtext + ")on page")
            raise e
        
    
    
    def verifyUserLinkPresent(self,username,accountname):
        '''
        Confirms the user specific link name@account is present on the page
        '''
        try:
            ltext = username+'@'+accountname
            self.log.debug(self.hd("verifyUserLink starting("+ltext+")..."))
            webelm = self.getUserLink()
            self.log.debug("Userlink elm:"+webelm.text)
            if (webelm.text == ltext):
                self.log.debug("Userlinks matched: ltext:"+ltext+" vs found:"+webelm.text)
            else:
                raise Exception("Userlinks did not match: ltext:"+ltext+" vs found:"+webelm.text)
        except Exception, e:
            self.log.critical("error Validating user link:" + str(e))
            
        
    
    def getUserLink(self,linkstring =""):
        '''
        get the link user@account link at top of page...
        '''
        self.log.debug(self.hd("getUserLink starting..."))
        driver = self.driver
        try:
            if (linkstring == "" ):
                #use xpath
                elm = driver.find_element_by_xpath(self.wg.xUserLink)
            else:
                #use the name@domain link string
                elm = driver.find_element_by_link_text(linkstring)
            self.log.debug("got elm for user link")
            return elm
        except Exception, e:
            self.log.critical("Failed to get User Link")
            raise e
        
        
    def downloadCredentials(self, username, accountname, timeout=60, force = False, callBackMethod=None):
        '''
        hack to temporarily simulate a user downloading creds
        note this will always attempt to download to the default dir setup when creating the webdriver instance
        will lock the directory until the method passed is executed on the file, note method will be passed the file name/path as the single arg
        hack work around to allow multiple instances of this test to run  at the same time
        '''
        try:
            driver = self.driver
            self.getUserLink().click()
            retcode = 0
            waitforlock = timeout
            mypid = str(os.getpid())
            mylockfile = self.downloadPath+'/lockfile'+str(mypid)
            #spin here wait for lockfile up to timeout
            while ((retcode == 0) and (waitforlock > 0)):
                retcode = call('ls '+self.downloadPath+' | grep -i lockfile',shell=True)
                if (retcode == 0):
                    self.log.debug("download dir is locked, waitforlock:"+str(waitforlock))
                time.sleep(1)
                waitforlock -= 1
            #check to see if we timed out or really go the go ahead
            if (retcode == 0):
                if (force):
                    self.log.critical("download dir was not empty after("+str(timeout)+")seconds, forcing removal...")
                    cmd = 'rm '+self.downloadPath+'/lockfile*'
                    self.log.critical("using cmd:"+cmd)
                    call(cmd,shell = True)
                    retcode = call('ls '+self.downloadPath+' | grep -i lockfile',shell=True)
                    if (retcode == 0):
                        raise Exception("download dir still not empty after force removal")
                else:
                    raise Exception("download dir:"+self.downloadPath+" was not empty after("+str(timeout)+") seconds")
            #create a lockfile in the download dir
            call("touch "+mylockfile, shell=True)
            #clear out the directory of previous zip files
            call("rm -f "+self.downloadPath+"/*.zip",shell=True)
            
            #now download the file via the webgui...
            driver.find_element_by_link_text("Download new credentials").click()
            #now check the local filesystem under the default dir to see if it was downloaded...
            downloaded = 1
            waitforfile = timeout
            #wait for the timeout period for the file to show up in our download dir...
            while ((downloaded == 1) and (waitforfile > 0)):
                downloaded = call('ls -la '+self.downloadPath+' | grep -i zip',shell=True)
                time.sleep(1)
                waitforfile -= 1
            if (downloaded == 1):
                raise Exception("File was not detected in("+self.downloadPath+", waitforfile:"+str(waitforfile))
            #get the file name since all we know so far is based on the assumption the file is named with a .zip extension... 
            filelist = os.listdir(self.downloadPath+"/")
            credfile = ""
            for f in filelist:
                if (re.search('zip$',f)):
                    credfile = self.downloadPath+"/"+f
                    self.log.debug("file found:"+str(credfile))
            if (credfile == ""):
                raise Exception("Failed to create the downloaded filename?")
            try:
                if (callBackMethod is not None):
                    callBackMethod(credfile)
            except Exception, cbe:
                raise Exception("Call back ("+str(callBackMethod.__name__)+") Failed: " +str(cbe))
        except Exception, e:
            self.log.debug("downloadCredentials failed:" + str(e))
        finally:
            try:
                self.log.debug("Removing file: "+credfile)
                os.remove(credfile)
            except Exception, rme:
                self.log.debug("Exception caught removing files:" + str(rme))
                pass
            try: 
                self.log.debug("Removing file: "+mylockfile)
                os.remove(mylockfile)
            except Exception, rme:
                self.log.debug("Exception caught removing files:" + str(rme))
                pass
            
            
            
    def unzipCredentialsToDir(self,sourcefile,destdir):
        '''
        unzip downloaded creds from 'sourcefile' to 'destdir'
        '''
        try:
            self.log.debug("unzipCredentialsToDir, sourcefile:"+str(sourcefile)+" destdir:"+str(destdir))
            #unzip credentials from a source path/file to a destdir
            cmd = 'unzip -o '+str(sourcefile)+' -d '+str(destdir)
            #status, output = commands.getstatusoutput(cmd)
            #self.log.debug("cmd:"+str(cmd)+", output:"+output)
            status = call(cmd, shell=True)
            if (status != 0 ):
                raise Exception("Failed to extract credentials for zip file")
        except Exception, e:
            raise Exception("unzipCredentialsToDir Failed: "+str(e))
        
    def sourceEucarcFromDir(self,srcdir):
        try:
            srcdir = str(srcdir)
            self.log.debug("sourceEucarcFromDir srcdir: " + srcdir)
            srcdir = str(srcdir)
            filelist = os.listdir(str(srcdir))
            if (not re.search('/$',srcdir) ):
                srcdir = srcdir+'/'
            for f in filelist:
                self.log.debug("file in dir:"+ str(f))
                if (re.search('eucarc',f)):
                    cmd = 'source '+srcdir+f
                    self.log.debug("exec cmd:"+str(cmd))
                    status, output = commands.getstatusoutput(cmd)
                    self.log.debug("cmd output:"+str(output))
                    if (status != 0 ):
                        raise Exception("cmd("+cmd+")failed with status:"+str(status))
                    return
            raise Exception("eucarc file not found in dir:"+str(srcdir))
        except Exception, e:
            raise Exception("sourceEucarcFromDir failed:" + str(e))
        
 
    def confirmAccount(self,acctname):
        '''
        This should simulate the user getting the email and clicking the confirmation link
        after being approved
        '''
        try:
            acctname = str(acctname)
            driver = self.driver
            link = self.getApprovalEmailLink(acctname)
            self.driverRestart()
            self.driver.get("about:blank")
            driver.get(str(link))
            self.waitForTextOnPage("confirmed", 2)
            driver.find_element_by_css_selector("button.gwt-Button").click()
        except Exception, e:
            self.log.critical("Could not confirm account:"+str(e))
            raise e
        #clear the browser since this sequence of events ends here
        self.driverRestart()
    
    def getApprovalEmailLink(self,acctname):
        #ssh into clc and see if an email and link was generated for this acctname
        acctname = str(acctname)
        output = []
        line = ""
        self.log.debug(self.hd("checkApprovalEmail starting("+acctname+")"))
        #ugly but simple way to get the last emailed link for this account from clc...
        searchcmd = "cat /var/spool/mail/root | grep \"'"+acctname+"' application was approved\" -a3 | grep https | tail -1"
        self.log.debug("checkApprovalEmail using cmd:"+str(searchcmd))
        try:
            output = self.eutester.sys(str(searchcmd))
        except Exception, e:
            self.log.critical("doh! error with ssh cmd: "+ str(e))
            raise e
        #this should probably only be 1 line but do this to make changing the search cmd easier if needed...?
        if (output != []):
            for line in output:
                self.log.debug("line in output:"+str(line))
                m = re.search('https', line)
                if (m):
                    self.log.debug("got Match:"+str(line))
                    return line
        raise Exception("No approval link found in email?")
        
    def getPasswordResetEmailLink(self,user,account):
        #ssh into clc and see if an email and link was generated for this acctname
        account = str(account)
        user = str(user)
        output = []
        line = ""
        self.log.debug(self.hd("getPasswordResetEmailLink starting("+user+"@"+account+")"))
        #ugly but simple way to get emailed link from clc...
        searchcmd = "cat /var/spool/mail/root | grep '"+user+"@"+account+"' -a10 | grep 'reset:confirmationcode' | tail -1"
        self.log.debug("getPasswordResetEmail using cmd:"+str(searchcmd))
        try:
            output = self.eutester.sys(str(searchcmd))
        except Exception, e:
            self.log.critical("doh! error with ssh cmd: "+ str(e))
            raise e
        #this should probably only be 1 line but do this to make changing the search cmd easier if needed...?
        if (output != []):
            for line in output:
                self.log.debug("line in output:"+str(line))
                m = re.search('https', line)
                if (m):
                    self.log.debug("got Match:"+str(line))
                    return line
        raise Exception("No password reset link found in email?")
    
    

    def changePassword(self,user,account,newpass,verify_pass="", expect=""):
        '''
        Simulate a user requesting a password reset, by clicking on reset link, getting email, 
        then clicking on emailed reset form, filling it out, and reseting password
        '''
        if (verify_pass == ""):
            verify_pass = newpass
        if (expect == ""):
            expect = self.wg.PasswordRestSuccess
        try:
            user = str(user)
            account = str(account)
            driver = self.driver
            link = self.getPasswordResetEmailLink(user, account)
            self.driverRestart()
            self.driver.get("about:blank")
            driver.get(str(link))
            self.waitForTextOnPage(self.wg.PasswordResetForm,2)
            driver.find_element_by_css_selector("input.gwt-PasswordTextBox").clear()
            driver.find_element_by_css_selector("input.gwt-PasswordTextBox").send_keys(newpass)
            driver.find_element_by_xpath("//tr[2]/td[2]/input").clear()
            driver.find_element_by_xpath("//tr[2]/td[2]/input").send_keys(verify_pass)
            driver.find_element_by_link_text("OK").click()
            self.waitForTextOnPage(expect, 0)
            if (expect == self.wg.PasswordRestSuccess):
                driver.find_element_by_css_selector("button.gwt-Button").click()
    
        except Exception, e:
            self.log.critical("Error with reset passwd dialog:"+str(e))
            raise e
        #clear the browser since this sequence of events ends here
        self.driverRestart()


    def signUpUser(self, account, user, passwd, email,expect= ""):
        '''
        Method is used to Sign a user up from the signup link on the login page
        Should fill out the form on the signup pop up and verify page returns to login page 
        afterwards.
        If these xpaths get used elsewhere should move to globals, otherwise
        this small portion may not be worth resolving xpath in globals since it's unique to this function
        '''
        if (expect == ""):
            expect = self.wg.AccountSignUpSuccess
        self.log.debug(self.hd("signUpUser:account:"+account+", user:"+ user+", passwd:"+ passwd+", email:"+email))
        try:
            driver = self.driver
            driver.get(self.clcurl) # assume were logged in, and go to home page...
            driver.find_element_by_link_text("Signup Account").click()
            driver.find_element_by_css_selector("input.gwt-TextBox").clear()
            driver.find_element_by_css_selector("input.gwt-TextBox").send_keys(account)
            driver.find_element_by_xpath("//tr[2]/td[2]/input").clear()
            driver.find_element_by_xpath("//tr[2]/td[2]/input").send_keys(email)
            driver.find_element_by_css_selector("input.gwt-PasswordTextBox").clear()
            driver.find_element_by_css_selector("input.gwt-PasswordTextBox").send_keys(passwd)
            driver.find_element_by_xpath("//tr[4]/td[2]/input").clear()
            driver.find_element_by_xpath("//tr[4]/td[2]/input").send_keys(passwd)
            driver.find_element_by_link_text("OK").click()
            self.waitForTextOnPage(expect,1) 
            if (expect == self.wg.AccountSignUpSuccess):
                driver.find_element_by_css_selector("button.gwt-Button").click()
                #wait for password on the page to verify the login page is returned
                #use a retry count of 3 which should essentially wait for 3 x the implicit wait period
                self.waitForText(self.wg.xPage,"Password", 3)#return to home page failed
        except Exception, e:
            self.log.critical("Err caught during SignUpUser ("+user+"@"+account+") from login page:\n"+ str(e))
            raise e
        

    def clickButtonXpathAndVerify(self,xpath,verify_text):
        '''
        click button at xpath and verify the success 
        by checking the page for an expected string verify_text
        selenium will error if link is not on the visible page, and scrolling/resizing is not working
        in the latest version for FF and IE...?
        '''
        try:
            self.log.debug(self.hd("clickButtonXpathAndVerify starting...\nButtonxpath:"+str(xpath)+"\nVerify_text:"+verify_text))
            driver = self.driver
            button=xpath
            driver.find_element_by_xpath(button).click()
            self.waitForTextOnPage(verify_text)
        except Exception, e:
            self.log.critical("clickButtonXpathAndVerify err:"+str(e))
            raise e
        
    def getAccountListAll(self):
        self.log.critical(self.hd("gettAccountListALL starting..."))
        return self.getAccountList(None,None,None)
    
    def getAccountById(self,uid):
        self.log.critical(self.hd("Starting getAccountById:"+str(uid)))
        if (not uid):
            self.log.critical("uid was null in getAccountById")
            raise Exception("uid was null in getAccountById")
        else:
            return self.getAccountList(None, uid, None)
            
            
    def getAccountByName(self, name):
        acct = euwebaccount.Euwebaccount()
        self.log.critical(self.hd("getAccountByName ("+str(name)+") starting...."))
        if (not name):
            self.log.critical("name was null in getAccountById")
            raise Exception("name was null in getAccountById")
        else:
            acct = self.getAccountList(name,None, None)
            if (acct is None):
                raise Exception("getAccountByName, accountlist returned null?")
            self.log.debug("Got account by name:")
            acct.printSelf()
            return acct
            
    def getAccountsByStat(self,stat):
        self.log.critical(self.hd("getAccountsByStat Starting:"+str(stat)))
        if (not stat):
            self.log.critical("Name was Null in getAccountsByStat")
            raise Exception("Name was null in getAccountsByStat")
        else:
            return self.getAccountList(None, None, stat)
        
    
    def getAccountList(self,name,uid,status):
        '''
        (avoid this method)
        ugly function in the making to traverse the accounts table and handle all the timing and stale page issues you can run into...
        navigate to the accounts page and get all the rows found in the accounts table   
        The list can be sorted by name, id or status, or if all are set to non it will retrieve them all
        '''
        
        self.log.debug(self.hd("getAccountList starting, name:("+str(name)+") id:("+str(uid)+") status:("+str(status)+")"))
        if (name is not None):
            name = str(name)
        if (uid is not None):
            uid = str(uid)
        if (status is not None):
            status = str(status)
            
        if ((name is None) and (uid is None) and (status is None)):
            getall = True
        else:
            getall = False
        try:
            accountlist = []
            driver = self.driver
            #navigate to page
            self.clickButtonXpathAndVerify( self.wg.xLn_Accounts, self.wg.AccountsTxt)
            self.driver.refresh()# 
            #make sure the table is present
            try:
                driver.find_elements_by_xpath(self.wg.xAccountsTable)
            except Exception, e:
                self.debug("accounts list is empty:"+ str(e))
                return accountlist
            prange = str(driver.find_element_by_xpath(self.wg.xAccountPageRange).get_attribute("textContent"))
            accountsonpage = int(prange.split('of').pop())
            row_xpath=self.wg.xAccountsRow1
            tr = 1
            page = 1
            retry = 1
            driver.implicitly_wait(1)
            #loop over a known pattern in xpath to grab the contents of the table
            #From this we can grab account name, id, and status, also can hold 
            while (True):
                try:
                    if (tr == 1 ):
                        self.log.debug("starting search account loop on table(tr:"+str(tr)+")")
                    gAccount = euwebaccount.Euwebaccount() 
                    #account= driver.find_element_by_xpath(row_xpath)
                    gAccount.row_xpath = row_xpath
                    tr+=1
                    if (tr > 2):
                        retry = 1 #reset retry if we get this far
                    row_xpath = self.wg.xAccountsRow1+"["+str(tr)+"]"
                    id_xpath = row_xpath+'/td'
                    name_xpath = row_xpath+'/td[2]'
                    status_xpath = row_xpath+'/td[3]'
                    
                    gAccount.id  = driver.find_element_by_xpath(id_xpath).get_attribute("textContent")
                    gAccount.id_xpath = id_xpath
                    self.log.debug("got id:"+gAccount.id)
                    if ((not getall) and (uid != None)):
                        if( uid == gAccount.id):
                            addtolist = True
                        else:
                            addtolist = False
                            continue
                        
                    gAccount.name = driver.find_element_by_xpath(name_xpath).get_attribute("textContent")
                    gAccount.name_xpath = name_xpath
                    self.log.debug("got name:"+gAccount.name)
                    if ((not getall) and (name != None)):
                        if (name == gAccount.name):
                            addtolist = True
                        else:
                            addtolist = False
                            continue
                    
                    gAccount.status = driver.find_element_by_xpath(status_xpath).get_attribute("textContent")
                    gAccount.status_elm = status_xpath
                    self.log.debug("got status:"+gAccount.status)
                    if ((not getall) and (status != None)):
                        if (status == gAccount.status):
                            addtolist = True
                        else:
                            addtolist = False
                            continue
                    
                    #if we only expect to match 1 name or 1 id return the account obj if we have one
                    if (addtolist and (not getall) and (not status)):
                        self.log.debug("returning single account (Acct#:"+str(tr)+" on page:"+str(page)+") :"+gAccount.name)
                        return gAccount
                        
                    #Otherwise if were getting em all or sorting to create a list add append it to the list
                    if (getall or addtolist):
                        self.log.debug("Adding account(#"+str(tr)+") to list")
                        accountlist.append(gAccount)
                    
                       
                except NoSuchElementException:
                    print "No such elm in list. tr:"+str(tr)+" retry:"+str(retry)+" accountsonpage:"+str(accountsonpage)
                    if ((accountsonpage > 0) and (retry < 5) and (tr == 2)):
                            self.log.debug("Total Accounts:"+str(accountsonpage)+" != 0, but found 0 here. Retry:"+str(retry)+" tr:"+str(tr))
                            retry += 1
                            tr = 1
                            time.sleep(3)
                    else:
                        try:
                            #We may have more accounts on the next page so try the forward buttton first...
                            self.log.debug("end of list try pressing the forward button (tr:"+str(tr)+" retry:"+str(retry)+" ...")
                            prange = str(driver.find_element_by_xpath(self.wg.xAccountPageRange).get_attribute("textContent"))
                            accountsonpage = int(prange.split('of').pop())
                            #click our button, and expect to NOT find range, if we do the button failed and were on the same page
                            try:
                                driver.implicitly_wait(3)
                                self.clickButtonXpathAndVerify(self.wg.xAccountForwardButton, prange)
                                button_failed = True
                            except Exception, be:
                                self.log.debug("range("+prange+")not found, assuming page progressed=good"+str(be))
                                button_failed = False
                                pass
                            if (button_failed):
                                raise Exception("Forward button did not progress page")
                            
                            row_xpath=self.wg.xAccountsRow1
                            tr = 1
                            page += 1
                            #Make sure the table gets reloaded:
                            driver.find_elements_by_xpath(self.wg.xAccountsTable)
                            driver.find_element_by_xpath(row_xpath)
                            time.sleep(1)
                            
                            self.log.debug("Pressed button, looks like there's more?")
                            driver.implicitly_wait(1)
                        except Exception, e:
                            self.log.debug("NoSuchElement assuming end of list found")
                            if (accountlist == []):
                                raise Exception("account not found(name:"+str(name)+" id:"+str(uid)+" status:"+str(status)+" )list is empty")
                            else:
                                self.log.debug("Returning account list?")
                                return accountlist
                
            raise Exception("uh oh, out of the loop?")
        except Exception, e:
            self.log.critical("Err while getting account list:"+str(e))
            raise e
        finally:
            driver.implicitly_wait(10)
            
            
  
    def searchForElementByUrl(self,url):
        '''
        Enter search criteria into url, this will be appended to the base clc url. 
        see euwebglobals for help with examples
        '''
        url = self.clcurl+str(url)
        self.log.debug(self.hd("searchForElementByUrl ("+str(url)+")"))
        #strings = verifytext = url.split('=')
        driver = self.driver
        driver.get(url)
        self.log.debug("search results page loaded, now verify search criteria is on page...")
        #now got through the url and verify all the seach criteria is present on the screen...
        pairs = re.findall('\w+\=\w+',url)
        for p in pairs:
            verifytext = p.split('=').pop()
            self.log.debug("searchForElementByUrl verifytext:"+verifytext)
            self.waitForTextOnPage(verifytext, 2)
        self.log.debug("searchForElement:Found, should be present in screen...")
        
    
    def searchForUser(self,user,account):
        '''
        Formats a user specific query to feed to search by url
        '''
        user=str(user)
        account=str(account)
        url = self.wg.urlSearchUserByAccount+account+" name="+user
        self.log.debug("searchForUser Url ("+str(url)+")")
        self.searchForElementByUrl(str(url))
    

    def getUserRowValuesByXpath(self,row_xpath):
        '''
        Assumes the table is current within the browser
        note this only gets the row values, so does not completely populate the user object
        '''
        try:
            self.log.debug(self.hd("getUserValuesByXpath: " +str(row_xpath)))
            driver = self.driver
            user = euwebuser.Euwebuser(makerandom=False)
            #first make sure the row is available...
            driver.find_element_by_xpath(row_xpath)
            
            id_xpath = row_xpath+'/td'
            name_xpath = row_xpath+'/td[2]'
            path_xpath = row_xpath+'/td[3]'
            account_xpath = row_xpath+'/td[4]'
            enabled_xpath = row_xpath+'/td[5]'
            status_xpath = row_xpath+'/td[6]'
            
            user.id = driver.find_element_by_xpath(id_xpath).get_attribute("textContent")
            user.user = driver.find_element_by_xpath(name_xpath).get_attribute("textContent")
            user.path = driver.find_element_by_xpath(path_xpath).get_attribute("textContent")
            user.account = driver.find_element_by_xpath(account_xpath).get_attribute("textContent")
            user.enabled = driver.find_element_by_xpath(enabled_xpath).get_attribute("textContent")
            user.status = driver.find_element_by_xpath(status_xpath).get_attribute("textContent")
            user.printUser()
            return user
        except Exception, e:
            raise Exception("Failed to get user values from table: "+ str(e))
            
            
            
        
        

    def enableDisableUser(self,user,account,enable_flag=True):
        '''
        Bring user into focus and toggle the rightnav element based on the enable value
        verifies the change has taken affect. 
        '''
        driver = self.driver
        if (enable_flag):
            entxt = "true"
        else:
            entxt = "false"
        self.log.debug(self.hd("enableDisableUser: user:"+user+" enable_flag: "+str(enable_flag)) )
        #search for user, user should be only element in the table after this...
        self.searchForUser(user,account)
        #bring user into focus, which brings up right nav
        self.clickButtonXpathAndVerify(self.wg.xUsersRow1Id, user)
        state = self.getRightNavValueByName(self.wg.UsersRightNav_Enabled, attribute="checked")
        self.log.debug("current state is: "+state+" , desired state:"+entxt)
        if ((state == "true")==enable_flag):
            self.log.debug("Enabled state is already set to:"+str(state))
            return
        self.log.debug("Attempting to click checkbox into desired state: "+entxt)
        #toggle state of checkbox...
        checkBoxXpath = self.getRightNavValueByName("Enabled",returnXpath = True)
   
        driver.find_element_by_xpath(checkBoxXpath).click()
        time.sleep(2)
   
        self.log.debug("clicked check box, now click save...")
        time.sleep(5)
        #save it
        driver.find_element_by_xpath(self.wg.xRighNavSaveButton).click()
        #verify the change took affect...
        self.log.debug("clicked save, now refresh and check that it took effect")
        time.sleep(5)
        driver.refresh()
        #bring user back into focus, assuming still on the user page...
        self.clickButtonXpathAndVerify(self.wg.xUsersRow1Id, user)
        newstate = self.getRightNavValueByName(self.wg.UsersRightNav_Enabled, attribute="checked") 
        if (newstate == state):
            raise Exception("Enabled state checkbox value did not change was:"+str(state)+" now: "+str(newstate))
        
        
    
    def addUserToAccount(self,accountname, username, path="", verifyLog = True):
        #assumes the current user is admin or has priv to do so...
        if (path == ""):
            path = "/"+username
        self.log.debug(self.hd("addUserToAccount (account:"+accountname+" user: "+username+" path:"+path+")"))
        driver = self.driver
        self.searchForElementByUrl(self.wg.urlSearchAccountByName+accountname)
        self.clickButtonXpathAndVerify(self.wg.xAccountsRow1Id, self.wg.rightNavTxt)
        driver.find_element_by_link_text("New users").click()
        driver.find_element_by_xpath("//td/div/table/tbody/tr/td[2]/input").clear()
        driver.find_element_by_xpath("//td/div/table/tbody/tr/td[2]/input").send_keys(username)
        driver.find_element_by_xpath("//td/div/table/tbody/tr[2]/td[2]/input").clear()
        driver.find_element_by_xpath("//td/div/table/tbody/tr[2]/td[2]/input").send_keys(path)
        driver.find_element_by_link_text("OK").click()
        if (verifyLog):
            result = self.getOnScreenLogMesg()
            if (result == "Failed to create users" ):
                raise Exception("Log indicates: Failed to create account")
            else:
                self.log.debug("log message after addUserToAccount:"+result)
                
                
    
    def changeUserPassword(self, accountname, username, adminpass, newpass, expect ="", vpass="", verifyLog=True):
        #assumes that this is executed from the admin user of the specific account this user is part of
        #changes the password of a user, will wait for text "expect" if used
        if (vpass == ""):
            vpass =newpass # used in the case you wan the 2nd typed passwd to be different from the 1st for testing
        self.log.debug(self.hd("changeUserPassword: (account:"+accountname+" user: "+username+" oldpass:"+adminpass+" newpass:"+newpass+")"))
        driver= self.driver
        url = self.wg.urlSearchUserByAccount+accountname+" name="+username
        self.searchForElementByUrl(url)
        self.clickButtonXpathAndVerify(self.wg.xUsersRow1Id, self.wg.rightNavTxt)
        passwdxpath = self.getRightNavValueByName(self.wg.UsersRighNav_Password,attribute="tagName",returnXpath=True, input_path="/div/a/span")
        driver.find_element_by_xpath(passwdxpath).click()
        self.waitForTextOnPage("Change password", 1)
        driver.find_element_by_css_selector("input.gwt-PasswordTextBox").clear()
        driver.find_element_by_css_selector("input.gwt-PasswordTextBox").send_keys(adminpass)
        driver.find_element_by_xpath("//td/div/table/tbody/tr[2]/td[2]/input").clear()
        driver.find_element_by_xpath("//td/div/table/tbody/tr[2]/td[2]/input").send_keys(newpass)
        driver.find_element_by_xpath("//tr[3]/td[2]/input").clear()
        driver.find_element_by_xpath("//tr[3]/td[2]/input").send_keys(vpass)
        driver.find_element_by_link_text("OK").click()
        if (expect != ""):
            self.waitForTextOnPage(expect, 1)
        if (verifyLog == True):
            result = self.getOnScreenLogMesg()
            self.log.debug("change passwd log result text:"+result)
            if (result == "Failed to change password"):
                raise Exception("Log Msg indicates we failed to Change passoword")
            elif ( result == "Password changed"):
                self.log.debug("Password Changed successfully")
            else:
                self.log.critical("Unrecognized or missing log message during changeUserPassword")
                
                
    
    def getOnScreenLogMesg(self):
        #attempt to get the most recent log message to the screen
        try:
            message = self.driver.find_element_by_xpath(self.wg.xLogMessage).get_attribute("textContent")
            message = str(message)
            self.log.debug("GetOnScreenLogMesg returning: "+message)
            return message
        except NoSuchElementException:
            self.log.debug("NoSuchElement assuming there is no message")
            return ""
        
        
        
    def userFirstTimeLogin(self,email,oldpass,newpass,newpass2="",expect=""):
        '''
        Assumes the firttime login pop up is present, attempts to fill out the forms
        email - address to enter into form for this user
        oldpass - the expected current password for this user
        newpass - the newpassword for this user
        newpass2 - the text to be entered in the 'verify password' box, default is = newpass
        expect - any text to be expected on the page at the end of the execution 
        '''
        if (newpass2 == ""):
            newpass2 = newpass
        driver = self.driver
        try:
            driver.find_element_by_css_selector("input.gwt-TextBox").clear()
        except Exception, e:
            raise("firstTimelogin failed, firsttime popup may be missing?:"+str(e))
        driver.find_element_by_css_selector("input.gwt-TextBox").send_keys(email)
        driver.find_element_by_css_selector("input.gwt-PasswordTextBox").clear()
        driver.find_element_by_css_selector("input.gwt-PasswordTextBox").send_keys(oldpass)
        driver.find_element_by_xpath("//tr[3]/td[2]/input").clear()
        driver.find_element_by_xpath("//tr[3]/td[2]/input").send_keys(newpass)
        driver.find_element_by_xpath("//tr[4]/td[2]/input").clear()
        driver.find_element_by_xpath("//tr[4]/td[2]/input").send_keys(newpass2)
        driver.find_element_by_link_text("OK").click()
        if (expect != ""):
            self.waitForTextOnPage(expect, 1)
        
        
    def deleteAccount(self,accountname,expect="",verifylog=True):
        driver = self.driver
        self.searchForElementByUrl(self.wg.urlSearchAccountByName+accountname)
        driver.find_element_by_link_text("Delete accounts").click()
        driver.find_element_by_link_text("OK").click()
        if (verifylog == True):
            result = self.getOnScreenLogMesg()
            if (result != "Accounts deleted" ):
                raise Exception("Log indicates: Failed to create account")
            else:
                self.log.debug("log message after addUserToAccount:"+result)
        

 
    def clickAndApproveAccount(self, bool_approve, bool_ok):
        #this assumes the test has already clicked on the xpath of a user item to bring that
        #user into focus on the accounts page. ok boolean indicates how the popup window is handled
        driver = self.driver
        if (bool_approve):
            #click on the approve button
            driver.find_element_by_link_text("Approve").click()
        else:
            driver.find_element_by_link_text("Reject").click()
        #now handle the popup which follows...
        if (bool_ok):
            #click on the ok button in the popup
            driver.find_element_by_link_text("OK").click()
        else:
            #click on the cancel button on the popup
            driver.find_element_by_link_text("Reject").click()
        driver.refresh()
    
    
    def addNewGroupToAccount(self, accountname,newgroupname, path="", verifyLog=True):
        #selects an account and proceeds to add a new group and group path to it
        if (path == ""):
            path = "/"+newgroupname
        driver = self.driver
        #bring our account into focus and select it
        self.searchForElementByUrl(self.wg.urlSearchAccountByName+accountname)
        self.driver.find_element_by_xpath(self.wg.xAccountsRow1Id).click()
        driver.find_element_by_link_text("New groups").click()
        driver.find_element_by_xpath("//td/div/table/tbody/tr/td[2]/input").clear()
        driver.find_element_by_xpath("//td/div/table/tbody/tr/td[2]/input").send_keys(newgroupname)
        driver.find_element_by_xpath("//td/div/table/tbody/tr[2]/td[2]/input").clear()
        driver.find_element_by_xpath("//td/div/table/tbody/tr[2]/td[2]/input").send_keys(path)
        driver.find_element_by_xpath("//tr[4]/td/a/span").click()
        #check the log at bottom of screen
        time.sleep(1) #give a second before fetching log message
        if (verifyLog == True):
            result = self.getOnScreenLogMesg()
            if (result.lower().find('fail') >= 0) :
                self.log.critical("Log Message:("+result+")")
                raise Exception("Log indicates: Failed to add group "+newgroupname+" to account")
            else:
                self.log.debug("log message after addNewGroupToAccount:("+result+")")
        
        
    def addExistingUserToGroup(self, accountname, groupname,username, verifyLog=True):
        self.log.debug( self.hd("addExistingUserToGroup starting (accountname:"+str(accountname)+" groupname:"+str(groupname)+" username:"+str(username)+")") )
        driver=self.driver
        #get group into focus and selected
        url = self.wg.urlSearchGroupByName+groupname+" account="+accountname
        self.searchForElementByUrl(url)
        time.sleep(3) #let page load
        self.log.debug("attempting to click on group row")
        driver.find_element_by_xpath(self.wg.xGroupRow1Id).click()
        self.log.debug("clicked on group row ,now looking for add users link to click")
        
        driver.find_element_by_link_text("Add users").click()
        self.log.debug("just clicked add users link")
        driver.find_element_by_xpath("//td/div/table/tbody/tr/td[2]/input").clear()
        driver.find_element_by_xpath("//td/div/table/tbody/tr/td[2]/input").send_keys(username)
        #driver.find_element_by_xpath("/html/body/div[6]/div/table/tbody/tr[2]/td[2]/div/div/table/tbody/tr[4]/td/a/span").click()
        driver.find_element_by_xpath("//html/body/div[6]/div/table/tbody/tr[2]/td[2]/div/div/table/tbody/tr[4]/td/a").click()
        #check the log at bottom of screen
        time.sleep(1) # give a second for the log message to update
        if (verifyLog == True):
            result = self.getOnScreenLogMesg()
            if (result.lower().find('fail') >= 0):
                self.log.critical("Log Message:("+result+")")
                raise Exception("Log indicates: Failed to add group "+groupname+" to account")
            else:
                self.log.debug("log message after addNewGroupToAccount:("+result+")")
        
    def addPolicyToAccount(self, accountname, newpolicyname, policytext, verifyLog=True):
        self.log.debug(self.hd("addPolicyToAccount(accountname:"+str(accountname)+" policytext:"+str(policytext)+")"))
        driver = self.driver
        #bring our account into focus and select it
        self.searchForElementByUrl(self.wg.urlSearchAccountByName+accountname)
        self.driver.find_element_by_xpath(self.wg.xAccountsRow1Id).click()
        #bring up add policy pop up window
        driver.find_element_by_link_text("Add policy").click()
        #fill out popup window add policy form
        driver.find_element_by_xpath("//td/div/table/tbody/tr/td[2]/input").clear()
        driver.find_element_by_xpath("//td/div/table/tbody/tr/td[2]/input").send_keys(newpolicyname)
        driver.find_element_by_css_selector("textarea.gwt-TextArea").clear()
        #enter our policy text string...
        #driver.find_element_by_css_selector("textarea.gwt-TextArea").send_keys("{\n  \"Statement\": [\n    {\n      \"Sid\": \"Stmt1323987968698\",\n      \"Action\": \"*\",\n      \"Effect\": \"Deny\",\n      \"Resource\": \"*\"\n    }\n  ]\n}")
        driver.find_element_by_css_selector("textarea.gwt-TextArea").send_keys(policytext)
        driver.find_element_by_link_text("OK").click()
        time.sleep(1) # give a second for the log message to update
        if (verifyLog == True):
            result = self.getOnScreenLogMesg()
            if (result.lower().find('fail') >= 0):
                self.log.critical("Log Message:("+result+")")
                raise Exception("Log indicates: Failed to add policy:("+str(newpolicyname)+") to account:("+str(accountname)+")")
            else:
                self.log.debug("log message after addPolicyToAccount:("+result+")")
    
    def addPolicyToUser(self,username,accountname,newpolicyname, policytext, verifyLog=True):
        self.log.debug(self.hd("addPolicyToUser(accountname:"+str(accountname)+" policytext:"+str(policytext)+")"))
        driver = self.driver
        #bring our user into focus and select it
        url = self.wg.urlSearchUserByName+username+" account:"+accountname
        self.searchForElementByUrl(url)
        self.driver.find_element_by_xpath(self.wg.xUsersRow1Id).click()
        #bring up add policy pop up window
        driver.find_element_by_link_text("Add policy").click()
        #fill out popup window add policy form
        driver.find_element_by_xpath("//td/div/table/tbody/tr/td[2]/input").clear()
        driver.find_element_by_xpath("//td/div/table/tbody/tr/td[2]/input").send_keys(newpolicyname)
        driver.find_element_by_css_selector("textarea.gwt-TextArea").clear()
        #enter our policy text string...
        #driver.find_element_by_css_selector("textarea.gwt-TextArea").send_keys("{\n  \"Statement\": [\n    {\n      \"Sid\": \"Stmt1323987968698\",\n      \"Action\": \"*\",\n      \"Effect\": \"Deny\",\n      \"Resource\": \"*\"\n    }\n  ]\n}")
        driver.find_element_by_css_selector("textarea.gwt-TextArea").send_keys(policytext)
        driver.find_element_by_link_text("OK").click()
        time.sleep(1) # give a second for the log message to update
        if (verifyLog == True):
            result = self.getOnScreenLogMesg()
            if (result.lower().find('fail') >= 0):
                self.log.critical("Log Message:("+result+")")
                raise Exception("Log indicates: Failed to add policy:("+str(newpolicyname)+") to "+str(username)+"@"+str(accountname)+")")
            else:
                self.log.debug("log message after addPolicyToUser:("+result+")")
    
    def addPolicyToGroup(self,groupname,accountname, newpolicyname, policytext, verifyLog=True):
        self.log.debug(self.hd("addPolicyToGroup(groupname:"+str(accountname)+" policytext:"+str(policytext)+")"))
        driver = self.driver
        #bring our group into focus and select it
        url = self.wg.urlSearchGroupByName+groupname+" account:"+accountname
        self.searchForElementByUrl(url)
        self.driver.find_element_by_xpath(self.wg.xGroupRow1Id).click()
        #bring up add policy pop up window
        driver.find_element_by_link_text("Add policy").click()
        #fill out popup window add policy form
        driver.find_element_by_xpath("//td/div/table/tbody/tr/td[2]/input").clear()
        driver.find_element_by_xpath("//td/div/table/tbody/tr/td[2]/input").send_keys(newpolicyname)
        driver.find_element_by_css_selector("textarea.gwt-TextArea").clear()
        #enter our policy text string...
        #driver.find_element_by_css_selector("textarea.gwt-TextArea").send_keys("{\n  \"Statement\": [\n    {\n      \"Sid\": \"Stmt1323987968698\",\n      \"Action\": \"*\",\n      \"Effect\": \"Deny\",\n      \"Resource\": \"*\"\n    }\n  ]\n}")
        driver.find_element_by_css_selector("textarea.gwt-TextArea").send_keys(policytext)
        driver.find_element_by_link_text("OK").click()
        time.sleep(1) # give a second for the log message to update
        if (verifyLog == True):
            result = self.getOnScreenLogMesg()
            if (result.lower().find('fail') >= 0):
                self.log.critical("Log Message:("+result+")")
                raise Exception("Log indicates: Failed to add policy:("+str(newpolicyname)+") to "+str(groupname)+"@"+str(accountname)+")")
            else:
                self.log.debug("log message after addPolicyToGroup:("+result+")")
                
                
    def modifyVmType(self,vmtype, attr, value, verifyLog = True):
        '''
        modify an attribute of a vmtype named 'vmtype'
        attempt to set the vmtype's attribute 'attr' to 'value'
        Note: use euweb globals vm right nav txt for the attrs when using this method
        '''
        self.log.debug(self.hd("addPolicyToGroup(vmtype:("+str(vmtype)+") attribute:"+str(attr)+" value:"+str(value)+")"))
        driver = self.driver
        #got to the vm page
        driver.get(self.clcurl+self.wg.urlSearchVmType)
        self.waitForTextOnPage(self.wg.VmTypesTxt)
        #find our row based on the name of the vm type, and bring it into focus to open the right nav
        #modify the xpath so the first element in the row is what gets clicked
        driver.find_element_by_xpath(self.getTableRowXpathByString(self.wg.xVmTypeTable, vmtype)+"/td").click()
        #now look for a table elment with the exact text 'attr' and set it's value to value
        attrxpath = self.getRightNavValueByName(attr, returnXpath=True)
        driver.find_element_by_xpath(attrxpath).clear()
        driver.find_element_by_xpath(attrxpath).send_keys(str(value))     
        #then click save
        time.sleep(1)
        driver.find_element_by_xpath(self.wg.xRighNavSaveButton).click()
        time.sleep(1)
        if (verifyLog == True):
            result = self.getOnScreenLogMesg()
            if (result.lower().find('fail') >= 0):
                self.log.critical("Log Message:("+result+")")
                raise Exception("Log indicates: Failed vmtype modification:("+str(vmtype)+")  attr"+str(attr)+" to "+str(value)+")")
            else:
                self.log.debug("log message after vmtype modification:("+result+")")
        
        
    def getTableRowXpathByString(self, table_xpath, match, startcol=1, endcol=1, case=False, highlightrow=False):
        '''
        Traverse a table at tablexpath, if elment at 'startcol' through 'endcol' matches the string 'match' 
        then the xpath for the row which that was found in is returned 
        This method assumes the page containing the table at tablexpath is loaded.
        This method can be used with other methods which forward elements in the the table ie:forward/reverse display buttons
        -'case' determines case sensative matching. 
        -'highlight' row can be used for debug to see which row is being examined in the browser if the row supports click, the first element will be click()'d
        '''
        if (case == False):
            match = str(match).upper()
        table_xpath = str(table_xpath)
        self.log.debug(self.hd("getTableRowXpathByName( table xpath:("+table_xpath+") match:("+match+")"))
        driver = self.driver
        row_xpath = table_xpath+"/tbody/tr"
        tr = 1
        td = startcol
        try:
            driver.find_elements_by_xpath(table_xpath)
        except Exception, nfe:
            self.log.critical("Table not found at xpath:"+str(table_xpath))
            raise nfe
        #to speed up the interations through the test set our timeout to 1 second per element not found
        driver.implicitly_wait(1)
        try:
            while (True):
                td = startcol
                if (td > 1):
                    element_xpath = row_xpath+"/td["+str(td)+"]"
                else:
                    element_xpath = row_xpath+"/td"
                
                if (highlightrow == True):
                    #click on the first element in the row so it is brought into focus
                    self.driver.find_element_by_xpath(row_xpath+"/td").click()
                self.log.debug ("trying td:"+str(td)+"row:"+str(row_xpath))
                try:
                    while  ( td <= endcol ):
                        self.log.debug("looking for ("+match+") at xpath:"+str(element_xpath))
                        vstr = str(driver.find_element_by_xpath(element_xpath).get_attribute("textContent"))
                        if (case == False):
                            vstr = vstr.upper()
                        self.log.debug( "Got value at row:"+str(tr)+" col:"+str(td)+" (value= "+str(vstr)+")")
                        if (vstr == match):
                            self.log.debug("Got match:("+match+" == "+vstr+") returning this row's xpath")
                            return row_xpath
                        td+=1
                        element_xpath=row_xpath+"/td["+str(td)+"]"
                    self.log.debug("not found in this row")
                    tr+=1
                    row_xpath=row_xpath+"["+str(tr)+"]"
                except NoSuchElementException, nse:
                    #the columns given likely exceeded the columns in the row so no such element
                    #not found on that row within  the columns defined, increment row and try again
                    self.log.debug("not found in this row")
                    tr+=1
                    row_xpath=row_xpath+"["+str(tr)+"]"
        except NoSuchElementException, nse:
            self.log.debug("End of visible table, item not found: "+ match)
            driver.implicitly_wait(10)
            raise nse
        finally:
            driver.implicitly_wait(10)
        
            
        
    
    def getRightNavValueByName(self,name,attribute="value", table_xpath="",row1_xpath="",returnXpath=False, input_path="[2]/input"):
        '''
        Get a table value out of specific page's right nav (or a table) by matching the name of the table element
        This nav is only shown for the account which is highlighted in the main accounts page. 
        for example "Registration status" would likely have a value of CONFIRMED or REGISTERED
        if returnXpath flag is set, this will return the xpath of the value element...
        xpath example: return the  xpath of checkbox to be checked or the textbox to be filled
        Note:Change input path if this is not a input text field, etc..
        '''
        if (table_xpath == ""):
            table_xpath = self.wg.xRightNavTable
        if (row1_xpath == ""):
            row1_xpath = table_xpath+"/tbody/tr"
            
        try:
            name = str(name)
            nav_val=""
            self.log.debug(self.hd("getRightNavValueByName (name:"+str(name)+" returnxpath:"+str(returnXpath)+")..."))
            driver = self.driver
            #self.clickButtonXpathAndVerify( self.wg.xLn_Accounts, self.wg.AccountsTxt)
            #make sure the table is present
            try:
                driver.find_elements_by_xpath(table_xpath)
            except Exception, e:
                self.debug("accounts RighNav is empty:"+ str(e))
                return nav_val  
            #now go through the table, if we find an element who's name matches our string
            #return the value of that element
            row_xpath=row1_xpath+"/td"
            tr = 1
            #were depending on a timeout to find an xpath to determine a failure or when the end 
            #of the table is reached, at this point we've already waited above for the table to load
            #so set the timeout to  small value now...
            driver.implicitly_wait(1)
            try:
                while (True):
                    self.log.debug("looking for ("+name+") at xpath:"+row_xpath)
                    vstr = str(driver.find_element_by_xpath(row_xpath).get_attribute("textContent"))
                    self.log.debug( "Got right nav element text: = "+vstr)
                    if (vstr == name):
                        self.log.debug("got match on: "+vstr)
                        nav_xpath = row_xpath+input_path
                        self.log.debug( "looking for value at:"+nav_xpath)
                        #either return the xpath of the elm or the string value of the elm here...
                        try:
                            nav_val = str(driver.find_element_by_xpath(nav_xpath).get_attribute(attribute))
                        except NoSuchElementException, nse:
                            self.log.debug("No such element,trying xpath with span for checkbox maybe?")
                            nav_xpath = row_xpath+"[2]/span/input"
                            nav_val = str(driver.find_element_by_xpath(nav_xpath).get_attribute(attribute))
                        self.log.debug("Found element("+name+") value("+nav_val+")")
                        if (returnXpath):
                            self.log.debug("Returning right nav XPATH: "+nav_xpath)
                            return nav_xpath
                        else:
                            return nav_val
                    tr+=1
                    row_xpath=row1_xpath+"["+str(tr)+"]/td"
            except NoSuchElementException, nse:
                self.log.debug("End of righ nav table, item not found: "+name)
                driver.implicitly_wait(10)
                raise nse
            finally:
                driver.implicitly_wait(10)
        except Exception, e:
            self.log.critical("Error getting element from accounts right nav:"+name)
            raise e
        
    #Click on reset password link on login page, and follow flow of popup
    #Expect a certain string to test for different flows, by default expects a succesful form flow
    #this should generate an emailed link 
    def requestPasswordReset(self,user,account,email,expect=""):
        self.log.debug(self.hd("requestPasswordReset..."))
        if (expect == ""):
            expect = self.wg.PasswordResetTxt
        driver = self.driver
        driver.find_element_by_link_text("Reset Password").click()
        driver.find_element_by_css_selector("input.gwt-TextBox").clear()
        driver.find_element_by_css_selector("input.gwt-TextBox").send_keys(user)
        driver.find_element_by_xpath("//tr[2]/td[2]/input").clear()
        driver.find_element_by_xpath("//tr[2]/td[2]/input").send_keys(account)
        driver.find_element_by_xpath("//tr[3]/td[2]/input").clear()
        driver.find_element_by_xpath("//tr[3]/td[2]/input").send_keys(email)
        driver.find_element_by_link_text("OK").click()
        self.waitForTextOnPage(expect,0)
        if (expect == self.wg.PasswordResetTxt):
            driver.find_element_by_css_selector("button.gwt-Button").click()
            self.waitForTextOnPage(self.wg.PasswordTxt, 0)
        
    def driverRestart(self):
        self.log.debug(self.hd("driverRestart..."))
        self.driver.delete_all_cookies()
        self.driver.get("about:blank")
        #self.driver.refresh()
        #self.driver.stop_client()
        
        
    #tear down this webdriver    
    def tearDown(self, stayOpenAfterError):
        if ( stayOpenAfterError != 0 ):
            time.sleep(stayOpenAfterError)
        self.driver.quit()
        self.driver.stop_client()
        #self.logger.outhdlr.close()
            
    def sig_handler(self,sig):
        self.log.critical( 'caught signal:' + sig )
        self.tearDown(0)
         
    
    signal.signal(signal.SIGINT, sig_handler)
            

            
class LoginFailure(Exception):
    def __init__(self, value):
        self.value = value
    def __str__ (self):
        return repr(self.value)
            

                       

        
        
        
            
            
            
            
            
                