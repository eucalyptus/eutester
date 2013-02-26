package com.eucalyptus.tests.awssdk;

import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.TimeUnit;

import com.amazonaws.AmazonServiceException;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.services.autoscaling.AmazonAutoScaling;
import com.amazonaws.services.autoscaling.AmazonAutoScalingClient;
import com.amazonaws.services.autoscaling.model.AutoScalingGroup;
import com.amazonaws.services.autoscaling.model.AutoScalingInstanceDetails;
import com.amazonaws.services.autoscaling.model.CreateAutoScalingGroupRequest;
import com.amazonaws.services.autoscaling.model.CreateLaunchConfigurationRequest;
import com.amazonaws.services.autoscaling.model.DeleteAutoScalingGroupRequest;
import com.amazonaws.services.autoscaling.model.DeleteLaunchConfigurationRequest;
import com.amazonaws.services.autoscaling.model.DescribeAutoScalingGroupsRequest;
import com.amazonaws.services.autoscaling.model.DescribeAutoScalingGroupsResult;
import com.amazonaws.services.autoscaling.model.DescribeAutoScalingInstancesRequest;
import com.amazonaws.services.autoscaling.model.DescribeAutoScalingInstancesResult;
import com.amazonaws.services.autoscaling.model.DescribeLaunchConfigurationsRequest;
import com.amazonaws.services.autoscaling.model.DescribeLaunchConfigurationsResult;
import com.amazonaws.services.autoscaling.model.LaunchConfiguration;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.AmazonEC2Client;
import com.amazonaws.services.ec2.model.AvailabilityZone;
import com.amazonaws.services.ec2.model.CreateKeyPairRequest;
import com.amazonaws.services.ec2.model.CreateSecurityGroupRequest;
import com.amazonaws.services.ec2.model.DeleteKeyPairRequest;
import com.amazonaws.services.ec2.model.DeleteSecurityGroupRequest;
import com.amazonaws.services.ec2.model.DescribeAvailabilityZonesResult;
import com.amazonaws.services.ec2.model.DescribeImagesRequest;
import com.amazonaws.services.ec2.model.DescribeImagesResult;
import com.amazonaws.services.ec2.model.DescribeInstancesRequest;
import com.amazonaws.services.ec2.model.DescribeInstancesResult;
import com.amazonaws.services.ec2.model.DescribeKeyPairsRequest;
import com.amazonaws.services.ec2.model.DescribeKeyPairsResult;
import com.amazonaws.services.ec2.model.DescribeSecurityGroupsRequest;
import com.amazonaws.services.ec2.model.DescribeSecurityGroupsResult;
import com.amazonaws.services.ec2.model.Filter;
import com.amazonaws.services.ec2.model.Instance;
import com.amazonaws.services.ec2.model.Reservation;
import com.amazonaws.services.ec2.model.RunInstancesRequest;
import com.amazonaws.services.ec2.model.SecurityGroup;
import com.amazonaws.services.ec2.model.StartInstancesRequest;
import com.amazonaws.services.ec2.model.StopInstancesRequest;
import com.amazonaws.services.ec2.model.TerminateInstancesRequest;
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancing;
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancingClient;

final class Eutester4j {

	static String EC2_ENDPOINT = null;
	static String AS_ENDPOINT = null;
	static String ELB_ENDPOINT = null;
	static String SECRET_KEY = null;
	static String ACCESS_KEY = null;
	static String CREDPATH = null;
	static String instanceType = "m1.small";

	public static void getCloudInfo() throws Exception {
		CREDPATH = "/Users/tony/Desktop/as_test_cloud/eucarc";
		EC2_ENDPOINT = parseEucarc(CREDPATH, "EC2_URL") + "/";
		AS_ENDPOINT = parseEucarc(CREDPATH, "AWS_AUTO_SCALING_URL") + "/";
		ELB_ENDPOINT = parseEucarc(CREDPATH, "AWS_ELB_URL") + "/";
		SECRET_KEY = parseEucarc(CREDPATH, "EC2_SECRET_KEY").replace("'", "");
		ACCESS_KEY = parseEucarc(CREDPATH, "EC2_ACCESS_KEY").replace("'", "");
	}

	/**
	 * create ec2 connection based with supplied accessKey and secretKey
	 * 
	 * @param accessKey
	 * @param secretKey
	 */
	public static AmazonEC2 getEc2Client(String accessKey, String secretKey,
			String endpoint) {
		AWSCredentials creds = new BasicAWSCredentials(accessKey, secretKey);
		final AmazonEC2 ec2 = new AmazonEC2Client(creds);
		ec2.setEndpoint(endpoint);
		return ec2;
	}

	public static AmazonAutoScaling getAutoScalingClient(String accessKey,
			String secretKey, String endpoint) {
		AWSCredentials creds = new BasicAWSCredentials(accessKey, secretKey);
		final AmazonAutoScaling as = new AmazonAutoScalingClient(creds);
		as.setEndpoint(endpoint);
		return as;
	}

	public static AmazonElasticLoadBalancing getElbClient(String accessKey, String secretKey,
			String endpoint) {
		AWSCredentials creds = new BasicAWSCredentials(accessKey, secretKey);
		final AmazonElasticLoadBalancing elb = new AmazonElasticLoadBalancingClient(creds);
		elb.setEndpoint(endpoint);
		return elb;
	}

	/**
	 * 
	 * @param credpath
	 * @param field
	 * @return the value of the field from eucarc file
	 * @throws IOException
	 */
	public static String parseEucarc(String credpath, String field)
			throws IOException {
		Charset charset = Charset.forName("UTF-8");
		String creds = credpath;
		String result = null;
		try {
			List<String> lines = Files.readAllLines(Paths.get(creds), charset);
			CharSequence find = field;
			for (String line : lines) {
				if (line.contains(find)) {
					result = line.substring(line.lastIndexOf('=') + 1);
					break;
				}
			}
		} catch (IOException ioe) {
			ioe.printStackTrace();
		}
		return result;
	}

	public static String eucaUUID() {
		return Long.toHexString(Double.doubleToLongBits(Math.random()));
	}

	public static void assertThat(boolean condition, String message) {
		assert condition : message;
	}

	public static void print(String text) {
		System.out.println(text);
	}

	/**
	 * helper method to pause execution
	 * 
	 * @param secs
	 *            time to sleep in seconds
	 */
	public static void sleep(int secs) {
		try {
			Thread.sleep(secs * 1000);
		} catch (InterruptedException e) {
			e.printStackTrace();
		}
	}

	public static void verifyInstanceHealthStatus(final AmazonAutoScaling as,
			final String instanceId, final String expectedStatus) {
		final String healthStatus = getHealthStatus(as, instanceId);
		assertThat(expectedStatus.equals(healthStatus), "Expected "
				+ expectedStatus + " health status");
	}

	public static void waitForHealthStatus(final AmazonAutoScaling as,
			final String instanceId, final String expectedStatus)
			throws Exception {
		final long startTime = System.currentTimeMillis();
		final long timeout = TimeUnit.MINUTES.toMillis(3);
		boolean completed = false;
		while (!completed && (System.currentTimeMillis() - startTime) < timeout) {
			Thread.sleep(5000);
			final String healthStatus = getHealthStatus(as, instanceId);
			completed = expectedStatus.equals(healthStatus);
		}
		assertThat(completed, "Instances health status did not change to "
				+ expectedStatus + " within the expected timeout");
		print("Instance health status changed in "
				+ (System.currentTimeMillis() - startTime) + "ms");
	}

	public static String getHealthStatus(final AmazonAutoScaling as,
			final String instanceId) {
		final DescribeAutoScalingInstancesResult instancesResult = as
				.describeAutoScalingInstances(new DescribeAutoScalingInstancesRequest()
						.withInstanceIds(instanceId));
		assertThat(instancesResult.getAutoScalingInstances().size() == 1,
				"Auto scaling instance found");
		final AutoScalingInstanceDetails details = instancesResult
				.getAutoScalingInstances().get(0);
		final String healthStatus = details.getHealthStatus();
		print("Health status: " + healthStatus);
		return healthStatus;
	}

	public static List<?> waitForInstances(final AmazonEC2 ec2,
			final long timeout, final int expectedCount,
			final String groupName, final boolean asString) throws Exception {
		final long startTime = System.currentTimeMillis();
		boolean completed = false;
		if (asString) {
			List<?> instanceIds = Collections.emptyList();
			while (!completed
					&& (System.currentTimeMillis() - startTime) < timeout) {
				Thread.sleep(5000);
				instanceIds = getInstancesForGroup(ec2, groupName, "running",
						true);
				completed = instanceIds.size() == expectedCount;
			}
			assertThat(completed, "Instances count did not change to "
					+ expectedCount + " within the expected timeout");
			print("Instance count changed in "
					+ (System.currentTimeMillis() - startTime) + "ms");
			return instanceIds;
		} else {
			List<?> instances = Collections.emptyList();
			while (!completed
					&& (System.currentTimeMillis() - startTime) < timeout) {
				Thread.sleep(5000);
				instances = getInstancesForGroup(ec2, groupName, "running",
						false);
				completed = instances.size() == expectedCount;
			}
			assertThat(completed, "Instances count did not change to "
					+ expectedCount + " within the expected timeout");
			print("Instance count changed in "
					+ (System.currentTimeMillis() - startTime) + "ms");
			return instances;
		}
	}

	public static List<?> getInstancesForGroup(final AmazonEC2 ec2,
			final String groupName, final String status, final boolean asString) {
		final DescribeInstancesResult instancesResult = ec2
				.describeInstances(new DescribeInstancesRequest()
						.withFilters(new Filter().withName(
								"tag:aws:autoscaling:groupName").withValues(
								groupName)));
		if (asString) {
			final List<String> instanceIds = new ArrayList<String>();
			for (final Reservation reservation : instancesResult
					.getReservations()) {
				for (final Instance instance : reservation.getInstances()) {
					if (status == null || instance.getState() == null
							|| status.equals(instance.getState().getName())) {
						instanceIds.add(instance.getInstanceId());
					}
				}
			}
			return instanceIds;
		} else {
			final List<Instance> instances = new ArrayList<Instance>();
			for (final Reservation reservation : instancesResult
					.getReservations()) {
				for (final Instance instance : reservation.getInstances()) {
					if (status == null || instance.getState() == null
							|| status.equals(instance.getState().getName())) {
						instances.add(instance);
					}
				}
			}
			return instances;
		}
	}

	public static String findImage(final AmazonEC2 ec2) {
		// Find an appropriate image to launch
		final DescribeImagesResult imagesResult = ec2
				.describeImages(new DescribeImagesRequest().withFilters(
						new Filter().withName("image-type").withValues(
								"machine"),
						new Filter().withName("root-device-type").withValues(
								"instance-store")));

		assertThat(imagesResult.getImages().size() > 0, "Image not found");

		final String imageId = imagesResult.getImages().get(0).getImageId();
		print("Using image: " + imageId);
		return imageId;
	}

	public static String findAvalablityZone(final AmazonEC2 ec2) {
		// Find an AZ to use
		final DescribeAvailabilityZonesResult azResult = ec2
				.describeAvailabilityZones();

		assertThat(azResult.getAvailabilityZones().size() > 0,
				"Availability zone not found");

		final String availabilityZone = azResult.getAvailabilityZones().get(0)
				.getZoneName();
		print("Using availability zone: " + availabilityZone);
		return availabilityZone;
	}

	public static List<AvailabilityZone> getAZ(AmazonEC2 ec2) {
		// Find an AZ to use
		final DescribeAvailabilityZonesResult azResult = ec2
				.describeAvailabilityZones();

		assertThat(azResult.getAvailabilityZones().size() > 0,
				"Availability zone not found");

		return azResult.getAvailabilityZones();
	}

	/**
	 * 
	 * @param name
	 * @param desc
	 */
	public static void createSecurityGoup(AmazonEC2 ec2, String name,
			String desc) {
		try {
			CreateSecurityGroupRequest securityGroupRequest = new CreateSecurityGroupRequest(
					name, desc);
			ec2.createSecurityGroup(securityGroupRequest);
			System.out.println("Created Security Group: " + name);
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
			securityGroupsResult = ec2
					.describeSecurityGroups(describeSecurityGroupsRequest);
		} catch (AmazonServiceException ase) {
			// Likely this means that the group is already created, so ignore.
			System.out.println(ase.getMessage());
		}
		return securityGroupsResult.getSecurityGroups();
	}

	/**
	 * 
	 * @param groupName
	 *            security group to delete
	 */
	public static void deleteSecurityGroup(AmazonEC2 ec2, String groupName) {
		try {
			DeleteSecurityGroupRequest deleteSecurityGroupRequest = new DeleteSecurityGroupRequest(
					groupName);
			ec2.deleteSecurityGroup(deleteSecurityGroupRequest);
			System.out.println("Deleted Security Group: " + groupName);
		} catch (AmazonServiceException ase) {
			System.out.println(ase.getMessage());
		}
	}

	/**
	 * 
	 * @param ec2
	 * @param emi
	 * @param keyName
	 * @param type
	 * @param securityGroups
	 */
	public static void runInstances(AmazonEC2 ec2, String emi, String keyName,
			String type, ArrayList<String> securityGroups, int minCount,
			int maxCount) {
		RunInstancesRequest runInstancesRequest = new RunInstancesRequest()
				.withInstanceType(type).withImageId(emi).withMinCount(minCount)
				.withMaxCount(maxCount).withSecurityGroups(securityGroups)
				.withKeyName(keyName);
		ec2.runInstances(runInstancesRequest);
		System.out.println("Started instance: "
				+ getLastlaunchedInstance(ec2).get(0).getInstanceId());
	}

	/**
	 * 
	 * @param ec2
	 * @param instanceIds
	 */
	public static void stopInstances(AmazonEC2 ec2, List<String> instanceIds) {
		StopInstancesRequest stopInstancesRequest = new StopInstancesRequest(
				instanceIds);
		ec2.stopInstances(stopInstancesRequest);
		for (String instance : instanceIds) {
			System.out.println("Stopped instance: " + instance);
		}
	}

	/**
	 * 
	 * @param ec2
	 * @param instanceIds
	 */
	public static void startInstances(AmazonEC2 ec2, List<String> instanceIds) {
		StartInstancesRequest startInstancesRequest = new StartInstancesRequest(
				instanceIds);
		ec2.startInstances(startInstancesRequest);
		for (String instance : instanceIds) {
			System.out.println("Started instance: " + instance);
		}
	}

	/**
	 * 
	 * @param ec2
	 * @param instanceIds
	 */
	public static void terminateInstances(AmazonEC2 ec2,
			List<String> instanceIds) {
		TerminateInstancesRequest terminateInstancesRequest = new TerminateInstancesRequest(
				instanceIds);
		ec2.terminateInstances(terminateInstancesRequest);
		for (String instance : instanceIds) {
			System.out.println("Terminated instance: " + instance);
		}
	}

	/**
	 * 
	 * @param ec2
	 * @return # of reservations
	 */
	public static List<Reservation> getInstancesList(AmazonEC2 ec2) {
		DescribeInstancesResult describeInstancesRequest = ec2
				.describeInstances();
		List<Reservation> reservations = describeInstancesRequest
				.getReservations();
		return reservations;
	}

	/**
	 * 
	 * @param ec2
	 * @param keyName
	 */
	public static void createKeyPair(AmazonEC2 ec2, String keyName) {
		CreateKeyPairRequest createKeyPairRequest = new CreateKeyPairRequest(
				keyName);
		ec2.createKeyPair(createKeyPairRequest);
		System.out.println("Created keypair: " + keyName);
	}

	/**
	 * 
	 * @param ec2
	 * @return
	 */
	public static int getKeyPairCount(AmazonEC2 ec2) {
		DescribeKeyPairsRequest describeKeyPairsRequest = new DescribeKeyPairsRequest();
		DescribeKeyPairsResult describeKeyPairsResult = ec2
				.describeKeyPairs(describeKeyPairsRequest);
		return describeKeyPairsResult.getKeyPairs().size();
	}

	/**
	 * 
	 * @param ec2
	 * @param keyName
	 */
	public static void deleteKeyPair(AmazonEC2 ec2, String keyName) {
		DeleteKeyPairRequest deleteKeyPairRequest = new DeleteKeyPairRequest(
				keyName);
		ec2.deleteKeyPair(deleteKeyPairRequest);
		System.out.println("Deelted keypair: " + keyName);
	}

	/**
	 * 
	 * @param ec2
	 * @return
	 */
	public static List<Instance> getLastlaunchedInstance(AmazonEC2 ec2) {
		List<Instance> instancelist = null;
		List<Reservation> reservations = getInstancesList(ec2);
		for (Reservation reservation : reservations) {
			instancelist = reservation.getInstances();
			Collections.sort(instancelist, new Comparator<Instance>() {
				public int compare(Instance i1, Instance i2) {
					return i1.getLaunchTime().compareTo(i2.getLaunchTime());
				}
			});
		}
		return instancelist;
	}

	public static void createLaunchConfig(AmazonAutoScaling as,
			String launchConfigurationName, String imageId, String type,
			String keyName, ArrayList<String> securityGroups) {
		CreateLaunchConfigurationRequest createLaunchConfigurationRequest = new CreateLaunchConfigurationRequest()
				.withLaunchConfigurationName(launchConfigurationName)
				.withImageId(imageId).withInstanceType(type)
				.withSecurityGroups(securityGroups).withKeyName(keyName);
		as.createLaunchConfiguration(createLaunchConfigurationRequest);
		System.out.println("Created Launch Configuration: "
				+ launchConfigurationName);
	}

	public static List<LaunchConfiguration> describeLaunchConfigs(
			AmazonAutoScaling as) {
		DescribeLaunchConfigurationsResult launchConfigurationsResult = null;
		try {
			DescribeLaunchConfigurationsRequest describeLaunchConfigurationsRequest = new DescribeLaunchConfigurationsRequest();
			launchConfigurationsResult = as
					.describeLaunchConfigurations(describeLaunchConfigurationsRequest);
		} catch (AmazonServiceException ase) {
			System.out.println(ase.getMessage());
		}
		return launchConfigurationsResult.getLaunchConfigurations();
	}

	public static void deleteLaunchConfig(AmazonAutoScaling as,
			String launchConfigurationName) {
		try {
			DeleteLaunchConfigurationRequest deleteLaunchConfigurationRequest = new DeleteLaunchConfigurationRequest()
					.withLaunchConfigurationName(launchConfigurationName);
			as.deleteLaunchConfiguration(deleteLaunchConfigurationRequest);
			System.out.println("Deleted Launch Configuration: "
					+ launchConfigurationName);
		} catch (AmazonServiceException ase) {
			System.out.println(ase.getMessage());
		}
	}

	public static void createAutoScalingGroup(AmazonAutoScaling as,
			String autoScalingGroupName, String launchConfigurationName,
			int minSize, int maxSize, String availabilityZones) {
		CreateAutoScalingGroupRequest createAutoScalingGroupRequest = new CreateAutoScalingGroupRequest()
				.withAutoScalingGroupName(autoScalingGroupName)
				.withLaunchConfigurationName(launchConfigurationName)
				.withMinSize(minSize).withMaxSize(maxSize)
				.withAvailabilityZones(availabilityZones);
		as.createAutoScalingGroup(createAutoScalingGroupRequest);
		System.out.println("Created Auto Scaling Group: "
				+ autoScalingGroupName);
	}

	public static List<AutoScalingGroup> describeAutoScalingGroups(
			AmazonAutoScaling as) {
		DescribeAutoScalingGroupsResult autoScalingGroupsResult = null;
		try {
			DescribeAutoScalingGroupsRequest describeAutoScalingGroupsRequest = new DescribeAutoScalingGroupsRequest();
			autoScalingGroupsResult = as
					.describeAutoScalingGroups(describeAutoScalingGroupsRequest);
		} catch (AmazonServiceException ase) {
			System.out.println(ase.getMessage());
		}
		return autoScalingGroupsResult.getAutoScalingGroups();
	}

	public static void deleteAutoScalingGroup(AmazonAutoScaling as,
			String autoScalingGroupName) {
		try {
			DeleteAutoScalingGroupRequest deleteAutoScalingGroupRequest = new DeleteAutoScalingGroupRequest()
					.withAutoScalingGroupName(autoScalingGroupName)
					.withForceDelete(true);
			as.deleteAutoScalingGroup(deleteAutoScalingGroupRequest);
			System.out.println("Deleted Auto Scaling Group: "
					+ autoScalingGroupName);
		} catch (AmazonServiceException ase) {
			System.out.println(ase.getMessage());
		}
	}

}
