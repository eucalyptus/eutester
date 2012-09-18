CSS: style.css

# Test Case Submission Framework

1.  Do a fork of Eucalyptus eutester project (requires github account for information on how to set up a Github account, refer to the following URL: [http://help.github.com/set-up-git-redirect/](http://help.github.com/set-up-git-redirect/)).  On information on how to fork a project, refer to the following link: [http://help.github.com/fork-a-repo/](http://help.github.com/fork-a-repo/).

2.  Clone eutester project from user's github account (example can be seen here =>  [hspencer77/eutester](https://github.com/hspencer77/eutester)) and checkout the testing branch:
	git clone git@github.com:"github-username"/eutester.git
	git checkout testing

3.  Create tester case.  There are two descriptions that are needed:
	1.  Description in script:  Top of the script => # Description section; comments in code is required.
	2.  Test cases should be based off of the test case template found in the eutester repo
	3.  Wiki page in user's forked project of eutester (example here [https://github.com/hspencer77/eutester/wiki/clusterbasics](https://github.com/hspencer77/eutester/wiki/clusterbasics))

4.  All test cases go under eutester/testcases/ directory structure. Tests that can be run using only credentials (ie do not require access to Eucalyptus component machines) should be placed in the cloud_user folder. Test cases requiring root access to any of the components should be placed in the cloud_admin folder.  **It would be helpful if name of test case script reflected what test the script is actually doing.**

5.  Once the test case is ready, do a pull request to the eutester project.  For information on how to do a pull request in Github, refer to the following help link: [http://help.github.com/send-pull-requests/](http://help.github.com/send-pull-requests/).

If there are any questions on how to set up eutester and create a test case script, please refer to the following blog:  [http://testingclouds.wordpress.com/](http://testingclouds.wordpress.com/).  