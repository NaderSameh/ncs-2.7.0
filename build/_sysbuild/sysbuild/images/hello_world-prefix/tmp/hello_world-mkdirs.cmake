# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.5)

file(MAKE_DIRECTORY
  "D:/ncs-D/v2.7.0-rc3/zephyr/samples/hello_world"
  "D:/ncs-D/v2.7.0-rc3/build/hello_world"
  "D:/ncs-D/v2.7.0-rc3/build/_sysbuild/sysbuild/images/hello_world-prefix"
  "D:/ncs-D/v2.7.0-rc3/build/_sysbuild/sysbuild/images/hello_world-prefix/tmp"
  "D:/ncs-D/v2.7.0-rc3/build/_sysbuild/sysbuild/images/hello_world-prefix/src/hello_world-stamp"
  "D:/ncs-D/v2.7.0-rc3/build/_sysbuild/sysbuild/images/hello_world-prefix/src"
  "D:/ncs-D/v2.7.0-rc3/build/_sysbuild/sysbuild/images/hello_world-prefix/src/hello_world-stamp"
)

set(configSubDirs )
foreach(subDir IN LISTS configSubDirs)
    file(MAKE_DIRECTORY "D:/ncs-D/v2.7.0-rc3/build/_sysbuild/sysbuild/images/hello_world-prefix/src/hello_world-stamp/${subDir}")
endforeach()
if(cfgdir)
  file(MAKE_DIRECTORY "D:/ncs-D/v2.7.0-rc3/build/_sysbuild/sysbuild/images/hello_world-prefix/src/hello_world-stamp${cfgdir}") # cfgdir has leading slash
endif()
