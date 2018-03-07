#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""A simple mapping of go versions to goroot directories."""
# LINT.IfChange
GOROOTS = {
    'go1': 'goroot-1.8',
    'go1.6': 'goroot-1.6',
    'go1.8': 'goroot-1.8',
    'go1.9': 'goroot-1.9',
}
# LINT.ThenChange(
#   //depot/google/appengine/release/BUILD,
#   //depot/google/appengine/runtime/go/compiler/integration_test.cc,
#   //depot/google/appengine/runtime/go/sdk/build_sdk.go,
#   //depot/google/appengine/runtime/go/stager/gas.go,
#   //depot/google/appengine/runtime/go/testdata/BUILD,
#   //depot/google/cloud/sdk/component_build/cloud_tool_defs.py,
#   //depot/google/third_party/cloudsdk/external/linux_packaging/rpm/specs/\
#       google-cloud-sdk-app-engine-go.spec,
#   //depot/google/third_party/go/appengine/sdk/build/build-clone-zip.sh,
#   //depot/google/third_party/go/appengine/sdk/rebuild.sh)
