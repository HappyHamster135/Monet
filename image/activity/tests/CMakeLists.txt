# SPDX-License-Identifier: GPL-3.0-or-later
find_package(Qt6 REQUIRED COMPONENTS Gui Test)
find_package(PkgConfig REQUIRED)
pkg_check_modules(WaylandServer REQUIRED IMPORTED_TARGET wayland-server)
find_program(WAYLAND_SCANNER wayland-scanner REQUIRED)
find_file(DPMS_XML dpms.xml PATHS /usr/share/plasma-wayland-protocols REQUIRED)
add_custom_command(OUTPUT dpms-server-protocol.h
    COMMAND ${WAYLAND_SCANNER} server-header ${DPMS_XML} ${CMAKE_CURRENT_BINARY_DIR}/dpms-server-protocol.h DEPENDS ${DPMS_XML})
add_custom_command(OUTPUT dpms-protocol.c
    COMMAND ${WAYLAND_SCANNER} private-code ${DPMS_XML} ${CMAKE_CURRENT_BINARY_DIR}/dpms-protocol.c DEPENDS ${DPMS_XML})
add_executable(activity-test activity-test.cpp fake-wayland.cpp fake-wayland.h dpms-protocol.c dpms-server-protocol.h)
target_include_directories(activity-test PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
target_link_libraries(activity-test PRIVATE Qt6::Core Qt6::DBus Qt6::Gui Qt6::Qml Qt6::Test PkgConfig::WaylandServer)
target_compile_options(activity-test PRIVATE -Wall -Wextra -Werror)
add_dependencies(activity-test monetactivityplugin)
add_test(NAME desktop-activity COMMAND sh ${CMAKE_CURRENT_SOURCE_DIR}/run.sh $<TARGET_FILE:activity-test>)
set_tests_properties(desktop-activity PROPERTIES TIMEOUT 60 ENVIRONMENT
    "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software;QML_IMPORT_PATH=${CMAKE_BINARY_DIR}/qml")
