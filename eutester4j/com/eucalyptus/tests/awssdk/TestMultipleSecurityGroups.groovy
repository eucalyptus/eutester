package com.eucalyptus.tests.awssdk

import com.amazonaws.services.autoscaling.AmazonAutoScaling
import com.amazonaws.services.autoscaling.model.*
import com.amazonaws.services.ec2.model.*
import org.testng.annotations.Test

import static com.eucalyptus.tests.awssdk.Eutester4j.*

/**
 * Test functionality for multiple (EC2-Classic) security groups.
 * https://eucalyptus.atlassian.net/browse/EUCA-8444
 */
class TestMultipleSecurityGroups {

    @Test
    public void test() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        AmazonAutoScaling asg = getAutoScalingClient(ACCESS_KEY, SECRET_KEY, AS_ENDPOINT);

        final List<Runnable> cleanupTasks = [] as List<Runnable>
        try {
            // Test EC2 functionality
            List<String> groupNames = (1..3).collect { Integer count -> "${NAME_PREFIX}Group${count}" as String }
            groupNames.each { String groupName ->
                println("Creating security group: ${groupName}")
                ec2.createSecurityGroup(new CreateSecurityGroupRequest(
                        groupName: groupName,
                        description: "Test group: ${groupName}"
                ))
                cleanupTasks.add {
                    print("Deleting security group: ${groupName}")
                    ec2.deleteSecurityGroup(new DeleteSecurityGroupRequest(groupName: groupName))
                }
            }

            final String instanceClientToken = "${NAME_PREFIX}Instance1"
            println("Running instance with client token: ${instanceClientToken}")
            final String instanceId = ec2.runInstances(new RunInstancesRequest(
                    imageId: IMAGE_ID,
                    instanceType: "m1.small",
                    minCount: 1,
                    maxCount: 1,
                    clientToken: instanceClientToken,
                    securityGroups: groupNames
            )).with {
                reservation?.with {
                    List<String> reservationGroupNames =
                            groups.collect { GroupIdentifier groupIdentifier -> groupIdentifier.groupName }
                    groupNames.each { String groupName ->
                        assertThat(reservationGroupNames.contains(groupName), "Expected ${groupName} in reservation security groups: ${reservationGroupNames}")
                    }

                    instances?.getAt(0)?.with {
                        List<String> instanceGroupNames =
                                securityGroups.collect { GroupIdentifier groupIdentifier -> groupIdentifier.groupName }
                        groupNames.each { String groupName ->
                            assertThat(instanceGroupNames.contains(groupName), "Expected ${groupName} in instance security groups: ${instanceGroupNames}")
                        }
                        instanceId
                    }
                }
            }

            print("Launched instance with id: ${instanceId}")
            cleanupTasks.add {
                print("Terminating instance: ${instanceId}")
                ec2.terminateInstances(new TerminateInstancesRequest(instanceIds: [instanceId]))
                (1..20).inject("running") { String lastStatus, Integer value ->
                    if (["terminated", "stopped"].contains(lastStatus)) return lastStatus
                    print("Waiting for instance to terminate: ${instanceId} - ${lastStatus}")
                    sleep 5000
                    ec2.describeInstances(new DescribeInstancesRequest(instanceIds: [instanceId])).with {
                        reservations?.getAt(0)?.instances?.getAt(0)?.state?.name ?: "terminated"
                    }
                }
            }

            print("Waiting for instance to start: ${instanceId}")
            (1..20).inject("pending") { String lastStatus, Integer value ->
                if (["running", "terminated"].contains(lastStatus)) return lastStatus
                print("Waiting for instance to launch: ${instanceId} - ${lastStatus}")
                sleep 5000
                print(ec2.describeInstances(new DescribeInstancesRequest(instanceIds: [instanceId])))
                ec2.describeInstances(new DescribeInstancesRequest(instanceIds: [instanceId])).with {
                    reservations?.getAt(0)?.instances?.getAt(0)?.state?.name ?: "pending"
                }
            }

            print("Verifying describe instances reports all groups.")
            ec2.describeInstances(new DescribeInstancesRequest(instanceIds: [instanceId])).with {
                reservations?.getAt(0)?.with {
                    List<String> reservationGroupNames =
                            groups.collect { GroupIdentifier groupIdentifier -> groupIdentifier.groupName }
                    groupNames.each { String groupName ->
                        assertThat(reservationGroupNames.contains(groupName), "Expected ${groupName} in reservation security groups: ${reservationGroupNames}")
                    }

                    instances?.getAt(0)?.with {
                        List<String> instanceGroupNames =
                                securityGroups.collect { GroupIdentifier groupIdentifier -> groupIdentifier.groupName }
                        groupNames.each { String groupName ->
                            assertThat(instanceGroupNames.contains(groupName), "Expected ${groupName} in instance security groups: ${instanceGroupNames}")
                        }
                        instanceId
                    }
                }
            }

            print("Verifying describe instance attributes reports all groups")
            ec2.describeInstanceAttribute(new DescribeInstanceAttributeRequest(instanceId: instanceId, attribute: InstanceAttributeName.GroupSet.toString())).with {
                // TODO - this currently requires a patched AWS Java SDK - https://github.com/aws/aws-sdk-java/pull/155
                List<String> attributeGroupNames = instanceAttribute?.securityGroups?.collect { GroupIdentifier groupIdentifier -> groupIdentifier.groupName } ?: []
                groupNames.each { String groupName ->
                    assertThat(attributeGroupNames.contains(groupName), "Expected ${groupName} in instance attribute security groups: ${attributeGroupNames}")
                }
            }

            print("Terminating instance")
            ec2.terminateInstances(new TerminateInstancesRequest(instanceIds: [instanceId]))
            String status = (1..20).inject("running") { String lastStatus, Integer value ->
                if (["terminated", "stopped"].contains(lastStatus)) return lastStatus
                print("Waiting for instance to terminate: ${instanceId} - ${lastStatus}")
                sleep 5000
                ec2.describeInstances(new DescribeInstancesRequest(instanceIds: [instanceId])).with {
                    reservations?.getAt(0)?.instances?.getAt(0)?.state?.name ?: "running"
                }
            }
            assertThat(["terminated", "stopped"].contains(status), "Unexpected instance status: ${status}")

            // Test AutoScaling functionality
            final String launchConfigurationName = "${NAME_PREFIX}Config1"
            print("Creating launch configuration: ${launchConfigurationName}");
            asg.createLaunchConfiguration(new CreateLaunchConfigurationRequest(
                    imageId: IMAGE_ID,
                    instanceType: "m1.small",
                    securityGroups: groupNames,
                    launchConfigurationName: launchConfigurationName,
            ))
            cleanupTasks.add {
                print("Deleting launch configuration: ${launchConfigurationName}");
                asg.deleteLaunchConfiguration(new DeleteLaunchConfigurationRequest(launchConfigurationName: launchConfigurationName))
            }

            final String autoScalingGroupName = "${NAME_PREFIX}Group1"
            print("Creating auto scaling group: ${autoScalingGroupName}");
            asg.createAutoScalingGroup(new CreateAutoScalingGroupRequest(
                    minSize: 0,
                    maxSize: 1,
                    desiredCapacity: 1,
                    availabilityZones: [AVAILABILITY_ZONE],
                    launchConfigurationName: launchConfigurationName,
                    autoScalingGroupName: autoScalingGroupName
            ))
            cleanupTasks.add {
                print("Deleting auto scaling group: ${autoScalingGroupName}");
                asg.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest(autoScalingGroupName: autoScalingGroupName, forceDelete: true))
            }

            final String autoScalingInstanceId = (1..20).inject(null) { String id, Integer value ->
                if (id != null) return id
                print("Waiting for instance to launch in auto scaling group: ${autoScalingGroupName}")
                sleep 5000
                asg.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest(autoScalingGroupNames: [autoScalingGroupName])).with {
                    autoScalingGroups?.getAt(0)?.instances?.getAt(0)?.instanceId
                }
            }
            assertThat(autoScalingInstanceId != null, "Expected instance id for auto scaling group instance")

            print("Verifying describe instance attributes reports all groups for: ${autoScalingInstanceId}")
            ec2.describeInstances(new DescribeInstancesRequest(instanceIds: [autoScalingInstanceId])).with {
                reservations?.getAt(0)?.with {
                    List<String> reservationGroupNames =
                            groups.collect { GroupIdentifier groupIdentifier -> groupIdentifier.groupName }
                    groupNames.each { String groupName ->
                        assertThat(reservationGroupNames.contains(groupName), "Expected ${groupName} in reservation security groups: ${reservationGroupNames}")
                    }

                    instances?.getAt(0)?.with {
                        List<String> instanceGroupNames =
                                securityGroups.collect { GroupIdentifier groupIdentifier -> groupIdentifier.groupName }
                        groupNames.each { String groupName ->
                            assertThat(instanceGroupNames.contains(groupName), "Expected ${groupName} in instance security groups: ${instanceGroupNames}")
                        }
                        instanceId
                    }
                }
            }

            print("Setting auto scaling group capacity to 0: ${autoScalingGroupName}");
            asg.setDesiredCapacity(new SetDesiredCapacityRequest(autoScalingGroupName: autoScalingGroupName, desiredCapacity: 0))

            String autoScalingGroupInstanceStatus = (1..30).inject("running") { String lastStatus, Integer value ->
                if (["terminated", "stopped"].contains(lastStatus)) return lastStatus
                print("Waiting for auto scaling group instance to terminate: ${autoScalingInstanceId} - ${lastStatus}")
                sleep 5000
                ec2.describeInstances(new DescribeInstancesRequest(instanceIds: [autoScalingInstanceId])).with {
                    reservations?.getAt(0)?.instances?.getAt(0)?.state?.name ?: "running"
                }
            }
            assertThat(["terminated", "stopped"].contains(autoScalingGroupInstanceStatus), "Unexpected instance status: ${status}")

            print("Deleting auto scaling group: ${autoScalingGroupName}");
            asg.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest(autoScalingGroupName: autoScalingGroupName, forceDelete: true))

            print("Deleting launch configuration: ${launchConfigurationName}");
            asg.deleteLaunchConfiguration(new DeleteLaunchConfigurationRequest(launchConfigurationName: launchConfigurationName))

            print("Test complete")
        } finally {
            // Attempt to clean up anything we created
            cleanupTasks.reverseEach { Runnable cleanupTask ->
                try {
                    cleanupTask.run()
                } catch (Exception e) {
                    e.printStackTrace()
                }
            }
        }
    }
}
