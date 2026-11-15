# SPDX-License-Identifier: GPL-3.0-or-later
add_executable(graphics-column-test graphics-column-test.cpp)
target_link_libraries(graphics-column-test PRIVATE Qt6::Core KSysGuard::ProcessCore)
target_compile_options(graphics-column-test PRIVATE -Wall -Wextra)
add_dependencies(graphics-column-test ksysguard_plugin_monetgraphics)
add_test(NAME graphics-column COMMAND sh ${CMAKE_CURRENT_SOURCE_DIR}/run.sh $<TARGET_FILE:graphics-column-test>
    ${CMAKE_BINARY_DIR}/plugins)
set_tests_properties(graphics-column PROPERTIES TIMEOUT 60)
