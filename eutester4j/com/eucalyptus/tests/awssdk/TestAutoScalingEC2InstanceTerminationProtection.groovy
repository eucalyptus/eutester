package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.autoscaling.AmazonAutoScaling
import com.amazonaws.services.autoscaling.AmazonAutoScalingClient
import com.amazonaws.services.autoscaling.model.CreateAutoScalingGroupRequest
import com.amazonaws.services.autoscaling.model.CreateLaunchConfigurationRequest
import com.amazonaws.services.autoscaling.model.DeleteAutoScalingGroupRequest
import com.amazonaws.services.autoscaling.model.DeleteLaunchConfigurationRequest
import com.amazonaws.services.autoscaling.model.DescribeAutoScalingGroupsRequest
import com.amazonaws.services.autoscaling.model.InstanceMonitoring
import com.amazonaws.services.autoscaling.model.SetDesiredCapacityRequest
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.DescribeImagesRequest
import com.amazonaws.services.ec2.model.DescribeInstanceAttributeRequest
import com.amazonaws.services.ec2.model.DescribeInstancesRequest
import com.amazonaws.services.ec2.model.Filter
import com.amazonaws.services.ec2.model.ModifyInstanceAttributeRequest
import com.amazonaws.services.ec2.model.TerminateInstancesRequest
import org.testng.annotations.Test

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit


/**
 * This application tests AutoScaling groups with EC2 instance termination protection.
 *
 * This is verification for the feature:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-2056
 */
class TestAutoScalingEC2InstanceTerminationProtection {

  private final String host
  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestEC2InstanceTerminationProtection().EC2InstanceTerminationProtectionTest()
  }

  public TestAutoScalingEC2InstanceTerminationProtection( ){
    minimalInit( )
    this.host = HOST_IP
    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private String cloudUri( String servicePath ) {
    URI.create( "http://" + host + ":8773/" )
        .resolve( servicePath )
        .toString()
  }

  private AmazonAutoScaling getAutoScalingClient( final AWSCredentialsProvider credentials ) {
    final AmazonAutoScaling auto = new AmazonAutoScalingClient( credentials )
    auto.endpoint = cloudUri( '/services/AutoScaling' )
    auto
  }

  private AmazonEC2Client getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2Client ec2 = new AmazonEC2Client( credentials )
    ec2.endpoint = cloudUri( '/services/compute' )
    ec2
  }

  private boolean assertThat( boolean condition,
                              String message ){
    assert condition : message
    true
  }

  private void print( String text ) {
    System.out.println( text )
  }

  @Test
  public void autoScalingEC2InstanceTerminationProtectionTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )
    final AmazonAutoScaling auto = getAutoScalingClient( credentials )

    // Find an AZ to use
    final String availabilityZone = ec2.describeAvailabilityZones( ).with{
      availabilityZones?.getAt( 0 )?.zoneName
    };
    assertThat( availabilityZone != null, "Availability zone not found" );
    print( "Using availability zone: ${availabilityZone}" );

    // Find an image to use
    final String imageId = ec2.describeImages( new DescribeImagesRequest(
        filters: [
            new Filter( name: "image-type", values: ["machine"] ),
            new Filter( name: "root-device-type", values: ["instance-store"] ),
        ]
    ) ).with {
      images?.getAt( 0 )?.imageId
    }
    assertThat( imageId != null , "Image not found (instance-store)" )
    print( "Using image: ${imageId}" )

    // Discover SSH key
    final String keyName = ec2.describeKeyPairs().with {
      keyPairs?.getAt(0)?.keyName
    }
    print( "Using key pair: " + keyName );

    final String namePrefix = UUID.randomUUID().toString().substring(0, 13) + "-";
    print( "Using resource prefix for test: " + namePrefix );

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      String instanceId = null
      String configName = "${namePrefix}config-1"
      String groupName = "${namePrefix}group-1"
      auto.with {
        print( "Creating launch configuration ${configName}" )
        createLaunchConfiguration( new CreateLaunchConfigurationRequest(
            imageId: imageId,
            instanceMonitoring: new InstanceMonitoring(
              enabled: false
            ),
            instanceType: 'm1.small',
            keyName: keyName,
            launchConfigurationName: configName
        ) )
        cleanupTasks.add{
          print( "Deleting launch configuration ${configName}" )
          deleteLaunchConfiguration( new DeleteLaunchConfigurationRequest(
              launchConfigurationName: configName
          ) )
        }

        print( "Creating auto scaling group: ${groupName}" )
        createAutoScalingGroup( new CreateAutoScalingGroupRequest(
            autoScalingGroupName: groupName,
            launchConfigurationName: configName,
            minSize: 0,
            maxSize: 1,
            desiredCapacity: 1,
            availabilityZones: [ availabilityZone ]
        ) )
        cleanupTasks.add{
          print( "Setting desired capacity to zero for group: ${groupName}" )
          setDesiredCapacity( new SetDesiredCapacityRequest(
              autoScalingGroupName: groupName,
              desiredCapacity: 0
          ))
          print( "Deleting auto scaling group: ${groupName}" )
          deleteAutoScalingGroup( new DeleteAutoScalingGroupRequest(
              autoScalingGroupName: groupName,
              forceDelete: true
          ) )
        }

        print( "Waiting for instance in auto scaling group: ${groupName}" )
        ( 1..50 ).find{
          sleep 6000
          print( "Waiting for instance in auto scaling group: ${groupName}, waited ${it*5}s" )
          describeAutoScalingGroups( new DescribeAutoScalingGroupsRequest(
              autoScalingGroupNames: [ groupName ]
          ) ).with {
            instanceId = autoScalingGroups?.getAt( 0 )?.instances?.getAt( 0 )?.instanceId
          }
        }
        print( "Found instance ${instanceId}, for group ${groupName}" )
        assertThat( instanceId != null, "Expected instance identifier (no instances in group)" )
      }

      ec2.with {
        print( "Describing attributes for instance ${instanceId} to check termination protection disabled" )
        final Boolean disableApiTermination = describeInstanceAttribute( new DescribeInstanceAttributeRequest(
            instanceId: instanceId,
            attribute: 'disableApiTermination'
        ) ).with {
          instanceAttribute?.disableApiTermination
        }
        assertThat( Boolean.FALSE.equals( disableApiTermination ), "Expected false == disableApiTermination, but was: ${disableApiTermination}" )

        print( "Enabling termination protection for instance ${instanceId}" )
        modifyInstanceAttribute( new ModifyInstanceAttributeRequest(
            instanceId: instanceId,
            disableApiTermination: true
        ) )

        print( "Describing attributes for instance ${instanceId} to check termination protection enabled" )
        final Boolean disableApiTermination2 = describeInstanceAttribute( new DescribeInstanceAttributeRequest(
            instanceId: instanceId,
            attribute: 'disableApiTermination'
        ) ).with {
          instanceAttribute?.disableApiTermination
        }
        assertThat( Boolean.TRUE.equals( disableApiTermination2 ), "Expected true == disableApiTermination, but was: ${disableApiTermination2}" )

        cleanupTasks.add{
          print( "Disabling termination protection for instance ${instanceId}" )
          modifyInstanceAttribute( new ModifyInstanceAttributeRequest(
              instanceId: instanceId,
              disableApiTermination: false
          ) )
          print( "Terminating instance ${instanceId}" )
          terminateInstances( new TerminateInstancesRequest(
              instanceIds: [ instanceId ]
          ) )
        }
      }

      auto.with {
        print( "Setting desired capacity to zero for group ${groupName} with protected instance ${instanceId}" )
        setDesiredCapacity( new SetDesiredCapacityRequest(
            autoScalingGroupName: groupName,
            desiredCapacity: 0
        ))
      }

      ec2.with {
        print( "Waiting for instance ${instanceId} to terminate" )
        Object found = ( 1..50 ).find{
          sleep 6000
          print( "Waiting for instance ${instanceId} to terminate, waited ${it*5}s" )
          describeInstances( new DescribeInstancesRequest(
              instanceIds: [ instanceId ]
          ) ).with {
            'terminated' == reservations?.getAt( 0 )?.instances?.getAt( 0 )?.state?.name
          }
        }
        assertThat( found != null, "Instance ${instanceId} did not terminate" )
        print( "Instance ${instanceId} with termination protection enabled was successfully terminated by auto scaling" )
      }

      print( "Test complete" )
    } finally {
      // Attempt to clean up anything we created
      cleanupTasks.reverseEach { Runnable cleanupTask ->
        try {
          cleanupTask.run()
        } catch ( Exception e ) {
          e.printStackTrace()
        }
      }
    }
  }

}
