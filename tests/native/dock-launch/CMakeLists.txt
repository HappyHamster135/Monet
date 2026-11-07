# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.22)
project(MonetDockLaunchTest LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
find_package(Qt6 REQUIRED COMPONENTS Widgets Quick Qml Test)
find_package(KF6Config REQUIRED)
find_package(KF6I18n REQUIRED)
find_package(Plasma REQUIRED)
find_package(PlasmaQuick REQUIRED)
add_executable(dock-launch main.cpp)
target_link_libraries(dock-launch PRIVATE Qt6::Widgets Qt6::Quick Qt6::Qml Qt6::Test
    KF6::ConfigCore KF6::I18n Plasma::Plasma Plasma::PlasmaQuick)
target_compile_options(dock-launch PRIVATE -Wall -Wextra -Werror)
