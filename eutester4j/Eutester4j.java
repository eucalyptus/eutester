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
import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import com.amazonaws.AmazonServiceException;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.services.autoscaling.AmazonAutoScaling;
import com.amazonaws.services.autoscaling.AmazonAutoScalingClient;
import com.amazonaws.services.autoscaling.model.CreateLaunchConfigurationRequest;
import com.amazonaws.services.autoscaling.model.DeleteLaunchConfigurationRequest;
import com.amazonaws.services.autoscaling.model.DescribeLaunchConfigurationsRequest;
import com.amazonaws.services.autoscaling.model.DescribeLaunchConfigurationsResult;
import com.amazonaws.services.autoscaling.model.LaunchConfiguration;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.AmazonEC2Client;
import com.amazonaws.services.ec2.model.CreateKeyPairRequest;
import com.amazonaws.services.ec2.model.CreateSecurityGroupRequest;
import com.amazonaws.services.ec2.model.DeleteKeyPairRequest;
import com.amazonaws.services.ec2.model.DeleteSecurityGroupRequest;
import com.amazonaws.services.ec2.model.DescribeInstancesResult;
import com.amazonaws.services.ec2.model.DescribeKeyPairsRequest;
import com.amazonaws.services.ec2.model.DescribeKeyPairsResult;
import com.amazonaws.services.ec2.model.DescribeSecurityGroupsRequest;
import com.amazonaws.services.ec2.model.DescribeSecurityGroupsResult;
import com.amazonaws.services.ec2.model.Instance;
import com.amazonaws.services.ec2.model.Reservation;
import com.amazonaws.services.ec2.model.RunInstancesRequest;
import com.amazonaws.services.ec2.model.SecurityGroup;
import com.amazonaws.services.ec2.model.StartInstancesRequest;
import com.amazonaws.services.ec2.model.StopInstancesRequest;
import com.amazonaws.services.ec2.model.TerminateInstancesRequest;

/**
 * @author tony
 *
 */
abstract class Eutester4j {
	
	/**
	 * @param ec2 the ec2 to set
	 */
	public static AmazonEC2 setEc2(AWSCredentials credentials) {
		return new AmazonEC2Client(credentials);
	}
	
	/**
	 * create ec2 connection based with supplied accessKey and secretKey
	 * 
	 * @param accessKey
	 * @param secretKey
	 */
	public static AmazonEC2 ec2Connection(String accessKey, String secretKey) {
		AWSCredentials creds = new BasicAWSCredentials(accessKey,secretKey);
		return setEc2(creds);
	}

	/**
	 * 
	 * @param name
	 * @param desc
	 */
	public static void createSecurityGoup(AmazonEC2 ec2, String name, String desc) {
		try {
        	CreateSecurityGroupRequest securityGroupRequest = new CreateSecurityGroupRequest(name, desc);
        	ec2.createSecurityGroup(securityGroupRequest);
    	} catch (AmazonServiceException ase) {
    		// Likely this means that the group is already created, so ignore.
    		System.out.println(ase.getMessage());
    	}
	}
	
	/**
	 * 
	 * @return list of security groups
	 */
	public static List<SecurityGroup> describeSecurityGroups(AmazonEC2 ec2) {
		DescribeSecurityGroupsResult securityGroupsResult = null;
		try {
			DescribeSecurityGroupsRequest describeSecurityGroupsRequest = new DescribeSecurityGroupsRequest();
			securityGroupsResult = ec2.describeSecurityGroups(describeSecurityGroupsRequest);
    	} catch (AmazonServiceException ase) {
    		// Likely this means that the group is already created, so ignore.
    		System.out.println(ase.getMessage());
    	}
    	return securityGroupsResult.getSecurityGroups();
	}
	
	/**
	 * 
	 * @param groupName security group to delete
	 */
	public static void deleteSecurityGroup(AmazonEC2 ec2, String groupName) {
		try {
			DeleteSecurityGroupRequest deleteSecurityGroupRequest = new DeleteSecurityGroupRequest(groupName);
			ec2.deleteSecurityGroup(deleteSecurityGroupRequest);
		} catch (AmazonServiceException ase) {
			System.out.println(ase.getMessage());
		}
	}
	
	/**
	 * @return a random Long hex number as a String
	 */
	public static String genRandomString() {
		return Long.toHexString(Double.doubleToLongBits(Math.random()));
	}
	

	/**
	 *	
	 * @param ec2
	 * @param emi
	 * @param keyName
	 * @param type
	 * @param securityGroups
	 */
	public static void runInstances(AmazonEC2 ec2, String emi, String keyName, String type, ArrayList<String> securityGroups, int minCount, int maxCount) {
		RunInstancesRequest runInstancesRequest = new RunInstancesRequest()
		    .withInstanceType(type)
		    .withImageId(emi)
		    .withMinCount(minCount)
		    .withMaxCount(maxCount)
		    .withSecurityGroups(securityGroups)
		    .withKeyName(keyName)
		;	
		ec2.runInstances(runInstancesRequest);
	}
	
	/**
	 * 
	 * @param ec2
	 * @param instanceIds
	 */
	public static void stopInstances(AmazonEC2 ec2, List<String> instanceIds) {
		StopInstancesRequest stopInstancesRequest = new StopInstancesRequest(instanceIds);
		ec2.stopInstances(stopInstancesRequest);
	}
	
	/**
	 * 
	 * @param ec2
	 * @param instanceIds
	 */
	public static void startInstances(AmazonEC2 ec2, List<String> instanceIds) {
		StartInstancesRequest startInstancesRequest = new StartInstancesRequest(instanceIds);
		ec2.startInstances(startInstancesRequest);
	}
	
	/**
	 * 
	 * @param ec2
	 * @param instanceIds
	 */
	public static void terminateInstances(AmazonEC2 ec2, List<String> instanceIds) {
		TerminateInstancesRequest terminateInstancesRequest = new TerminateInstancesRequest(instanceIds);
		ec2.terminateInstances(terminateInstancesRequest);
	}
	
	/**
	 * 
	 * @param ec2
	 * @return # of reservations
	 */
	public static List<Reservation> getInstancesList(AmazonEC2 ec2) {
		DescribeInstancesResult describeInstancesRequest = ec2.describeInstances();
        List<Reservation> reservations = describeInstancesRequest.getReservations();
		return reservations;
	}
	
	/**
	 * 
	 * @param ec2
	 * @param keyName
	 */
	public static void createKeyPair(AmazonEC2 ec2, String keyName) {
		CreateKeyPairRequest createKeyPairRequest = new CreateKeyPairRequest(keyName);
		ec2.createKeyPair(createKeyPairRequest);
	}
	
	/**
	 * 
	 * @param ec2
	 * @return
	 */
	public static int getKeyPairCount(AmazonEC2 ec2) {
		DescribeKeyPairsRequest describeKeyPairsRequest = new DescribeKeyPairsRequest();
		DescribeKeyPairsResult describeKeyPairsResult = ec2.describeKeyPairs(describeKeyPairsRequest);
		return describeKeyPairsResult.getKeyPairs().size();
	}
	
	/**
	 * 
	 * @param ec2
	 * @param keyName
	 */
	public static void deleteKeyPair(AmazonEC2 ec2, String keyName) {
		DeleteKeyPairRequest deleteKeyPairRequest = new DeleteKeyPairRequest(keyName);
		ec2.deleteKeyPair(deleteKeyPairRequest);
	}
	
	/**
	 * gets the number of instances that are in the supplied state
	 * states are strings such as: running, stopped, terminated
	 * 
	 * @param ec2
	 * @param state
	 * @return
	 */
	public static int getInstanceStateCount(AmazonEC2 ec2, String state){
		int count = 0;
		List <Reservation> reservations = getInstancesList(ec2);
        for (Reservation reservation : reservations){
             List <Instance> instancelist = reservation.getInstances();
             for (Instance instance:instancelist){
                 if (instance.getState().getName().equals(state)){
                	count++; 
                 }
             }     
        }
        return count;
	}
	
	/**
	 * 
	 * @param ec2
	 * @return
	 */
	public static List<Instance> getLastlaunchedInstance(AmazonEC2 ec2) {
		List <Instance> instancelist = null;
		List <Reservation> reservations = getInstancesList(ec2);
		for (Reservation reservation : reservations){
            instancelist = reservation.getInstances();
		    Collections.sort(instancelist, new Comparator<Instance>() {
		       public int compare(Instance i1, Instance i2) {
		          return i1.getInstanceId().compareTo(i2.getInstanceId());
		       }
		    });
		}
		return instancelist;		
	}
	
	/**
	 * helper method to pause execution
	 * 
	 * @param secs time to sleep in seconds
	 */
	public static void sleep(int secs) {
		try {
			Thread.sleep(secs * 1000);
		} catch (InterruptedException e) {
			e.printStackTrace();
		}
	}
	
	/**
	 * Used to get the state (as a String) of an instance
	 * 
	 * @param ec2
	 * @param instanceIds
	 * @return the state of an instance
	 */
	public static String getInstanceStateName(AmazonEC2 ec2, List<String> instanceIds){
		return getLastlaunchedInstance(ec2).get(0).getState().getName();
	}
	
	/**
	 * 
	 * @param credpath
	 * @param field
	 * @return the value of the field from eucarc file
	 * @throws IOException
	 */
	public static String parseEucarc(String credpath, String field) throws IOException{
		Charset charset = Charset.forName("UTF-8");
		String creds = credpath;
		String result = null;
		try {
			 List<String> lines = Files.readAllLines(Paths.get(creds), charset);
			 CharSequence find = field;
			 for (String line : lines){
				 if (line.contains(find)){
					 result = line.substring(line.lastIndexOf('=') + 1);
					 break;
				 }
			 }
		} catch (IOException ioe) {
			ioe.printStackTrace();
		}
		return result;
	}

	
/*****************************************************************************************
 * 
 * AUTO SCALING STUFF EXPERIMENTAL
 * 
 * TODO: document and test
 * 
 *****************************************************************************************/
	
	public static AmazonAutoScaling setAS(AWSCredentials credentials) {
		return new AmazonAutoScalingClient(credentials);
	}
	
	public static AmazonAutoScaling asConnection(String accessKey, String secretKey) {
		AWSCredentials creds = new BasicAWSCredentials(accessKey,secretKey);
		return setAS(creds);
	}
	
	public static void createLaunchConfig(AmazonAutoScaling as, String launchConfigurationName, String imageId, String type, String keyName, ArrayList<String> securityGroups){
		CreateLaunchConfigurationRequest createLaunchConfigurationRequest = new CreateLaunchConfigurationRequest()
		    .withLaunchConfigurationName(launchConfigurationName)
			.withImageId(imageId)
		    .withInstanceType(type)
		    .withSecurityGroups(securityGroups)
		    .withKeyName(keyName);
		as.createLaunchConfiguration(createLaunchConfigurationRequest);
	}
	
	public static List<LaunchConfiguration> describeLaunchConfigs(AmazonAutoScaling as) {
		DescribeLaunchConfigurationsResult launchConfigurationsResult = null;
		try {
			DescribeLaunchConfigurationsRequest describeLaunchConfigurationsRequest = new DescribeLaunchConfigurationsRequest();
			launchConfigurationsResult = as.describeLaunchConfigurations(describeLaunchConfigurationsRequest);
			System.out.println("LC size = " + launchConfigurationsResult.getLaunchConfigurations().size());
    	} catch (AmazonServiceException ase) {
    		System.out.println(ase.getMessage());
    	}
		return launchConfigurationsResult.getLaunchConfigurations();
	}
	
	public static void deleteLaunchConfig(AmazonAutoScaling as, String launchConfigurationName){
		try {
			DeleteLaunchConfigurationRequest deleteLaunchConfigurationRequest = new DeleteLaunchConfigurationRequest()
				.withLaunchConfigurationName(launchConfigurationName);
			as.deleteLaunchConfiguration(deleteLaunchConfigurationRequest);
		} catch (AmazonServiceException ase) {
			System.out.println(ase.getMessage());
		}
	}
	
}
