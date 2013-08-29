# Copyright 2008--2010 Mattias Norrby
#
# This file is part of Test Dept..
#
# Test Dept. is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Test Dept. is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Test Dept..  If not, see <http://www.gnu.org/licenses/>.

# A simple test project using test object sources in other directories
# than with one C file as SUT. This project has no stubs, but it is
# easily added using the TEST_DEPT_POSSIBLE_STUBS variable pointing to
# a header file stating prototypes for stub functions.

CC=gcc -std=gnu99 -ggdb

# The three rows below are only needed if test-dept is not installed
# in your environment. They refer relatively to the unpacked dist in ../..
#TEST_DEPT_BIN_PATH=../../src
#TEST_DEPT_INCLUDE_PATH=$(TEST_DEPT_BIN_PATH)
#CPPFLAGS=-I$(TEST_DEPT_INCLUDE_PATH) -I.
# If you use them, please also qualify the last include-file with
# a prefix, like this: $(TEST_DEPT_INCLUDE_PATH)/test-dept.mk

TEST_DEPT_SRC_DIR=../../eucalyptus/cluster

override CPPFLAGS+=-I$(TEST_DEPT_SRC_DIR)
override CPPFLAGS+=-I../../eucalyptus/util -I../../eucalyptus/storage -I../../eucalyptus/net -I../../eucalyptus/node -I../../eucalyptus/cluster/generated/ -I/usr/include/axis2-1.6.0/
TEST_SRCS=scheduler_test.c

check:	test_dept_run

clean:
	rm -f *.o *_test

scheduler_test: scheduler_test.o

include test-dept.mk
