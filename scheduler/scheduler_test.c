/* Copyright 2008 Mattias Norrby
 * 
 * Copyright (c) 2012  Nokia Siemens Networks Inc
 * 
 * This file is based on a file from Test Dept.
 * 
 * Eutester. is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * Eutester. is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with Test Dept..  If not, see <http://www.gnu.org/licenses/>.

 * Author:
 *   2008 Mattias Norrby
 *   2012 Michael De La Rue on behalf of Nokia Siemens Networks Sp. z o.o.
 *
 */

#include <test-dept.h>
#include "handlers.h"
#include <assert.h>

/*
 * the following are global variables within the Eucalyptus cluster controller
 * each test which relies on them should set them up at the start of the test.
 */

ccConfig *config;
ccResourceCache *resourceCache;

/* given that I have a cloud which a resource in RESDOWN state
 * when I attempt to schedule an instance with round_robin
 * then it should not be scheduled on that node.
 */ 


int logprintfl(int level, const char *format, ...) {
  return 1; 
}

int powerUp(ccResource *res) {
  return 1; 
}

void setup_empty_cloud() {
  ccResource *res;
  int i;

  config=malloc(sizeof(ccConfig));
  assert(NULL != config );
  /* FIXME: the following should be a macro both here and in main code */
  config->schedState=0; 

  resourceCache=malloc(sizeof(ccResourceCache));
  assert(NULL != resourceCache );
  for(i=0; i< MAXNODES; i++ ){
    /* FIXME: the following should be a macro both here and in main code */
    res=&(resourceCache->resources[0]);
    res->state=RESDOWN;
  }

  for(i=0; i<5; i++) {
    /* FIXME: the following should be macros both here and in main code */
    res=&(resourceCache->resources[i]);
    res->state=RESUP;
    res->availMemory = 44;
    res->availDisk = 88;
    res->availCores = 8;
  }
  resourceCache->numResources=6;

}

/* @setup_full_cloud - set config and resource as if the cloud is full
 * 
 * This sets up the config and resourceCache global variables to point
 * to data showing that the cloud is completely full.
 * 
 * N.B. the data space required is malloced in this function.  
 */

void setup_full_cloud() {
  ccResource *res;
  int i;

  config=malloc(sizeof(ccConfig));
  assert(NULL != config );
  /* FIXME: the following should be a macro both here and in main code */
  config->schedState=0; 

  resourceCache=malloc(sizeof(ccResourceCache));
  assert(NULL != resourceCache );
  for(i=0; i< MAXNODES; i++ ){
    /* FIXME: the following should be a macro both here and in main code */
    res=&(resourceCache->resources[0]);
    res->state=RESDOWN;
  }
  
  for(i=0; i<2; i++) {
    /* FIXME: the following should be macros both here and in main code */
    res=&(resourceCache->resources[i]);
    res->state=RESUP;
    res->availMemory = 0;
    res->availDisk = 7;
    res->availCores = 0;
  }
  resourceCache->numResources=2;

}

/* given that I have a cloud which has empty nodes with capacity for
 * an instance when I attempt to schedule an instance with round_robin
 * then it should be scheduled on the first node
 */ 

void test_empty_cloud_round_robin_scheduler() {
  virtualMachine vm;
  int outresid;
  int ret;
  ccResource *res;

  setup_empty_cloud();
  ret=schedule_instance_roundrobin(&vm, &outresid);

  assert_equals(0, ret);

  res=&(resourceCache->resources[0]);
  
  assert_equals(0, outresid);
}

/* given that I have a cloud which has no nodes with capacity for an instance
 * when I attempt to schedule an instance with round_robin
 * then I should get an error
 */ 

void test_full_cloud_round_robin_scheduler() {
  virtualMachine vm;
  int outresid;
  int ret;
  ccResource *res;

  vm.mem = 5;
  vm.disk = 5;
  vm.cores = 5;
  setup_full_cloud();
  ret=schedule_instance_roundrobin(&vm, &outresid);

  assert_not_equals(0, ret);

  res=&(resourceCache->resources[0]);
  
  assert_equals(0, outresid);
}

/*
 * @apply_scheduler - simulate running the scheduler 
 * 
 * 
 *
 */

int apply_scheduler(virtualMachine *vm, char *targetNode, int *outresid) { 
  int ret;
  ccResource *resource;
  ret=schedule_instance(vm, targetNode, outresid) ;
  resource = &(resourceCache->resources[*outresid]);
  resource->availMemory -= vm->mem;
  resource->availDisk -= vm->disk;
  resource->availCores -= vm->cores;
  return ret;
}
  
/* given that I have a cloud which has empty nodes with capacity for
 * multiple instances when I repeatedly schedule small instances then 
 * the scheduling should succeed
 */ 

void test_schedule_multiple() {
  virtualMachine vm;
  int outresid;
  int ret,i;
  ccResource *res;

  vm.mem = 5;
  vm.disk = 5;
  vm.cores = 2;

  setup_empty_cloud();
  config->schedPolicy = SCHEDROUNDROBIN;

  for (i=0; i<15; i++) {
    ret=apply_scheduler(&vm, NULL,&outresid);
    assert_equals(0, ret);
  }

}

/* given that I have a cloud which has empty nodes with capacity for
 * multiple instances when I repeatedly schedule small instances then 
 * the scheduling should succeed
 */ 

void test_schedule_big_after_many_small() {
  virtualMachine vm;
  int outresid;
  int ret,i;
  ccResource *res;

  vm.mem = 5;
  vm.disk = 5;
  vm.cores = 2;

  setup_empty_cloud();
  config->schedPolicy = SCHEDROUNDROBIN;

  for (i=0; i<15; i++) {
    ret=apply_scheduler(&vm, NULL,&outresid);
    assert_equals(0, ret);
  }

  vm.mem = 5;
  vm.disk = 5;
  vm.cores = 4;

  ret=apply_scheduler(&vm, NULL,&outresid);
  assert_equals(0, ret);
}

void teardown() {
  ;
}
