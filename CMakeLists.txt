cmake_minimum_required(VERSION 3.5)

project(AstmPhantomTest)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/Atracsys/astm-phantom-test")
set(EXTENSION_CATEGORY "IGT")
set(EXTENSION_CONTRIBUTORS "Sylvain Bernhardt, Atracsys LLC")
set(EXTENSION_DESCRIPTION "This extension for 3D Slicer is an assistant in performing the accuracy test of a tracking system as described in the ASTM standard F2554. ")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/Atracsys/astm-phantom-test/master/astm-phantom-test.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/Atracsys/astm-phantom-test/master/screenshots/screenshot1.png https://raw.githubusercontent.com/Atracsys/astm-phantom-test/master/screenshots/screenshot2.png https://raw.githubusercontent.com/Atracsys/astm-phantom-test/master/screenshots/screenshot3.png")
set(EXTENSION_DEPENDS "SlicerOpenIGTLink")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(AstmPhantomTest)

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_CPACK})