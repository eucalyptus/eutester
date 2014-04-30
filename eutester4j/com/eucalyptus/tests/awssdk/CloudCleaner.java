/*************************************************************************
 * Copyright 2009-2013 Eucalyptus Systems, Inc.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see http://www.gnu.org/licenses/.
 *
 * Please contact Eucalyptus Systems, Inc., 6755 Hollister Ave., Goleta
 * CA 93117, USA or visit http://www.eucalyptus.com/licenses/ if you need
 * additional information or have any questions.
 ************************************************************************/

package com.eucalyptus.tests.awssdk;

import com.amazonaws.services.autoscaling.model.ScalingPolicy;
import com.amazonaws.services.ec2.model.*;
import com.amazonaws.services.autoscaling.model.LaunchConfiguration;
import com.amazonaws.services.autoscaling.model.AutoScalingGroup;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 *
 *  !!! CAUTION !!!
 *  !!! WARNING !!!
 *  This will NUKE all instances, keypairs, groups, volumes, snapshots, policies, launch configs and autoscaling groups
 *
 * @author tony
 */
public class CloudCleaner {

    /**
     * @param args
     */
    public static void main(String[] args) throws Exception {
        final CloudCleaner test = new CloudCleaner();
        test.clean();
        print("Test complete");
    }

    @Test
    public void clean() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        //Terminate All instances
        List<String> instancesToTerminate = new ArrayList<String>();
        DescribeInstancesResult result =ec2.describeInstances();
        List<Reservation> reservations = result.getReservations();
        if (reservations.size() > 0){
            print("Found instances to terminate");
            for (Reservation reservation : reservations) {
                List<Instance> instances = reservation.getInstances();
                for (Instance instance : instances) {
                    print("Terminating: " + instance.getInstanceId());
                    instancesToTerminate.add(instance.getInstanceId());
                }
            }
            TerminateInstancesRequest term = new TerminateInstancesRequest();
            term.setInstanceIds(instancesToTerminate);
            ec2.terminateInstances(term);
        }  else {
            print("No instances found");
        }

        // delete all keypairs
        if (getKeyPairCount() > 0 ) {
            print("Found Keypairs to delete");
            DescribeKeyPairsResult describeKeyPairsResult = ec2.describeKeyPairs();
            for (KeyPairInfo keypair : describeKeyPairsResult.getKeyPairs()){
                deleteKeyPair(keypair.getKeyName());
            }
        } else {
            print("No keypairs found");
        }

        // delete all groups except default group
        List<SecurityGroup> groups = describeSecurityGroups();
        if (groups.size() > 1) {
            print("Found security groups to delete");
            for(SecurityGroup group : groups){
                if (!group.getGroupName().equals("default")){
                    deleteSecurityGroup(group.getGroupName());
                }
            }
        } else {
            print("No Security Groups found (other than default)");
        }

        // delete all policies
        List<ScalingPolicy> policies = describePolicies();
        if (policies.size() > 0) {
            print("Found Policies to delete");
            for(ScalingPolicy policy : policies){
                deletePolicy(policy.getPolicyName());
            }
        } else {
            print("No auto scaling policies found");
        }

        // delete launch configs
        List<LaunchConfiguration> lcs = describeLaunchConfigs();
        if (lcs.size() > 0) {
            print("Found Launch Configs to delete");
            for(LaunchConfiguration lc : lcs){
                deleteLaunchConfig(lc.getLaunchConfigurationName());
            }
        } else {
            print("No launch configs found");
        }

        // delete autoscaling groups
        List<AutoScalingGroup> asGroups = describeAutoScalingGroups();
        if (asGroups.size() > 0) {
            print("Found Auto Scaling Groups to delete");
            for(AutoScalingGroup asg : asGroups){
                deleteAutoScalingGroup(asg.getAutoScalingGroupName(), true);
            }
        } else {
            print("No auto scaling groups found");
        }

        // delete volumes
        List<Volume> volumes = ec2.describeVolumes().getVolumes();
        if (volumes.size() > 0) {
            print("Found volumes to delete");
            for(Volume vol : volumes){
                deleteVolume(vol.getVolumeId());
            }
        } else {
            print("No volumes found");
        }

        //delete snapshots
        List<Snapshot> snapshots = ec2.describeSnapshots().getSnapshots();
        if (snapshots.size() > 0) {
            print("Found snapshots to delete");
            for(Snapshot snap : snapshots){
                deleteSnapshot(snap.getSnapshotId());
            }
        } else {
            print("No volumes found");
        }
    }

}