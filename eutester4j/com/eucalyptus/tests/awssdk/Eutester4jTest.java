/**
 * Software License Agreement (BSD License)
 *
 * Copyright (c) 2009-2013, Eucalyptus Systems, Inc.
 * All rights reserved.
 *
 * Redistribution and use of this software in source and binary forms, with or
 * without modification, are permitted provided that the following conditions
 * are met:
 *
 *   Redistributions of source code must retain the above
 *   copyright notice, this list of conditions and the
 *   following disclaimer.
 *
 *   Redistributions in binary form must reproduce the above
 *   copyright notice, this list of conditions and the
 *   following disclaimer in the documentation and/or other
 *   materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 * 
 * @author tony
 */

package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

import org.testng.annotations.AfterClass;
import org.testng.annotations.Test;
import org.testng.annotations.BeforeClass;
import org.testng.AssertJUnit;

import java.util.ArrayList;
import java.util.List;
import com.amazonaws.services.autoscaling.AmazonAutoScaling;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.model.DescribeAvailabilityZonesResult;
import com.amazonaws.services.ec2.model.SecurityGroup;
import com.amazonaws.services.autoscaling.model.LaunchConfiguration;

/**
 * At this time eucarc path needs to be hard coded. 
 * emi/ami an available image to use for creating instances (Required)
 * To test AWS or Euca comment out the lines for the one you do not want to 
 * test ie. "//euca" lines and uncomment the one you do ie. the "//AWS" lines
 */
public class Eutester4jTest {
	
	private static AmazonEC2 ec2;
	private static AmazonAutoScaling as;
	private static String ec2Endpoint = null;
	private static String asEndpoint = null;
	private static String secretKey = null;
	private static String accessKey= null;
	private static String credpath = null;
	
	private static String secGroupName = "TestGroup-" + eucaUUID();
	private static String secGroupDesc = "TestDesc-" + eucaUUID();
	private static String keyName = "TestKey-" + eucaUUID();
	private static ArrayList<String> securityGroups = new ArrayList<String>();

	/*
	 * for testing against euca cloud
	 */
//	private static String emi = "emi-52F13945"; //euca an emi you have access to
//	private static String type = "m1.small"; //euca
	
	/*
	 * for testing against AWS
	 */
	private static String type = "t1.micro"; //AWS
	private static String emi = "ami-921f3fd7"; //AWS an ami you have access to
	
	/**
	 * Called once, before the first test is run. Creates an ec2 connection.
     * 
	 * @throws java.lang.Exception
	 */
	@BeforeClass
	public static void setUpBeforeClass() throws Exception {
		
		/*
		 * For testing against Eucacloud
		 */
		credpath = "/Users/tony/Desktop/as_test_cloud/eucarc"; //euca
		secretKey = parseEucarc(credpath, "EC2_SECRET_KEY").replace("'", ""); //euca
		accessKey = parseEucarc(credpath, "EC2_ACCESS_KEY").replace("'", ""); //euca
		ec2Endpoint = parseEucarc(credpath, "EC2_URL")+"/"; //euca
		asEndpoint = parseEucarc(credpath, "AWS_AUTO_SCALING_URL") + "/"; //euca
		ec2 = getEc2Client(accessKey, secretKey, ec2Endpoint);
		as = getAutoScalingClient(accessKey, secretKey, asEndpoint);
//		ec2 = ec2Connection(accessKey,secretKey); //euca
//		as = asConnection(accessKey, secretKey); //euca
		
		/*
		 * For testing against AWS
		 */
//		AWSCredentials credentials = new PropertiesCredentials(
//                Eutester4j.class.getResourceAsStream("AwsCredentials.properties")); //AWS
//		ec2 = new AmazonEC2Client(credentials); //AWS
//		as = new AmazonAutoScalingClient(credentials); //AWS
//		ec2Endpoint = "http://ec2.us-west-1.amazonaws.com"; //AWS
//		asEndpoint = "http://autoscaling.us-west-1.amazonaws.com"; //AWS
//		secretKey = credentials.getAWSSecretKey(); //AWS
//		accessKey = credentials.getAWSAccessKeyId(); //AWS
		
//		ec2.setEndpoint(ec2Endpoint);
//		as.setEndpoint(asEndpoint);
		createSecurityGoup(ec2, secGroupName, secGroupDesc);
		createKeyPair(ec2, keyName);
		securityGroups.add(secGroupName);
	}

	/**
     * Called after all the tests in a class
     *
	 * @throws java.lang.Exception
	 */
	@AfterClass
	public static void tearDownAfterClass() throws Exception {
//		sleep(60); // give the system a chance to complete test actions
		deleteKeyPair(ec2, keyName);
		deleteSecurityGroup(ec2, secGroupName);
		ec2 = null;
		as=null;
		secretKey = null;
		accessKey = null;
		ec2Endpoint = null;
		asEndpoint = null;
	}

//	/*
//	 * Test that invalid access key prevents execution of ec2 commands. There should be an exception caught
//	 * After the test, credentials are reset to values present before the test ran.
//	 */
//	@Test(enabled=true)
//	public void testInvalidAccessKey() {
//		ec2Connection("badAccessKey", secretKey);
//		try {
//			ec2.describeAvailabilityZones();
//		} catch (Exception e) {
//			AssertJUnit.assertTrue(e.getMessage().length() > 0);
//		} finally {
//			ec2Connection(accessKey, secretKey);
//		}
//	}
//	
//	/*
//	 * Test that invalid secret key prevents execution of ec2 commands. There should be an exception caught.
//	 * After the test, credentials are reset to values present before the test ran
//	 */
//	@Test(enabled=true)
//	public void testInvalidSecretKey() {
//		ec2Connection(accessKey, "badSecretKey");
//		try {
//			ec2.describeAvailabilityZones();
//		} catch (Exception e) {
//			AssertJUnit.assertTrue(e.getMessage().length() > 0);
//		} finally {
//			ec2Connection(accessKey, secretKey);
//		}
//	}
	
	/*
	 * Test that valid credentials have a successful connection by verifying
	 * a simple ec2 command (describeAvalabilityZones) returns some zones
	 */
	@Test(enabled=true)
	public void testGoodCreds() {
		DescribeAvailabilityZonesResult availabilityZonesResult = ec2.describeAvailabilityZones();
		AssertJUnit.assertTrue(availabilityZonesResult.getAvailabilityZones().size() >= 1);
	}
	
	/**
	 * Test that security group can be created then deletes the group
	 */
	@Test(enabled=true)
	public void testCreateSecurityGroup() {
		String name = eucaUUID();
		String desc = eucaUUID();
		
		List<SecurityGroup> secGroups = describeSecurityGroups(ec2);
		int initialSize = secGroups.size();
	
		try {
			createSecurityGoup(ec2, name, desc);
			secGroups = describeSecurityGroups(ec2);
			AssertJUnit.assertTrue(secGroups.size() > initialSize);
		} catch (Exception e) {
			e.printStackTrace();
		} finally {
			deleteSecurityGroup(ec2, name);
		}
	}
	
	/**
	 * Test that security group can be deleted
	 */
	@Test(enabled=true)
	public void testDeleteSecurityGroup() {
		String name = eucaUUID();
		String desc = eucaUUID();
	
		try {
			createSecurityGoup(ec2, name, desc);
			
			List<SecurityGroup> secGroups = describeSecurityGroups(ec2);
			int initialSize = secGroups.size();
			
			deleteSecurityGroup(ec2, name);
			secGroups = describeSecurityGroups(ec2);
			AssertJUnit.assertTrue(secGroups.size() < initialSize);
		} catch (Exception e) {
			e.printStackTrace();
		}
	}
	
	/**
	 * Test running instances also tests get instance count
	 */
	@Test(enabled=false)
	public void testRunInstances(){
		int initalInstanceCount = getInstancesList(ec2).size();
		runInstances(ec2, emi, keyName, type, securityGroups, 1, 1);
		AssertJUnit.assertTrue(getInstancesList(ec2).size() > initalInstanceCount);
		
		// terminate after the test
		List<String> instanceIds = new ArrayList<String>();
		instanceIds.add(getLastlaunchedInstance(ec2).get(0).getInstanceId());
		System.out.println("Going to terminate " + getLastlaunchedInstance(ec2).get(0).getInstanceId());
		terminateInstances(ec2, instanceIds);
		System.out.println("Terminate requested");

	}
	
//	/**
//	 * test stopping instances (bfebs image required)
//	 *
//	 * appears there is a compatibility issue with euca supporting getState() for instances
//	 * it is always returning null
//	 */
//	@Test(enabled=false)
//	public void testStopInstances(){
//		runInstances(ec2, emi, keyName, type, securityGroups, 1, 1);
//		List<String> instanceIds = new ArrayList<String>();
//		instanceIds.add(getLastlaunchedInstance(ec2).get(0).getInstanceId());
//		System.out.println("State Check 1: " + getInstanceStateName(ec2, instanceIds));
//		while(!getLastlaunchedInstance(ec2).get(0).getState().getName().equals("running")){}
//		System.out.println("State Check 2: " + getInstanceStateName(ec2, instanceIds));
//		stopInstances(ec2, instanceIds);
//		System.out.println("State Check 3: " + getInstanceStateName(ec2, instanceIds));
//		while(!getLastlaunchedInstance(ec2).get(0).getState().getName().equals("stopped")){}
//		System.out.println("State Check 4: " + getInstanceStateName(ec2, instanceIds));
//		AssertJUnit.assertTrue(getLastlaunchedInstance(ec2).get(0).getState().getName().equals("stopped"));
//		// after test terminate the instance
//		terminateInstances(ec2, instanceIds);
//		System.out.println("State Check 6: " + getInstanceStateName(ec2, instanceIds));
//	}
	
	/**
	 * test terminating
	 * 
	 * appears there is a compatibility issue with euca supporting getState() for instances
	 * it is always returning null
	 */
	@Test(enabled=false)
	public void testTerminateInstances(){
		runInstances(ec2, emi, keyName, type, securityGroups, 1, 1);
		List<String> instanceIds = new ArrayList<String>();
		instanceIds.add(getLastlaunchedInstance(ec2).get(0).getInstanceId());
		System.out.println("Created instance = " + getLastlaunchedInstance(ec2).get(0).getInstanceId());
		System.out.println("State: " + getLastlaunchedInstance(ec2).get(0).getState());
		System.out.println("State before terminate = " + getLastlaunchedInstance(ec2).get(0).getState().getName());
		terminateInstances(ec2, instanceIds);
		System.out.println("State after terminate = " + getLastlaunchedInstance(ec2).get(0).getState().getName());
		while(!getLastlaunchedInstance(ec2).get(0).getState().getName().equals("terminated")){}
		AssertJUnit.assertTrue(getLastlaunchedInstance(ec2).get(0).getState().getName().equals("terminated"));
	}
	
	/**
	 * Tests createKeyPair, getKeyPairCount and deleteKeyPair
	 */
	@Test(enabled=true)
	public void testCreateKeyPair() {
		String keyName = "test key";
		int initialKeyPairCount = getKeyPairCount(ec2);
		createKeyPair(ec2, keyName);
		AssertJUnit.assertTrue(getKeyPairCount(ec2) > initialKeyPairCount);
		deleteKeyPair(ec2, keyName);
	}
	
	/**
	 * Tests create, describe and delete launch configurations
	 */
	@Test(enabled=true)
	public void testBasicLaunchConfig(){
		String launchConfigurationName = "LC-" + eucaUUID();
		try {
			createLaunchConfig(as, launchConfigurationName, emi, type, keyName, securityGroups);
			
			List<LaunchConfiguration> launchConfigs = describeLaunchConfigs(as);
			
			int initialSize = launchConfigs.size();
			deleteLaunchConfig(as, "LC-3fd0d59cd39bf7fc");
			deleteLaunchConfig(as, launchConfigurationName);
			launchConfigs = describeLaunchConfigs(as);
			AssertJUnit.assertTrue(launchConfigs.size() < initialSize);
		} catch (Exception e) {
			e.printStackTrace();
		}
	}
}
