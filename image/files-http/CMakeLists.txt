cmake_minimum_required(VERSION 3.22)
project(MonetKioHttp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_SKIP_RPATH ON)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/plugins")

find_package(ECM REQUIRED NO_MODULE)
list(APPEND CMAKE_MODULE_PATH "${ECM_MODULE_PATH}")
include(ECMQtDeclareLoggingCategory)
include(KDEInstallDirs)
find_package(Qt6 REQUIRED COMPONENTS Network Xml)
find_package(KF6 REQUIRED COMPONENTS CoreAddons KIO I18n Config)

add_library(kio_http MODULE http.cpp)
set_target_properties(kio_http PROPERTIES PREFIX "")
target_include_directories(kio_http PRIVATE "${KIO_CORE_SOURCE_DIR}" "${CMAKE_CURRENT_BINARY_DIR}")
ecm_qt_declare_logging_category(kio_http
    HEADER debug.h
    IDENTIFIER KIOHTTP_LOG
    CATEGORY_NAME kf.kio.workers.http
)
target_link_libraries(kio_http PRIVATE KF6::KIOCore KF6::I18n KF6::ConfigCore Qt6::Network Qt6::Xml)
