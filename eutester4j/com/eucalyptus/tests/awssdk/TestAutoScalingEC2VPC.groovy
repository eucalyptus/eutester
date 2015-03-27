package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentials
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.services.autoscaling.AmazonAutoScaling
import com.amazonaws.services.autoscaling.AmazonAutoScalingClient
import com.amazonaws.services.autoscaling.model.CreateAutoScalingGroupRequest
import com.amazonaws.services.autoscaling.model.CreateLaunchConfigurationRequest
import com.amazonaws.services.autoscaling.model.DeleteAutoScalingGroupRequest
import com.amazonaws.services.autoscaling.model.DeleteLaunchConfigurationRequest
import com.amazonaws.services.autoscaling.model.DescribeAutoScalingGroupsRequest
import com.amazonaws.services.autoscaling.model.DescribeLaunchConfigurationsRequest
import com.amazonaws.services.autoscaling.model.ScalingActivityInProgressException
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.AttachInternetGatewayRequest
import com.amazonaws.services.ec2.model.CreateSecurityGroupRequest
import com.amazonaws.services.ec2.model.CreateSubnetRequest
import com.amazonaws.services.ec2.model.CreateVpcRequest
import com.amazonaws.services.ec2.model.DeleteInternetGatewayRequest
import com.amazonaws.services.ec2.model.DeleteSecurityGroupRequest
import com.amazonaws.services.ec2.model.DeleteSubnetRequest
import com.amazonaws.services.ec2.model.DeleteVpcRequest
import com.amazonaws.services.ec2.model.DescribeImagesRequest
import com.amazonaws.services.ec2.model.DetachInternetGatewayRequest
import com.amazonaws.services.ec2.model.Filter

/**
 * This application tests Auto Scaling use of EC2 VPC functionality.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9828
 */
class TestAutoscalingEC2VPC {

  private final String host;
  private final String accessKey;
  private final String secretKey;

  public static void main( String[] args ) throws Exception {
    final TestAutoscalingEC2VPC test =  new TestAutoscalingEC2VPC(
        '10.111.5.64',
        'AKI4YB4UYR1BRFUYPGHO',
        'JbvmaFyUjehb56LOV0lmcUe3Tbc2LM5nIyWO6wDP'
    );
    test.test();
  }

  public TestAutoscalingEC2VPC( final String host,
                                final String accessKey,
                                final String secretKey ) {
    this.host = host;
    this.accessKey = accessKey;
    this.secretKey = secretKey;
  }

  private AWSCredentials credentials() {
    return new BasicAWSCredentials( accessKey, secretKey );
  }

  private String cloudUri( String servicePath ) {
    URI.create( "http://" + host + ":8773/" )
        .resolve( servicePath )
        .toString()
  }

  private AmazonAutoScaling getAutoScalingClient( ) {
    final AmazonAutoScaling asc = new AmazonAutoScalingClient( credentials( ) )
    asc.setEndpoint( cloudUri( "/services/AutoScaling/" ) )
    asc
  }

  private AmazonEC2 getEc2Client( ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( credentials() )
    ec2.setEndpoint( cloudUri( "/services/compute/" ) )
    ec2
  }

  private String instanceType() {
    return "m1.small"
  }

  private void assertThat( boolean condition,
                           String message ){
    assert condition : message
  }

  private void print( String text ) {
    System.out.println( text )
  }

  public void test() throws Exception{
    final AmazonEC2 ec2 = getEc2Client()

    // Find an image to use
    final String imageId = ec2.describeImages( new DescribeImagesRequest(
        filters: [
            new Filter( name: "image-type", values: ["machine"] ),
            new Filter( name: "root-device-type", values: ["instance-store"] ),
        ]
    ) ).with {
      images?.getAt( 0 )?.imageId
    }
    assertThat( imageId != null , "Image not found" )
    print( "Using image: ${imageId}" )

    // Discover SSH key
    final String keyName = ec2.describeKeyPairs().with {
      keyPairs?.getAt(0)?.keyName
    }
    print( "Using key pair: " + keyName )

    // End discovery, start test
    final String namePrefix = UUID.randomUUID().toString() + "-"
    print( "Using resource prefix for test: " + namePrefix )

    final List<Runnable> cleanupTasks = new ArrayList<Runnable>()
    try {
      final String vpcId = ec2.with {
        // Create VPC to use
        print('Creating VPC')
        final String vpcId = createVpc(new CreateVpcRequest(
            cidrBlock: '10.0.0.0/24'
        )).with {
          vpc?.vpcId
        }
        assertThat(vpcId != null, "Expected VPC identifier")
        print("Created vpc ${vpcId}")
        cleanupTasks.add {
          print("Deleting vpc ${vpcId}")
          deleteVpc(new DeleteVpcRequest(vpcId: vpcId))
        }

        print('Creating internet gateway')
        final String internetGatewayId = createInternetGateway().with {
          internetGateway?.internetGatewayId
        }
        assertThat(internetGatewayId != null, "Expected internet gateway identifier")
        print("Created internet gateway ${internetGatewayId}")
        cleanupTasks.add {
          print("Deleting internet gateway ${internetGatewayId}")
          deleteInternetGateway(new DeleteInternetGatewayRequest(internetGatewayId: internetGatewayId))
        }

        print("Attaching internet gateway ${internetGatewayId} to vpc ${vpcId}")
        attachInternetGateway(new AttachInternetGatewayRequest(
            internetGatewayId: internetGatewayId,
            vpcId: vpcId
        ))
        cleanupTasks.add {
          print("Detaching internet gateway ${internetGatewayId} from vpc ${vpcId}")
          detachInternetGateway(new DetachInternetGatewayRequest(
              internetGatewayId: internetGatewayId,
              vpcId: vpcId
          ))
        }
        vpcId
      }

      final String subnetId = ec2.with{
        print( "Creating subnet" )
        final String subnetId = createSubnet( new CreateSubnetRequest( vpcId: vpcId, cidrBlock: '10.0.0.0/24' ) ).with {
          subnet?.subnetId
        }
        assertThat( subnetId != null, "Expected subnet identifier" )
        print( "Created subnet ${subnetId}" )
        cleanupTasks.add{
          print( "Deleting subnet ${subnetId}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId ) )
        }
        subnetId
      }

      final String groupId = ec2.with{
        final String securityGroupName = namePrefix + "EC2VPCTest"
        print( "Creating a security group for test use: " + securityGroupName )
        final String groupId = ec2.createSecurityGroup( new CreateSecurityGroupRequest(
            groupName: securityGroupName,
            description: securityGroupName,
            vpcId: vpcId
        ) ).with {
          groupId
        }
        print( "Created security group: ${securityGroupName}/${groupId}" )
        cleanupTasks.add{
          print( "Deleting security group: ${securityGroupName}/${groupId}" )
          ec2.deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: groupId ) )
        }
        groupId
      }

      getAutoScalingClient( ).with {
        // Register cleanup for launch config
        final String configName = namePrefix + "EC2VPCTest"
        cleanupTasks.add{
          print( "Deleting launch configuration: ${configName}" )
          deleteLaunchConfiguration( new DeleteLaunchConfigurationRequest( launchConfigurationName: configName ) )
        }

        // Create launch configuration
        print( "Creating launch configuration: " + configName )
        createLaunchConfiguration( new CreateLaunchConfigurationRequest(
            launchConfigurationName: configName,
            imageId: imageId,
            keyName: keyName,
            securityGroups: [ groupId ],
            instanceType: instanceType( ),
            associatePublicIpAddress: true
        ) )

        print( "Verifying launch configuration public IP address association setting" )
        describeLaunchConfigurations( new DescribeLaunchConfigurationsRequest(
            launchConfigurationNames: [ configName ]
        ) ).with {
          assertThat( launchConfigurations != null && launchConfigurations.size()==1,
              "Expected one launch configuration, but was: ${launchConfigurations?.size()}")
          launchConfigurations[0].with {
            assertThat( associatePublicIpAddress,
                "Expected associatePublicIpAddress true, but was: ${associatePublicIpAddress}" )
          }
        }

        // Register cleanup for auto scaling group
        final String groupName = namePrefix + "EC2VPCTest"
        cleanupTasks.add{
          print( "Deleting group: " + groupName )
          deleteAutoScalingGroup( new DeleteAutoScalingGroupRequest(
              autoScalingGroupName: groupName,
              forceDelete: true
          ) )
        }

        // Create scaling group
        print( "Creating auto scaling group: " + groupName )
        createAutoScalingGroup( new CreateAutoScalingGroupRequest(
            autoScalingGroupName: groupName,
            launchConfigurationName: configName,
            desiredCapacity: 0,
            minSize: 0,
            maxSize: 0,
            VPCZoneIdentifier: subnetId
        ) )

        print( "Verifying auto scaling group vpc zone identifier setting" )
        describeAutoScalingGroups( new DescribeAutoScalingGroupsRequest(
            autoScalingGroupNames: [ groupName ]
        ) ).with {
          assertThat( autoScalingGroups != null && autoScalingGroups.size()==1,
              "Expected one auto scaling group, but was: ${autoScalingGroups?.size()}")
          autoScalingGroups[0].with {
            assertThat( VPCZoneIdentifier == subnetId,
                "Expected vpc zone identifier ${subnetId}, but was: ${VPCZoneIdentifier}" )
          }
        }
      }

      print( "Test complete" )
    } finally {
      // Attempt to clean up anything we created
      Collections.reverse( cleanupTasks )
      for ( final Runnable cleanupTask : cleanupTasks ) {
        while (true) try {
          cleanupTask.run()
          break
        } catch ( ScalingActivityInProgressException e ) {
          print( "Retrying cleanup due to : " +  e.toString() )
          Thread.sleep( 1000 )
        } catch ( Exception e ) {
          e.printStackTrace()
          break
        }
      }
    }
  }
}
