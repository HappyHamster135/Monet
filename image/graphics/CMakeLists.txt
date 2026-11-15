# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.22)
project(MonetGraphics LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_AUTOMOC ON)
find_package(Qt6 REQUIRED COMPONENTS Core Gui Qml)
find_package(KF6CoreAddons REQUIRED)
find_package(KF6I18n REQUIRED)
# KSysGuard's own config doesn't look for everything its process library links publicly
# (KF6::Service, and Qt Gui/Qml through its formatter), so find those first.
find_package(KF6Service REQUIRED)
find_package(KSysGuard REQUIRED)
set(MONET_GRAPHICS_USE "/usr/libexec/monet-graphics-use" CACHE STRING "The helper that measures each program's share")
add_library(ksysguard_plugin_monetgraphics MODULE monetgraphics.cpp monetgraphics.h)
# Built where Qt finds it (ksysguard/process) when the tests point at the build folder.
set_target_properties(ksysguard_plugin_monetgraphics PROPERTIES PREFIX ""
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/plugins/ksysguard/process")
target_compile_definitions(ksysguard_plugin_monetgraphics PRIVATE MONET_GRAPHICS_USE="${MONET_GRAPHICS_USE}")
target_link_libraries(ksysguard_plugin_monetgraphics PRIVATE Qt6::Core KF6::CoreAddons KF6::I18n KSysGuard::ProcessCore)
target_compile_options(ksysguard_plugin_monetgraphics PRIVATE -Wall -Wextra)
include(CTest)
if(BUILD_TESTING)
    add_subdirectory(tests)
endif()
