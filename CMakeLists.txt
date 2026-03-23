cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(NpzLoader)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/turtleizzy/slicer-npz-loader")
set(EXTENSION_CATEGORY "Informatics")
set(EXTENSION_CONTRIBUTORS "TurtleIzzy")
set(EXTENSION_DESCRIPTION "Load volume and segmentation data from NPZ/NPY files into 3D Slicer.")
set(EXTENSION_ICONURL "")
set(EXTENSION_SCREENSHOTURLS "")
set(EXTENSION_DEPENDS "NA")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(NpzLoader)

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
