# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.5)

file(MAKE_DIRECTORY
  "D:/ncs-D/v2.7.0-rc3/zephyr/samples/modem_test"
  "D:/ncs-D/v2.7.0-rc3/koko/modem_test"
  "D:/ncs-D/v2.7.0-rc3/koko/_sysbuild/sysbuild/images/modem_test-prefix"
  "D:/ncs-D/v2.7.0-rc3/koko/_sysbuild/sysbuild/images/modem_test-prefix/tmp"
  "D:/ncs-D/v2.7.0-rc3/koko/_sysbuild/sysbuild/images/modem_test-prefix/src/modem_test-stamp"
  "D:/ncs-D/v2.7.0-rc3/koko/_sysbuild/sysbuild/images/modem_test-prefix/src"
  "D:/ncs-D/v2.7.0-rc3/koko/_sysbuild/sysbuild/images/modem_test-prefix/src/modem_test-stamp"
)

set(configSubDirs )
foreach(subDir IN LISTS configSubDirs)
    file(MAKE_DIRECTORY "D:/ncs-D/v2.7.0-rc3/koko/_sysbuild/sysbuild/images/modem_test-prefix/src/modem_test-stamp/${subDir}")
endforeach()
if(cfgdir)
  file(MAKE_DIRECTORY "D:/ncs-D/v2.7.0-rc3/koko/_sysbuild/sysbuild/images/modem_test-prefix/src/modem_test-stamp${cfgdir}") # cfgdir has leading slash
endif()
