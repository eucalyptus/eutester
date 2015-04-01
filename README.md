Eutester
======================

[![Build Status](https://secure.travis-ci.org/eucalyptus/eutester.png)](https://travis-ci.org/eucalyptus/eutester)

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


### Branches
Eutester vs. Eucalyptus compatibility matrix:

A new version of Eutester is released with every new version of Eucalyptus and the
compatibility matrix goes as the following pattern: 

| Eutester Version | Eucalyptus Version |
|------------------|--------------------|
| 1.2.0            | 4.2.0              |
| 1.2.1            | 4.2.1              |
| 1.3.0            | 4.3.0              |
| 1.3.1            | 4.3.1              |
| 2.0.0            | 5.0.0              |
| u.y.y            | x.y.y              |


For developers and testers, the compatibility matrix is little different than using
Eucalyptus from official release. In this case Eutester will use the same branch names
as Eucalyptus:

| Eutester Branch | Eucalyptus Branch |
| ----------------|-------------------|
| master          | master            |
| maint-4.1       | maint-4.1         |
| maint-4.2       | maint-4.2         |


Main Classes
------
eutester contains the framework pieces like parsing config/creds, setting up connections and providing test primitives.
`Eucaops` uses the framework provided by eutester to provide validated higher order operations on those cloud connections.
For more information regarding the module structure of eutester, please refer to the [Eutester Python Module Documentation Index](http://packages.python.org/eutester/py-modindex.html).

![class-diagram](https://dl.dropboxusercontent.com/u/5458574/eutester-class-diagram.png)

Example test cases written with this library can be found in the testcases/unstable directory of the source tree

Design
------

Eutester is designed to allow a user to quickly generate automated tests for testing a Eucalyptus or Amazon cloud.
In the case of testing a private cloud a configuration file can be used to create cases that require root access to
the machines. The config file describes a few things about the clouds configuration including the bare metal machine
configuration and IPs.

The `Eucaops` class can be imported in order to use pre-defined routines which validate common operations on the cloud:

    from eutester.euca.euca_ops import Eucaops

Constructor
------

The basic constructor can be used for 2 different connections:

1. Private cloud with root access - CLC SSH, Cloud, and Walrus connections
    Purpose - connect to and manipulate Eucalyptus components using boto and command line. Recommended to use Eucaops.  
    Required arguments: root password, config file with topology information
    Optional arguments: credential path so that new credentials are not created

        tester = Eucaops(password="foobar",  config_file="/root/input/2b_tested.lst")
        
        # Get all instances
        tester.ec2.get_instances()
        
        # Get all accounts
        tester.iam.get_all_accounts()
        
        
        
2. Public cloud - local SSH, EC2 and S3 connections
    Purpose - can be used to wrap euca2ools commands installed locally on the tester machine or with Eucaops
    Required arguments: credential path

        tester = Eucaops(credpath="~/.eucarc")
        tester.ec2.run_image(image) ## run an m1.small instance using image
        
            
 
Config file
----------
Example config file:
        
        NETWORK	EDGE
        10.10.1.1	CENTOS	6.5	64	REPO	[CLC]
        10.10.1.2	CENTOS	6.5	64	REPO	[WS]
        10.10.1.3	CENTOS	6.5	64	REPO	[CC00]
        10.10.1.4	CENTOS	6.5	64	REPO	[SC00]
        10.10.1.5	CENTOS	6.5	64	REPO	[NC00]
        10.10.1.6	CENTOS	6.5	64	REPO	[CC01]
        10.10.1.7	CENTOS	6.5	64	REPO	[SC01]
        10.10.1.8	CENTOS	6.5	64	REPO	[NC01]

Network
------
Possible values are EDGE, VPCMIDO, MANAGED, MANAGED-NOVLAN

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
    SC01 - Storage controller for cluster 01
    CC01 - Cluster controller for cluster 01
    NC01 - A node controller in cluster 01

