package com.eucalyptus.tests.awssdk

import com.amazonaws.AmazonServiceException
import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*
import org.testng.annotations.Test

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP

/**
 * This application tests EC2 instance termination protection.
 *
 * This is verification for the feature:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-2056
 */
class TestEC2InstanceTerminationProtection {

  private final String host
  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
      new TestEC2InstanceTerminationProtection().EC2InstanceTerminationProtectionTest()
  }

  public TestEC2InstanceTerminationProtection( ){
    minimalInit()
    this.host=HOST_IP
    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private String cloudUri( String servicePath ) {
    URI.create( "http://" + host + ":8773/" )
            .resolve( servicePath )
            .toString()
  }

  private AmazonEC2Client getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2Client ec2 = new AmazonEC2Client( credentials )
    ec2.setEndpoint( cloudUri( '/services/compute' ) )
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
  public void EC2InstanceTerminationProtectionTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

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

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      ec2.with {
        print( "Running instance without termination protection" )
        String instanceId = runInstances( new RunInstancesRequest(
            imageId: imageId,
            keyName: keyName,
            minCount: 1,
            maxCount: 1,
            placement: new Placement(
                availabilityZone: availabilityZone
            )
        ) ).with {
          reservation?.instances?.getAt(0)?.instanceId
        }
        cleanupTasks.add{
          print( "Terminating instance: ${instanceId}" )
          terminateInstances( new TerminateInstancesRequest(
              instanceIds: [ instanceId ]
          ) )
        }

        print( "Describing attributes for instance ${instanceId} to check termination protection disabled" )
        final Boolean disableApiTermination = describeInstanceAttribute( new DescribeInstanceAttributeRequest(
            instanceId: instanceId,
            attribute: 'disableApiTermination'
        ) ).with {
          instanceAttribute?.disableApiTermination
        }
        assertThat( Boolean.FALSE.equals( disableApiTermination ), "Expected false == disableApiTermination, but was: ${disableApiTermination}" )

        print( "Terminating instance ${instanceId}" )
        terminateInstances( new TerminateInstancesRequest(
            instanceIds: [ instanceId ]
        ) )
      }

      ec2.with {
        print( "Running instance with termination protection" )
        String instanceId = runInstances( new RunInstancesRequest(
            imageId: imageId,
            keyName: keyName,
            minCount: 1,
            maxCount: 1,
            placement: new Placement(
                availabilityZone: availabilityZone
            ),
            disableApiTermination: true
        ) ).with {
          reservation?.instances?.getAt(0)?.instanceId
        }
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

        print( "Describing attributes for instance ${instanceId} to check termination protection enabled" )
        final Boolean disableApiTermination = describeInstanceAttribute( new DescribeInstanceAttributeRequest(
            instanceId: instanceId,
            attribute: 'disableApiTermination'
        ) ).with {
          instanceAttribute?.disableApiTermination
        }
        assertThat( Boolean.TRUE.equals( disableApiTermination ), "Expected true == disableApiTermination, but was: ${disableApiTermination}" )

        print( "Terminating instance ${instanceId} (should fail)" )
        try {
          terminateInstances( new TerminateInstancesRequest(
              instanceIds: [ instanceId ]
          ) )
          assertThat( false, "Expected termination to fail for instance ${instanceId} with termination protection enabled")
        } catch ( AmazonServiceException e ) {
          print( "Expected termination failure: ${e}" )
          assertThat( 'OperationNotPermitted' == e.errorCode, "Expected error code OperationNotPermitted, but was: ${e.errorCode}" )
        }

        print( "Disabling termination protection for instance ${instanceId}" )
        modifyInstanceAttribute( new ModifyInstanceAttributeRequest(
            instanceId: instanceId,
            disableApiTermination: false
        ) )

        print( "Describing attributes for instance ${instanceId} to check termination protection disabled" )
        final Boolean disableApiTermination2 = describeInstanceAttribute( new DescribeInstanceAttributeRequest(
            instanceId: instanceId,
            attribute: 'disableApiTermination'
        ) ).with {
          instanceAttribute?.disableApiTermination
        }
        assertThat( Boolean.FALSE.equals( disableApiTermination2 ), "Expected false == disableApiTermination, but was: ${disableApiTermination2}" )

        print( "Terminating instance ${instanceId}" )
        terminateInstances( new TerminateInstancesRequest(
            instanceIds: [ instanceId ]
        ) )
      }

      ec2.with {
        print( "Running instance without termination protection" )
        String instanceId = runInstances( new RunInstancesRequest(
            imageId: imageId,
            keyName: keyName,
            minCount: 1,
            maxCount: 1,
            placement: new Placement(
                availabilityZone: availabilityZone
            )
        ) ).with {
          reservation?.instances?.getAt(0)?.instanceId
        }
        cleanupTasks.add{
          print( "Terminating instance: ${instanceId}" )
          terminateInstances( new TerminateInstancesRequest(
              instanceIds: [ instanceId ]
          ) )
        }

        print( "Enabling termination protection for instance ${instanceId}" )
        modifyInstanceAttribute( new ModifyInstanceAttributeRequest(
            instanceId: instanceId,
            disableApiTermination: true
        ) )

        print( "Describing attributes for instance ${instanceId} to check termination protection enabled" )
        final Boolean disableApiTermination = describeInstanceAttribute( new DescribeInstanceAttributeRequest(
            instanceId: instanceId,
            attribute: 'disableApiTermination'
        ) ).with {
          instanceAttribute?.disableApiTermination
        }
        assertThat( Boolean.TRUE.equals( disableApiTermination ), "Expected true == disableApiTermination, but was: ${disableApiTermination}" )

        print( "Terminating instance ${instanceId} (should fail)" )
        try {
          terminateInstances( new TerminateInstancesRequest(
              instanceIds: [ instanceId ]
          ) )
          assertThat( false, "Expected termination to fail for instance ${instanceId} with termination protection enabled")
        } catch ( AmazonServiceException e ) {
          print( "Expected termination failure: ${e}" )
          assertThat( 'OperationNotPermitted' == e.errorCode, "Expected error code OperationNotPermitted, but was: ${e.errorCode}" )
        }

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
