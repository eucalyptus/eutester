#!/usr/bin/python
'''
Created on Nov 10, 2011

@author: clarkmatthew
'''

from eucaweb import Eucaweb, euwebuser, euwebaccount,euwebglobals
import time

if __name__ == '__main__':
    wg = euwebglobals.Webui_globals()
    ret = 0
    try:
        user = euwebuser.Euwebuser()
        a = euwebaccount.Euwebaccount()
        gui = Eucaweb("localhost","FIREFOX","192.168.51.9","admin")
        #gui.signUpUser(user.account, user.user, user.passwd, user.email)
        gui.login()
        accounts = gui.getAccountList()
        for a in accounts:
            a.printSelf()
            gui.clickButtonXpathAndVerify(a.id_xpath,a.name)
            navname= gui.getAccountsRightNavValueByName(wg.AccountsRightNav_Name)
            if (not navname):
                print "Ouch nav is missing"
            else:
                print "navname is:"+navname
                if (navname == a.name):
                    print "Matched name in right nav"+navname
            regstat = gui.getAccountsRightNavValueByName(wg.AccountsRightNav_RegStatus)
            if (not regstat):
                print "regstat is missing"
            else:
                if (regstat == wg.Registered):
                    print "were Registered"
                elif ( regstat == wg.Confirmed):
                    print "were Confirmed"
                else:
                    raise Exception("WHAT status is this?"+regstat)
            #time.sleep(1)
        print "ALL GOOD HERE"
    except Exception, e:
        print "Caught Error:" + str(e)
        ret = 1
    finally:
        try:
            print "Tearing down the gui..."
            gui.tearDown(0)
        except NameError:
            print "Couldnt tear down the gui..."
            exit (ret)
            
