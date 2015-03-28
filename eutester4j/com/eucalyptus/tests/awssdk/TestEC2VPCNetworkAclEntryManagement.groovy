package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.EC2_ENDPOINT
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * This application tests management of network ACL entries for EC2 VPC.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9610
 */
class TestEC2VPCNetworkAclEntryManagement {

  private final AWSCredentialsProvider credentials


  public static void main( String[] args ) throws Exception {
    new TestEC2VPCNetworkAclEntryManagement( ).EC2VPCNetworkAclEntryManagementTest( )
  }

    public TestEC2VPCNetworkAclEntryManagement(){
        minimalInit()
        this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
    }

  private AmazonEC2 getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( credentials )
    ec2.setEndpoint( EC2_ENDPOINT )
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
  public void EC2VPCNetworkAclEntryManagementTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    // Find an AZ to use
    final DescribeAvailabilityZonesResult azResult = ec2.describeAvailabilityZones();

    assertThat( azResult.getAvailabilityZones().size() > 0, "Availability zone not found" );

    final String availabilityZone = azResult.getAvailabilityZones().get( 0 ).getZoneName();
    print( "Using availability zone: " + availabilityZone );

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      ec2.with{
        print( 'Creating VPC' )
        String defaultDhcpOptionsId = null
        String vpcId = createVpc( new CreateVpcRequest( cidrBlock: '10.100.215.0/28' ) ).with {
          vpc.with {
            defaultDhcpOptionsId = dhcpOptionsId
            vpcId
          }
        }
        print( "Created VPC with id ${vpcId}" )
        cleanupTasks.add{
          print( "Deleting VPC ${vpcId}" )
          deleteVpc( new DeleteVpcRequest( vpcId: vpcId ) )
        }

        print( 'Creating network ACL' )
        String networkAclId = createNetworkAcl( new CreateNetworkAclRequest( vpcId: vpcId ) ).with {
          networkAcl.networkAclId
        }
        print( "Created network acl with id ${networkAclId}" )
        cleanupTasks.add{
          print( "Deleting network acl ${networkAclId}" )
          deleteNetworkAcl( new DeleteNetworkAclRequest( networkAclId: networkAclId ) )
        }

        print( "Creating all protocol entry for network ACL ${networkAclId}" )
        createNetworkAclEntry( new CreateNetworkAclEntryRequest(
            networkAclId: networkAclId,
            ruleNumber: 200,
            ruleAction: 'allow',
            egress: false,
            cidrBlock: '0.0.0.0/0',
            protocol: -1
        ) )

        print( "Creating tcp protocol entry for network ACL ${networkAclId}" )
        createNetworkAclEntry( new CreateNetworkAclEntryRequest(
            networkAclId: networkAclId,
            ruleNumber: 300,
            ruleAction: 'allow',
            egress: false,
            cidrBlock: '0.0.0.0/0',
            protocol: 6,
            portRange: new PortRange(
              from: 22,
              to: 22
            )
        ) )

        print( "Creating udp protocol entry for network ACL ${networkAclId}" )
        createNetworkAclEntry( new CreateNetworkAclEntryRequest(
            networkAclId: networkAclId,
            ruleNumber: 300,
            ruleAction: 'allow',
            egress: true,
            cidrBlock: '0.0.0.0/0',
            protocol: 'udp',
            portRange: new PortRange(
                from: 50,
                to: 59
            )
        ) )

        print( "Creating icmp protocol entry for network ACL ${networkAclId}" )
        createNetworkAclEntry( new CreateNetworkAclEntryRequest(
            networkAclId: networkAclId,
            ruleNumber: 1,
            ruleAction: 'allow',
            egress: true,
            cidrBlock: '0.0.0.0/0',
            protocol: 1,
            icmpTypeCode: new IcmpTypeCode(
                type: 8,
                code: -1
            )
        ) )

        print( "Verifying network ACL entries for ${networkAclId}" )
        describeNetworkAcls( new DescribeNetworkAclsRequest( networkAclIds: [ networkAclId ] ) ).with {
          assertThat( networkAcls.size( ) == 1, "Expected one network ACL, but was: ${networkAcls.size( )}" )
          networkAcls[0].with {
            assertThat( entries.size( ) == 6, "Expected 6 entries, but was: ${entries.size( )}" )
            entries[0].with {
              assertThat( ruleNumber == 1, "Expected rule number 1, but was: ${ruleNumber}" )
              assertThat( ruleAction == 'allow', "Expected rule action allow, but was: ${ruleAction}" )
              assertThat( egress, "Expected egress rule, but was: ingress" )
              assertThat( cidrBlock == '0.0.0.0/0', "Expected cidr 0.0.0.0/0, but was: ${cidrBlock}" )
              assertThat( protocol == '1', "Expected protocol 1, but was: ${protocol}" )
              assertThat( icmpTypeCode != null, "Expected icmp type and code" )
              icmpTypeCode.with {
                assertThat( type == 8, "Expected icmp type 8, but was: ${type}" )
                assertThat( code == -1, "Expected icmp code -1, but was: ${type}" )
              }
            }
            entries[1].with {
              assertThat( ruleNumber == 300, "Expected rule number 300, but was: ${ruleNumber}" )
              assertThat( ruleAction == 'allow', "Expected rule action allow, but was: ${ruleAction}" )
              assertThat( egress, "Expected egress rule, but was: ingress" )
              assertThat( cidrBlock == '0.0.0.0/0', "Expected cidr 0.0.0.0/0, but was: ${cidrBlock}" )
              assertThat( protocol == '17', "Expected protocol 17, but was: ${protocol}" )
              assertThat( portRange != null, "Expected port range" )
              portRange.with {
                assertThat( from == 50, "Expected from port 50, but was: ${from}" )
                assertThat( to == 59, "Expected to port 59, but was: ${to}" )
              }
            }
            entries[2].with {
              assertThat( ruleNumber == 32767, "Expected rule number 32767, but was: ${ruleNumber}" )
              assertThat( ruleAction == 'deny', "Expected rule action deny, but was: ${ruleAction}" )
              assertThat( egress, "Expected egress rule, but was: ingress" )
              assertThat( cidrBlock == '0.0.0.0/0', "Expected cidr 0.0.0.0/0, but was: ${cidrBlock}" )
              assertThat( protocol == '-1', "Expected protocol -1, but was: ${protocol}" )
            }
            entries[3].with {
              assertThat( ruleNumber == 200, "Expected rule number 200, but was: ${ruleNumber}" )
              assertThat( ruleAction == 'allow', "Expected rule action allow, but was: ${ruleAction}" )
              assertThat( !egress, "Expected ingress rule, but was: egress" )
              assertThat( cidrBlock == '0.0.0.0/0', "Expected cidr 0.0.0.0/0, but was: ${cidrBlock}" )
              assertThat( protocol == '-1', "Expected protocol -1, but was: ${protocol}" )
            }
            entries[4].with {
              assertThat( ruleNumber == 300, "Expected rule number 300, but was: ${ruleNumber}" )
              assertThat( ruleAction == 'allow', "Expected rule action allow, but was: ${ruleAction}" )
              assertThat( !egress, "Expected ingress rule, but was: egress" )
              assertThat( cidrBlock == '0.0.0.0/0', "Expected cidr 0.0.0.0/0, but was: ${cidrBlock}" )
              assertThat( protocol == '6', "Expected protocol 6, but was: ${protocol}" )
              portRange.with {
                assertThat( from == 22, "Expected from port 22, but was: ${from}" )
                assertThat( to == 22, "Expected to port 22, but was: ${to}" )
              }
            }
            entries[5].with {
              assertThat( ruleNumber == 32767, "Expected rule number 32767, but was: ${ruleNumber}" )
              assertThat( ruleAction == 'deny', "Expected rule action deny, but was: ${ruleAction}" )
              assertThat( !egress, "Expected ingress rule, but was: egress" )
              assertThat( cidrBlock == '0.0.0.0/0', "Expected cidr 0.0.0.0/0, but was: ${cidrBlock}" )
              assertThat( protocol == '-1', "Expected protocol -1, but was: ${protocol}" )
            }
          }
        }

        print( "Deleting imcp protocol entry for network ACL ${networkAclId}" )
        deleteNetworkAclEntry( new DeleteNetworkAclEntryRequest(
            networkAclId: networkAclId,
            ruleNumber: 1,
            egress: true
        ) )

        print( "Verifying imcp protocol entry deleted for ${networkAclId}" )
        describeNetworkAcls( new DescribeNetworkAclsRequest( networkAclIds: [ networkAclId ] ) ).with {
          assertThat( networkAcls.size( ) == 1, "Expected one network ACL, but was: ${networkAcls.size( )}" )
          networkAcls[0].with {
            assertThat( entries.size( ) == 5, "Expected 5 entries, but was: ${entries.size( )}" )
            entries[0].with {
              assertThat( ruleNumber == 300, "Expected rule number 300, but was: ${ruleNumber}" )
              assertThat( egress, "Expected egress rule, but was: ingress" )
            }
            entries[1].with {
              assertThat( ruleNumber == 32767, "Expected rule number 32767, but was: ${ruleNumber}" )
              assertThat( egress, "Expected egress rule, but was: ingress" )
            }
            entries[2].with {
              assertThat( ruleNumber == 200, "Expected rule number 200, but was: ${ruleNumber}" )
              assertThat( !egress, "Expected ingress rule, but was: egress" )
            }
            entries[3].with {
              assertThat( ruleNumber == 300, "Expected rule number 300, but was: ${ruleNumber}" )
              assertThat( !egress, "Expected ingress rule, but was: egress" )
            }
            entries[4].with {
              assertThat( ruleNumber == 32767, "Expected rule number 32767, but was: ${ruleNumber}" )
              assertThat( !egress, "Expected ingress rule, but was: egress" )
            }
          }
        }

        print( "Replacing tcp protocol entry for network ACL ${networkAclId}" )
        replaceNetworkAclEntry( new ReplaceNetworkAclEntryRequest(
            networkAclId: networkAclId,
            ruleNumber: 300,
            ruleAction: 'allow',
            egress: false,
            cidrBlock: '10.0.0.0/8',
            protocol: 6,
            portRange: new PortRange(
                from: 22,
                to: 42
            )
        ) )

        print( "Verifying tcp protocol entry replaced for ${networkAclId}" )
        describeNetworkAcls( new DescribeNetworkAclsRequest( networkAclIds: [ networkAclId ] ) ).with {
          assertThat( networkAcls.size( ) == 1, "Expected one network ACL, but was: ${networkAcls.size( )}" )
          networkAcls[0].with {
            assertThat( entries.size( ) == 5, "Expected 5 entries, but was: ${entries.size( )}" )
            entries[0].with {
              assertThat( ruleNumber == 300, "Expected rule number 300, but was: ${ruleNumber}" )
              assertThat( egress, "Expected egress rule, but was: ingress" )
            }
            entries[1].with {
              assertThat( ruleNumber == 32767, "Expected rule number 32767, but was: ${ruleNumber}" )
              assertThat( egress, "Expected egress rule, but was: ingress" )
            }
            entries[2].with {
              assertThat( ruleNumber == 200, "Expected rule number 200, but was: ${ruleNumber}" )
              assertThat( !egress, "Expected ingress rule, but was: egress" )
            }
            entries[3].with {
              assertThat( ruleNumber == 300, "Expected rule number 300, but was: ${ruleNumber}" )
              assertThat( ruleAction == 'allow', "Expected rule action allow, but was: ${ruleAction}" )
              assertThat( !egress, "Expected ingress rule, but was: egress" )
              assertThat( cidrBlock == '10.0.0.0/8', "Expected cidr 10.0.0.0/8, but was: ${cidrBlock}" )
              assertThat( protocol == '6', "Expected protocol 6, but was: ${protocol}" )
              assertThat( portRange != null, "Expected port range" )
              portRange.with {
                assertThat( from == 22, "Expected from port 22, but was: ${from}" )
                assertThat( to == 42, "Expected to port 42, but was: ${to}" )
              }
            }
            entries[4].with {
              assertThat( ruleNumber == 32767, "Expected rule number 32767, but was: ${ruleNumber}" )
              assertThat( !egress, "Expected ingress rule, but was: egress" )
            }
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
          // Some not-found errors are expected here so may need to be suppressed
          e.printStackTrace()
        }
      }
    }
  }
}
