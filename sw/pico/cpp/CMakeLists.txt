cmake_minimum_required(VERSION 3.13)

# pico_sdk_import.cmake is provided by the pico-bootstrap submodule
include(${CMAKE_CURRENT_LIST_DIR}/../imported/pico-bootstrap/cmake/pico_sdk_import.cmake)

project(eyevolt C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(eyevolt
    src/main.cpp
    src/monitor.cpp
    src/generator.cpp
)

target_include_directories(eyevolt PRIVATE src)

target_link_libraries(eyevolt
    pico_stdlib
    hardware_adc
    hardware_pwm
    hardware_gpio
)

# USB CDC stdio — printf + getchar over USB (matches MicroPython USB-serial).
# The PC software connects to the Pico's USB serial port directly.
pico_enable_stdio_usb(eyevolt 1)
pico_enable_stdio_uart(eyevolt 0)

pico_add_extra_outputs(eyevolt)

target_compile_definitions(eyevolt PRIVATE
    EYEVOLT_VERSION="2.0-cpp-1.0"
)
