package com.eucalyptus.tests.awssdk;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Properties;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import org.jclouds.Constants;
import org.jclouds.ContextBuilder;
import static com.eucalyptus.tests.awssdk.Eutester4j.*;
import org.jclouds.compute.ComputeService;
import org.jclouds.compute.ComputeServiceContext;
import org.jclouds.compute.domain.ComputeMetadata;
import org.jclouds.domain.Location;
import org.jclouds.ec2.EC2AsyncClient;
import org.jclouds.ec2.EC2Client;
import org.jclouds.ec2.domain.KeyPair;
import org.jclouds.ec2.domain.PublicIpInstanceIdPair;
import org.jclouds.ec2.domain.SecurityGroup;
import org.jclouds.ec2.domain.Snapshot;
import org.jclouds.ec2.domain.Volume;
import org.jclouds.logging.log4j.config.Log4JLoggingModule;
import org.jclouds.rest.RestContext;
import org.testng.annotations.Test;
import com.google.common.collect.ImmutableSet;
import com.google.inject.Module;

/**
 * Tests for JClouds library
 *
 * @see <a href="http://www.jclouds.org/">jclouds.org</a>
 * @see <a href="http://github.com/jclouds/">jclouds on github.com</a>
 */
public class JCloudsTest {
    private static final String securityGroupName   = "SECURITY-GROUP-" + eucaUUID();
    private static final String keyName             = "KEYPAIR-" + eucaUUID();
    private static final String snapshotDescription = "Test Snapshot";
    private static final String eucalyptusRegion    = "eucalyptus";

    /**
     * Test jclouds functionality related to EC2 describe actions.
     */
    @Test
    public void testDescribeEC2( ) throws Exception {
        testInfo( this.getClass().getSimpleName() );
        getCloudInfo( );

        final List<Runnable> cleanup = new ArrayList<Runnable>();
        try {
            // create resources for use in test and register clean up tasks
            cleanup.add( new Runnable() {
                @Override
                public void run() {
                    deleteKeyPair( keyName );
                }
            } );
            cleanup.add( new Runnable() {
                @Override
                public void run() {
                    deleteSecurityGroup( securityGroupName );
                }
            } );
            print( "Creating security group…" );
            createSecurityGroup( securityGroupName, "A Test Security Group" );
            print( "Creating key pair…" );
            createKeyPair( keyName );
            print( "Creating volume…" );
            final String volumeId = createVolume( findAvailablityZone(), 1 );
            print( "Waiting for volume availability…" );
            waitForVolumes( TimeUnit.MINUTES.toMillis( 10 ) );
            cleanup.add( new Runnable() {
                @Override
                public void run() {
                    deleteVolume( volumeId );
                }
            } );
            print( "Creating snapshot…" );
            final String snapshotId = createSnapshot( volumeId, snapshotDescription );
            print( "Waiting for snapshot availability…" );
            waitForSnapshots( TimeUnit.MINUTES.toMillis( 10 ) );
            cleanup.add( new Runnable() {
                @Override
                public void run() {
                    deleteSnapshot( snapshotId );
                }
            } );
            print( "Allocating elastic ip…" );
            final String ip = allocateElasticIP( );
            cleanup.add( new Runnable() {
                @Override
                public void run() {
                    releaseElasticIP( ip );
                }
            } );
            runInstances( findImage( ), keyName, "m1.small", Collections.singletonList( securityGroupName ), 1, 1 );
            final String id = getLastlaunchedInstance().get(0).getInstanceId();
            cleanup.add( new Runnable() {
                @Override
                public void run() {
                    terminateInstances( Collections.singletonList( id ) );
                    waitForInstances( TimeUnit.MINUTES.toMillis( 10 ) );
                }
            } );

            // begin jclouds test
            final ContextBuilder builder = initContextBuilder( ACCESS_KEY, SECRET_KEY );
            final ComputeService compute = builder.buildView( ComputeServiceContext.class ).getComputeService( );
            final EC2Client ec2Client = builder.<RestContext<EC2Client, EC2AsyncClient>>build( ).getApi( );

            print( "Calling listAssignableLocations…" );
            final Set<? extends Location> locations = compute.listAssignableLocations();
            print( "Total Number of Locations = " + locations.size() );
            print( "Retrieved locations:" + locations );
            boolean foundRegion = false;
            boolean foundZone = false;
            for (final Location location: locations) {
                print( "\t" + location );
                switch ( location.getScope( ) ) {
                    case REGION:
                        foundRegion = true;
                        break;
                    case ZONE:
                        foundZone = true;
                        break;
                }
            }
            assertThat( foundRegion, "Region not found" );
            assertThat( foundZone, "Availability zone not found" );

            print( "Calling listImages…" );
            final Set<? extends ComputeMetadata> images = compute.listImages();
            print( "Total Number of Images = " + images.size() );
            assertThat( !images.isEmpty(), "Images not found" );
            for (final ComputeMetadata image: images) {
                print( "\t" + image );
            }

            print( "Calling listNodes…" );
            final Set<? extends ComputeMetadata> nodes = compute.listNodes();
            print( "Total Number of Nodes = " + nodes.size() );
            boolean foundInstance = false;
            for (final ComputeMetadata node: nodes) {
                print( "\t" + node );
                if ( id.equals( node.getProviderId() ) ) {
                    foundInstance = true;
                }
            }
            assertThat( foundInstance, "Instance ("+id+") not found" );

            print( "Calling describeKeyPairsInRegion…" );
            final Set<KeyPair> keyPairs = ec2Client.getKeyPairServices().describeKeyPairsInRegion( eucalyptusRegion );
            print( "Total Number of KeyPairs = " + keyPairs.size() );
            boolean foundKeyPair = false;
            for (final KeyPair keyPair: keyPairs) {
                print( "\t" + keyPair );
                if ( keyName.equals( keyPair.getKeyName() ) ) {
                    foundKeyPair = true;
                }
            }
            assertThat( foundKeyPair, "KeyPair ("+keyName+") not found" );

            print( "Calling describeSecurityGroupsInRegion…" );
            final Set<SecurityGroup> securityGroups = ec2Client.getSecurityGroupServices().describeSecurityGroupsInRegion( eucalyptusRegion );
            print( "Total Number of SecurityGroups = " + securityGroups.size() );
            boolean foundSecurityGroup= false;
            for (final SecurityGroup securityGroup: securityGroups) {
                print( "\t" + securityGroup );
                if ( securityGroupName.equals( securityGroup.getName( ) ) ) {
                    foundSecurityGroup = true;
                }
            }
            assertThat( foundSecurityGroup, "SecurityGroup ("+ securityGroupName +") not found" );

            print( "Calling describeAddressesInRegion…" );
            final Set<PublicIpInstanceIdPair> ips = ec2Client.getElasticIPAddressServices().describeAddressesInRegion( eucalyptusRegion );
            print( "Total Number of IPS = " + ips.size() );
            boolean foundElasticIP = false;
            for (final PublicIpInstanceIdPair ipp: ips) {
                print( "\t" + ipp.getPublicIp() );
                if ( ip.equals( ipp.getPublicIp() ) ) {
                    foundElasticIP = true;
                }
            }
            assertThat( foundElasticIP, "Elastic IP ("+ ip +") not found" );

            print( "Calling describeSnapshotsInRegion…" );
            final Set<Snapshot> snapshots = ec2Client.getElasticBlockStoreServices().describeSnapshotsInRegion( eucalyptusRegion );
            print( "Total Number of Snapshots = " + snapshots.size() );
            boolean foundSnapshot = false;
            for (final Snapshot snapshot: snapshots) {
                print( "\t" + snapshot );
                if ( snapshotId.equals( snapshot.getId() ) ) {
                    foundSnapshot = true;
                }
            }
            assertThat( foundSnapshot, "Snapshot ("+ snapshotId +") not found" );

            print( "Calling describeVolumesInRegion…" );
            final Set<Volume> volumes = ec2Client.getElasticBlockStoreServices().describeVolumesInRegion( eucalyptusRegion );
            print( "Total Number of Volumes = " + volumes.size() );
            boolean foundVolume = false;
            for (final Volume volume: volumes) {
                print( "\t" + volume );
                if ( volumeId.equals( volume.getId() ) ) {
                    foundVolume = true;
                }
            }
            assertThat( foundVolume, "Volume ("+ volumeId +") not found" );

            print( "Test complete" );
        } finally {
            Collections.reverse( cleanup );
            for ( final Runnable runnable : cleanup ) {
                try {
                    runnable.run( );
                } catch ( Exception e ) {
                    e.printStackTrace();
                }
            }
        }
    }

    private static ContextBuilder initContextBuilder( String accessKeyIdentifier, String secretKey ) {
        final Iterable<Module> modules = ImmutableSet.<Module>of( new Log4JLoggingModule( ) );
        final Properties properties = new Properties();
        properties.setProperty( Constants.PROPERTY_ENDPOINT, EC2_ENDPOINT );
        return ContextBuilder.newBuilder( "ec2" )
                .credentials( accessKeyIdentifier, secretKey )
                .modules( modules )
                .overrides( properties );
    }
}