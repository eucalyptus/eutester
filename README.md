eutester version 0.0.5
======================

[Intro to Eutester](http://testingclouds.wordpress.com/2012/03/04/test1/)

[Video - Eutester Overview: An Introduction to the Functional Testing Framework for Eucalyptus](http://vimeo.com/51627165)

[Getting Setup](http://testingclouds.wordpress.com/2012/03/29/eutester-basics-part-ii-setting-up-a-development-environment/)

[Writing Your First Testcase](http://testingclouds.wordpress.com/2012/04/02/eutester-basics-part-iii-creating-your-first-testcase/)

[Guidelines for Contributing Testcases](https://github.com/eucalyptus/eutester/wiki/Guidelines-for-Contributing-Test-Cases)

[Creating a Eucalyptus Test Harness: Jenkins, Testlink, and Eutester](http://testingclouds.wordpress.com/2012/10/01/creating-a-eucalyptus-test-harness-jenkinstestlink-and-eutester/)

[Eutester Documentation on packages.python.org](http://packages.python.org/eutester/)

eutester is an attempt to leverage existing test code to make test writing faster and standardized.  

Installation
------
If easy_install is not available in your environment use your package manager to install python-setuptools
    
    yum install python-setuptools gcc python-devel git
    apt-get install python-setuptools gcc python-dev git

Installing eutester and its dependencies is as easy as:

    easy_install eutester

For development purposes you can then clone the code from github and then reinstall with your changes

    git clone https://github.com/eucalyptus/eutester.git
    cd eutester
    [CHANGE CODE]
    python setup.py install

Main Classes
------
eutester contains the framework pieces like parsing config/creds, setting up connections and providing test primitives.
eucaops uses the framework provided by eutester to provide validated higher order operations on those cloud connections.
For more information regarding the module structure of eutester, please refer to the [Eutester Python Module Documentation Index](http://packages.python.org/eutester/py-modindex.html).

![class-diagram](https://s3.amazonaws.com/vic-bucket/eutester-class-diagram.jpg)

Example test cases written with this library can be found in the testcases/unstable directory of the source tree

Design
------

Eutester is designed to allow a user to quickly generate automated tests for testing a Eucalyptus or Amazon cloud. In the case of testing a private cloud a configuration file can be used to create cases that require root access to the machines.
The config file describes a few things about the clouds configuration including the bare metal machine configuration and IPs.

The `eucaops` class can be imported in order to use pre-defined routines which validate common operations on the cloud:

    from eucaops import Eucaops

Constructor
------

The basic constructor can be used for 2 different connections:

1. Private cloud with root access - CLC SSH, Cloud, and Walrus connections  
    Purpose - connect to and manipulate Eucalyptus components using boto and command line. Recommended to use Eucaops.  
    Required arguments: root password, config file with topology information  
    Optional arguments: credential path so that new credentials are not created

        private_cloud = Eucaops( password="my_root_pass",  config_file="cloud.conf")
        private_cloud.sys("euca-describe-availability-zones") ### use local credentials to determine viable availability-zones
        
        
2. Public cloud - local SSH, EC2 and S3 connections  
    Purpose - can be used to wrap euca2ools commands installed locally on the tester machine or with Eucaops  
    Required arguments: credential path

        public_cloud = Eucaops(credpath="~/.eucarc")    
        public_cloud.run_instance(image) ## run an m1.small instance using image
        
            
 
Config file
----------
    NETWORK MANAGED
    clc.mydomain.com CENTOS 5.7 64 REPO [CC00 CLC SC00 WS]    
    nc1.mydomain.com VMWARE ESX-4.0 64 REPO [NC00]

Network
------
Possible values are MANAGED, MANAGED-NOVLAN, SYSTEM, or STATIC

Columns
------ 
    IP or hostname of machine  
    Distro installed on machine  
    Distro version on machine  
    Distro base architecture
    System built from packages (REPO) or source (BZR), packages assumes path to eucalyptus is /, bzr assumes path to eucalyptus is /opt/eucalyptus
    List of components installed on this machine encapsulated in brackets []

These components can be:

    CLC - Cloud Controller   
    WS - Walrus   
    SC00 - Storage controller for cluster 00   
    CC00 - Cluster controller for cluster 00    
    NC00 - A node controller in cluster 00   
