# SPDX-License-Identifier: BSD-3-Clause
cmake_minimum_required(VERSION 3.22)
project(MonetMediaKeys LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_AUTOMOC ON)
set(QT_MAJOR_VERSION 6)
find_package(ECM REQUIRED NO_MODULE)
list(APPEND CMAKE_MODULE_PATH ${ECM_MODULE_PATH})
include(KDEInstallDirs6)
include(KDECMakeSettings)
find_package(Qt6 REQUIRED COMPONENTS Core DBus Widgets Qml)
find_package(KF6 REQUIRED COMPONENTS GlobalAccel XmlGui I18n DBusAddons CoreAddons KIO Service)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
# Compile the matching Fedora shortcut registrations against its installed player library.
find_library(KMPRIS NAMES libkmpris.so.6 REQUIRED)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/adapt.py"
    "${UPSTREAM_SOURCE}/libkmpris/kded/mprisservice.cpp" "${UPSTREAM_SOURCE}/libkmpris/kded/mprisservice.h"
    "${UPSTREAM_SOURCE}/libkmpris/kded/mprisservice.json")
execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/adapt.py"
    "${UPSTREAM_SOURCE}/libkmpris/kded" "${CMAKE_CURRENT_BINARY_DIR}" COMMAND_ERROR_IS_FATAL ANY)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/kmpris_export.h" "#pragma once\n#include <QtCore/qglobal.h>\n#define KMPRIS_EXPORT Q_DECL_IMPORT\n#define KMPRIS_NO_EXPORT\n")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
kcoreaddons_add_plugin(mprisservice SOURCES "${CMAKE_CURRENT_BINARY_DIR}/mprisservice.cpp"
    "${CMAKE_CURRENT_BINARY_DIR}/mprisservice.h" rules.cpp rules.h INSTALL_NAMESPACE "kf6/kded")
target_include_directories(mprisservice PRIVATE "${UPSTREAM_SOURCE}/libkmpris" "${CMAKE_CURRENT_BINARY_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}")
target_compile_definitions(mprisservice PRIVATE TRANSLATION_DOMAIN="libkmpris")
target_link_libraries(mprisservice PRIVATE Qt6::Qml Qt6::DBus KF6::CoreAddons KF6::DBusAddons KF6::GlobalAccel
    KF6::I18n KF6::XmlGui KF6::KIOGui KF6::Service "${KMPRIS}")
