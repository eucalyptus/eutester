package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.regions.Region
import com.amazonaws.regions.Regions
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.AttachInternetGatewayRequest
import com.amazonaws.services.ec2.model.AuthorizeSecurityGroupIngressRequest
import com.amazonaws.services.ec2.model.CreateSecurityGroupRequest
import com.amazonaws.services.ec2.model.CreateSubnetRequest
import com.amazonaws.services.ec2.model.CreateVpcRequest
import com.amazonaws.services.ec2.model.DeleteInternetGatewayRequest
import com.amazonaws.services.ec2.model.DeleteSecurityGroupRequest
import com.amazonaws.services.ec2.model.DeleteSubnetRequest
import com.amazonaws.services.ec2.model.DeleteVpcRequest
import com.amazonaws.services.ec2.model.DescribeAvailabilityZonesResult
import com.amazonaws.services.ec2.model.DetachInternetGatewayRequest
import com.amazonaws.services.ec2.model.IpPermission
import com.amazonaws.services.ec2.model.UserIdGroupPair
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancing
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancingClient
import com.amazonaws.services.elasticloadbalancing.model.*

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit;
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP;
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY;
/**
 *
 */
class TestELBVPC {

  private final String host;
  private final AWSCredentialsProvider credentials;

  public static void main( String[] args ) throws Exception {
    new TestELBVPC( ).test( )
  }

  public TestELBVPC(  ) {
    minimalInit()
    this.host = HOST_IP
    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private String cloudUri( String servicePath ) {
    URI.create( "http://" + host + ":8773/" )
        .resolve( servicePath )
        .toString()
  }

  private AmazonEC2 getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( credentials )
    if ( host ) {
      ec2.setEndpoint( cloudUri( "/services/compute" ) )
    } else {
      ec2.setRegion(Region.getRegion( Regions.US_WEST_1 ) )
    }
    ec2
  }

  private AmazonElasticLoadBalancing getELBClient( final AWSCredentialsProvider credentials ) {
    final AmazonElasticLoadBalancing elb = new AmazonElasticLoadBalancingClient( credentials )
    if ( host ) {
      elb.setEndpoint( cloudUri( "/services/LoadBalancing" ) )
    } else {
      elb.setRegion(Region.getRegion( Regions.US_WEST_1 ) )
    }
    elb
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
  public void test( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    // Find an AZ to use
    final DescribeAvailabilityZonesResult azResult = ec2.describeAvailabilityZones();

    assertThat( azResult.getAvailabilityZones().size() > 0, "Availability zone not found" );

    final String availabilityZone = azResult.getAvailabilityZones().get( 0 ).getZoneName();
    print( "Using availability zone: " + availabilityZone );

    final String availabilityZone2 = azResult.getAvailabilityZones().getAt( 1 )?.getZoneName( );

    final String namePrefix = UUID.randomUUID().toString().substring(0, 13) + "-";
    print( "Using resource prefix for test: " + namePrefix );

    final AmazonElasticLoadBalancing elb = getELBClient( credentials )
    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      String vpcId
      String subnetId
      String securityGroupId
      ec2.with {
        print( "Creating VPC for ELB" )
        vpcId = createVpc( new CreateVpcRequest(
          cidrBlock: '10.0.0.0/24'
        ) )?.with {
          vpc.vpcId
        }
        print( "Created VPC ${vpcId}" )
        cleanupTasks.add{
          println( "Deleting VPC ${vpcId}" )
          deleteVpc( new DeleteVpcRequest( vpcId: vpcId ))
        }

        print( "Creating internet gateway" )
        String internetGatewayId = createInternetGateway( ).with{
          internetGateway.internetGatewayId
        }

        print( "Created internet gateway ${internetGatewayId}" )
        cleanupTasks.add{
          print( "Deleting internet gateway ${internetGatewayId}" )
          deleteInternetGateway( new DeleteInternetGatewayRequest( internetGatewayId: internetGatewayId ) )
        }

        print( "Attaching internet gateway to vpc" )
        attachInternetGateway( new AttachInternetGatewayRequest( vpcId: vpcId, internetGatewayId: internetGatewayId ))
        cleanupTasks.add{
          print( "Detaching internet gateway from vpc" )
          detachInternetGateway( new DetachInternetGatewayRequest( vpcId: vpcId, internetGatewayId: internetGatewayId ))
        }

        print( "Creating subnet for ELB" )
        subnetId = createSubnet( new CreateSubnetRequest( vpcId: vpcId, cidrBlock: '10.0.0.0/24' ) ).with {
          subnet.subnetId
        }
        print( "Created subnet ${subnetId}" )

        cleanupTasks.add{
          print( "Deleting subnet ${subnetId}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId ) )
        }

        String groupName = "${namePrefix}elb-test-group"
        print( "Creating security group with name ${groupName}" )
        securityGroupId = createSecurityGroup( new CreateSecurityGroupRequest(
            groupName: groupName,
            vpcId: vpcId,
            description: 'Group for ELB VPC testing'
        ) ).with {
          groupId
        }
        print( "Created security group ${groupName}/${securityGroupId}" )
        cleanupTasks.add{
          print( "Deleting security group ${groupName}/${securityGroupId}" )
          deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: securityGroupId ) )
        }
      }

      elb.with {
        String loadBalancerName = "${namePrefix}-balancer1"
        print( "Creating load balancer: ${loadBalancerName}" )
        createLoadBalancer( new CreateLoadBalancerRequest(
            loadBalancerName: loadBalancerName,
            listeners: [ new Listener(
                loadBalancerPort: 9999,
                protocol: 'HTTP',
                instancePort: 9999,
                instanceProtocol: 'HTTP'
            ) ],
            subnets: [ subnetId ]
        ) )
        cleanupTasks.add {
          print( "Deleting load balancer: ${loadBalancerName}" )
          deleteLoadBalancer( new DeleteLoadBalancerRequest( loadBalancerName: loadBalancerName ) )
        }

        println( "Created load balancer: ${loadBalancerName}" )
        describeLoadBalancers( new DescribeLoadBalancersRequest( loadBalancerNames: [ loadBalancerName ] ) ).with {
          println(loadBalancerDescriptions.toString())
          assertThat(loadBalancerDescriptions.size() == 1, "Expected one load balancer, but was: ${loadBalancerDescriptions.size()}")
          loadBalancerDescriptions.get(0).with {
            assertThat(loadBalancerName == it.loadBalancerName, "Expected name ${loadBalancerName}, but was: ${it.loadBalancerName}")
            assertThat(scheme == 'internet-facing', "Expected scheme internet-facing, but was: ${scheme}")
            assertThat(VPCId == vpcId, "Expected vpc ${vpcId}, but was: ${VPCId}")
            assertThat(subnets != null && subnets.size()==1, "Expected one subnet, but was: ${subnets}")
            assertThat(securityGroups != null && securityGroups.size()==1, "Expected one (VPC) security group, but was: ${securityGroups}")
            assertThat(availabilityZones == [availabilityZone], "Expected zones [ ${availabilityZone} ], but was: ${availabilityZones}")
            assertThat(sourceSecurityGroup != null, "Expected source security group")
            subnetId = subnets.get( 0 );
            sourceSecurityGroup.with {
              assertThat( 'default' == groupName, "Expected security group name default, but was: ${groupName}" )
              ec2.with {
                String authGroupName = "${namePrefix}elb-source-group-auth-test"
                println("Creating security group to test elb source group authorization: ${authGroupName}")
                String authGroupId = createSecurityGroup(new CreateSecurityGroupRequest(
                    groupName: authGroupName,
                    vpcId: vpcId,
                    description: 'Test security group for validation of ELB source group authorization'
                )).with {
                  groupId
                }
                println("Created security group ${authGroupName}, with id ${authGroupId}")
                cleanupTasks.add {
                  println("Deleting security group: ${authGroupName}/${authGroupId}")
                  deleteSecurityGroup(new DeleteSecurityGroupRequest(
                      groupId: authGroupId
                  ))
                }

                println("Authorizing elb source group ${ownerAlias}/${groupName} for ${authGroupName}/${authGroupId}")
                authorizeSecurityGroupIngress(new AuthorizeSecurityGroupIngressRequest(
                    groupId: authGroupId,
                    ipPermissions: [
                        new IpPermission(
                            ipProtocol: 'tcp',
                            fromPort: 9999,
                            toPort: 9999,
                            userIdGroupPairs: [
                                new UserIdGroupPair(
                                    userId: ownerAlias,
                                    groupName: groupName
                                )
                            ]
                        )
                    ]
                ))
              }
            }
          }
        }

        println( "Applying security groups [${securityGroupId}] to ${loadBalancerName}" )
        applySecurityGroupsToLoadBalancer( new ApplySecurityGroupsToLoadBalancerRequest(
            loadBalancerName: loadBalancerName,
            securityGroups: [ securityGroupId ]
        ) ).with {
          println( "Security groups now ${securityGroups}" )
        }

        println( "Verifying security groups for load balancer: ${loadBalancerName}" )
        describeLoadBalancers( new DescribeLoadBalancersRequest( loadBalancerNames: [ loadBalancerName ] ) ).with {
          println(loadBalancerDescriptions.toString())
          assertThat(loadBalancerDescriptions.size() == 1, "Expected one load balancer, but was: ${loadBalancerDescriptions.size()}")
          loadBalancerDescriptions.get(0).with {
            assertThat(loadBalancerName == it.loadBalancerName, "Expected name ${loadBalancerName}, but was: ${it.loadBalancerName}")
            assertThat(securityGroups != null && [ securityGroupId ] == securityGroups, "Expected [${securityGroupId}] security groups, but was: ${securityGroups}")
          }
        }
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
