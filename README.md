# ASTM Phantom Test
This software is a module for [3D Slicer](https://www.slicer.org) to perform the accuracy test of a tracking system as described in the [standard ASTM F2554](https://www.astm.org/f2554-18.html).
(:warning: The present procedures are based on the guidelines outlined in the upcoming revision of the standard due to late 2022).

This test relies on a calibration object, hereafter referred to as the "phantom", of known dimensions measured by a [CMM](https://en.wikipedia.org/wiki/Coordinate-measuring_machine). Performing measurements on such a phantom provides a reliable assessment of the tracking system accuracy and precision.

# Table of contents
- [Material](#material)
- [Required software](#requiredSoft)
   - [PLUS Toolkit](#plusInstall)
   - [3D Slicer](#slicerInstall)
- [Parameter files](#paramFiles)
   - [Pointer file](#pointerFile)
   - [Working volume file](#wvFile)
   - [Phantom file](#phantomFile)
- [Usage](#usage)
   - [Setup](#setup)
   - [Launching the software](#launch)
   - [Running the tests](#tests)
   - [Getting the results](#results)
- [Troubleshooting](#trouble)

# Material<a name="material"></a>
To perform the test, the following items are necessary:
- [ ] A **phantom** with a distribution of divots and a reference tracked array rigidly attached. See the [standard](https://www.astm.org/f2554-18.html) for requirements and recommendations regarding phantom design and manufacturing.
- [ ] The tested **tracking system**, typically including
  - [ ] A **pointer** composed of a tracked array and a shaft with a pointy end fitting the divots.
  - [ ] A **tracker** which spatially locates the various arrays aforementionned. Various technologies can be utilized (optical, magnetic, etc).
  - [ ] A **computer** to receive and analyze the tracking data. The present software is to be installed on this computer, alongside the various supporting tools and libraries. Since this software also provides visual guidance to perform the test, a computer monitor is recommended.

# Required software<a name="requiredSoft"></a>
## PLUS Toolkit<a name="plusInstall"></a>
[PLUS Toolkit](https://plustoolkit.github.io/) is a free, open-source set of software tools for Computer-Assisted Surgery, which includes a wrapper for SDK's from many manufacturers of tracking systems. This enables a standardization of the tracking data streaming from the tracker to the computer, thanks to an [OpenIGTLink](http://openigtlink.org) server (i.e. the **Plus Server**).

### Installation<a name="plusDownload"></a>
Pre-built installers for more than twenty systems are available for Windows from the [Download page](https://plustoolkit.github.io/download.html). To know which installer to choose, the user may refer to the table at the bottom of that page. The version must be 2.9.0.202207x or more recent. Since the 2.9 release is not stable yet, one can access it from the **Latest Development Snapshot**.

:warning: Beside the wrappers, PLUS Toolkit also includes the SDK for most systems. For Atracsys trackers though, the SDK needs to be installed separately on the computer. Also, the Atracsys SDK version is required to be 4.5.2 or more recent.

To install on Linux or Mac OS, please refer to the [Developer's guide](https://plustoolkit.github.io/developersguide).

### Configuration file<a name="configFile"></a>
The **Plus Server** relies on a configuration file, in XML format, to set the tracking parameters. These configuration files are located in `/config` for pre-built versions and in `/PlusLibData/ConfigFiles` for compiled versions. Plus Toolkit already comes with two examples of configuration file for the ASTM Phantom Test: one for Atracsys trackers (`PlusDeviceSet_Server_AstmPhantomTest_Atracsys.xml`) and one for NDI Polaris trackers (`PlusDeviceSet_Server_AstmPhantomTest_NDI_Polaris.xml`). The user is welcome to duplicate and customize these configuration files to meet their needs, but some parameters, listed below, must be correctly set in order to successfully run the ASTM Phantom Test.

* `Device > Type` describes what tracker is used and must be in accordance with the version of PLUS Toolkit installed. For more information on what type to use, please refer to the [Configuration page](http://perk-software.cs.queensu.ca/plus/doc/nightly/user/Configuration.html).

* The `Device > ToolReferenceFrame` gives a name to the reference frame of the tracking coordinates, typically the tracker.

* `DataSources` provides the inputs i.e. the description of the tracked arrays. For our ASTM Phantom Test, two are necessary:
  - the array attached to the phantom with the id `Phantom`. This id must remain unchanged.
  - the array of the pointer with the id `Pointer`. This id must remain unchanged.
  Each array can be for `ACTIVE` tracking (with emitting markers) or `PASSIVE` tracking (with reflective markers). <a name="geometryFile"></a>`GeometryFile` is set as the path (relative to the xml configuration file) of the geometry of the array (which enables the detection and tracking). For Atracsys trackers for example, the geometry is contained in an .ini file as such:
  ```ini
  [geometry]
  count=4
  id=101
  [fiducial0]
  x=-24.3012
  y=-29.5377
  z=0.14917
  [fiducial1]
  x=-66.7241
  y=14.0559
  z=-6.80029
  [fiducial2]
  x=20.8942
  y=3.55241
  z=1.4325
  [fiducial3]
  x=70.131
  y=11.9294
  z=5.21875
  [pivot]
  x=0.0000
  y=0.0000
  z=0.0000
  ```
  However, each manufacturer has its own format for such geometry files, so please refer to the tracker's manual for more information.

* The `OutputChannel` will be composed of the two streams of our `DataSources` so `Phantom` and `Pointer`

* <a name="transformsStream"></a>The Plus Server is an OpenIGTLink server, which sends messages of type `TRANSFORM`. These represent 4x4 matrices describing the transform from one item to another. For the ASTM Phantom Test, we need three transforms:
  - the transform from the pointer (`Pointer`) to the phantom (`Phantom`), which results in `PointerToPhantom`
  - the transform from the phantom (`Phantom`) to the tracker (`Tracker`), which results in `PhantomToTracker`
  - the transform from the pointer (`Pointer`) to the tracker (`Tracker`), which results in `PointerToTracker`
  <br>**DO NOT** change the names of the output transforms, as these are hardcoded in the Slicer module.
  
  The option `SendValidTransformsOnly` has to be set to `FALSE`, which helps the device detect when an item gets out of tracking (the corresponding transform attribute then goes from "VALID" to "MISSING").

* Other device-specific parameters can be set, depending on the manufacturer and/or the tracker. For example, the origin of the tracker coordinate system is supposed to be at the center of the device. For Atracsys trackers, the device parameter `SymmetriseCoordinates="1"` is then required to move the origin of the tracker from the left camera to the center.

For a better understanding of configuration files, their structure is detailed in the [Configuration page](http://perk-software.cs.queensu.ca/plus/doc/nightly/user/Configuration.html) of the User Manual.

## 3D Slicer<a name="slicerInstall"></a>
[3D Slicer](https://www.slicer.org) (or "Slicer" for short) is a free, open-source software dedicated to medical image analysis. One of strengths of Slicer is its modularity, as it is possible to develop extensions to further expand its features or use its platform to create a dedicated software. The latter is the approach chosen for this project. Our Slicer module sets up an **OpenIGTLink client**, connects to the **Plus Server** and receives and analyzes the tracking data to perform the ASTM Phantom Test.

### Installation
From Slicer's [download page](https://download.slicer.org), download, install and run the latest stable release corresponding to the computer OS. Then, click on `Install Slicer Extensions` from the welcome panel.

![Launch extensions manager](/readme_img/install1.svg)

In the Extensions Manager, head to the `Install Extensions` tab (1) and browse or look for the `AstmPhantomTest` extension (2). Once found, simply click on Install (3) and restart Slicer as required (4).

![Module install](/readme_img/install2.svg)

The ASTM Phantom Test module is now installed and a shortcut for it can be set in the main menu bar by returning to `Application Settings` > `Modules`.<a name="moduleShortcut"></a>

![Module shortcut](/readme_img/module_shortcut.svg)

# Parameter files<a name="paramFiles"></a>
The module relies on several parameter files to accomodate for the used hardware. Those parameter files may be duplicated and customized to accomodate for specific tools or requirements. The parameter files are located in the module folder, whose path (hereafter coined `module_path`) can be found via `Application Settings > Modules`.

![Module path](/readme_img/module_path.svg)

## Pointer file<a name="pointerFile"></a>
Located in `module_path\Resources\ptr`, this parameter file contains the maximum tilt angle (`MAXTILT`, in degrees) beyond which the pointer manufacturer does not guarantee tracking.
This value typically depends on the type of tracking technology and that of the fiducials/markers attached to the pointer.
<a name="ptrRotAxes"></a>The parameter file also describes the pointer rotation axes (`ROLL`, `PITCH`, `YAW`) **in the coordinate system of the pointer**. :warning: These axes need to match those set for the [working volume](#wvRotAxes) (more details in the [Troubleshooting section](#tbWrongOrientation)). 
Finally, the file contains the pointer height (`HEIGHT`, in mm) to accomodate for pointer tracking while the phantom nears the top of the working volume. This consists in placing the top target location for the phantom ([`TL`](#wvFile)) with a downward offset of `HEIGHT` + the elevation of the highest divot (e.g, #47) from the central divot ([`CTR`](#phantomFile)). If `HEIGHT` is set to 0, then there is no compensation.

## Working volume file<a name="wvFile"></a>
Located in `module_path\Resources\wv`, this parameter file contains various information:
- the coordinates of the various locations that the phantom should be placed at in the working volume. Beside the center location (`CL`), all other locations lie at the edges of the working volume, as described in the ASTM standard. The four other locations are placed on the outer boundaries of the back plane. `BL` is located at the bottom, `TL` at the top, `LL` at the left and `RL` at the right. All these coordinates are expressed in the referential of the tracker.

![Locations](/readme_img/wv_locations_light.svg#gh-light-mode-only)
![Locations](/readme_img/wv_locations_dark.svg#gh-dark-mode-only)

- the actual working volume is described by the `NODES` coordinates (again in the tracker referential frame). The working volume is assumed to be composed of a succession of quadrilateral planes, but their number can vary.

![Nodes](/readme_img/wv_nodes_light.svg#gh-light-mode-only)
![Nodes](/readme_img/wv_nodes_dark.svg#gh-dark-mode-only)

- the moving tolerance<a name="movTol"></a> is the threshold that separates actual pointer motion from the slight "wiggle" that typically occurs with most tracking technologies even when the pointer tip is static. Since the magnitude of this wiggle often depends on the distance to the tracker, the range for the moving tolerance is given by two extreme values. `MOVTOLMIN` sets the minimum threshold when the pointer is the closest possible to the tracker (e.g, 0.4mm at 920mm in depth) and `MOVTOLMAX` the maximum when the pointer is the farthest possible (e.g, 1.0mm at 2850mm in depth). The **moving tolerance is automatically set by the module** during the tests within the provided range. Nonetheless, if the user experiences trouble acquiring a divot because the program keeps detecting tip motion when there is none, the moving tolerance can be manually increased live (see [troubleshoot](#tbRemainingStatic)).

- <a name="wvRotAxes"></a>the working volume file also describes the pointer rotation axes (`ROLL`, `PITCH`, `YAW`) **in the coordinate system of the tracker**.  :warning: These axes need to match those set for the [pointer](#ptrRotAxes) (more details in the [Troubleshooting section](#tbWrongOrientation)).

- the model name of the tracker (`MODEL`) is also given in the working volume file. The name has to match one of the models included in `module_path\Resources\models`. For example, `MODEL = ftk500` will prompt the software to load the 3D model `ftk500_RAS.stl`.

## Phantom file<a name="phantomFile"></a>
Located in `module_path\Resources\gt`, this parameter file describes the divots on the phantom and their use. All the divots coordinates are listed (`POINT id`,`X`,`Y`,`Z`) and given **in the referential frame of the phantom**. This referential frame is defined by three divots which ids are given by `REF` in the following order O, X and Y.

The sequence of divots used for the multi-point test is given by `SEQ` and the id of the central divot (used for all the other tests) is given by `CTR`.

```
REF = 1 19 18
SEQ = 20 18 12 6 1 7 13 19 25 22 28 30 32 34 37 35 40 42 44 46
CTR = 20

POINT 1
X 0.00
Y 0.00
Z 0.00
POINT 2
X 0.01
Y 14.44
Z 0.00
POINT 3
X 14.45
Y 0.00
Z -0.01
...
```

# Usage<a name="usage"></a>
## Setup<a name="setup"></a>
The tracker and the phantom are set up so that:
1. the tracker is installed according to the manufacturer's specifications (typically in orientation). Then, it is connected to the computer and turned on. For more details about this connection (e.g. cabling, network configuration, drivers), please refer to the tracker manual.
2. the phantom is inially placed within the first half of the working volume facing the tracker.
3. during the measurements, both the phantom and the pointer must keep their tracked array (approximately) oriented towards the tracker so as to ensure an optimal tracking accuracy. The only exception is for the pointer during the rotation tests.
4. the operator can manipulate the pointer with respect to the phantom with ease, without occluding the device lines of sight. The operator should also be able to monitor the progress of the tests on the screen monitor. See example of setup below.
5. if possible, sound should be enabled on the computer as audio clues are given to signal progression during the tests, which sometimes alleviates the need to look at the screen (especially during the multi-point test).

![Example of setup](/readme_img/setup_example_light.svg#gh-light-mode-only)
![Example of setup](/readme_img/setup_example_dark.svg#gh-dark-mode-only)

## Launching the software<a name="launch"></a>
### Plus Server
The Plus Server is launched by running `PlusServerLauncher.exe` from the `bin` repository of PLUS Toolkit.

Once launched as illustrated below, the path to the configuration files folder (1) is automatically selected as the one included in the PLUS Toolkit repository. If the requested configuration file is located elsewhere, the user may manually select another folder and refresh it thanks to the two buttons next to the input field.

Then, the user shall select from the dropdown menu (2) the appropriate configuration file, correctly formatted as explained in the [Configuration file](#configFile) subsection. Finally, the server is launched by click on the `Launch Server` button (3) and the message `Connecting to devices.` appears.
 
![Server Launcher](/readme_img/server1.svg)

If the server has sucessfully started, it appears as shown below.

![Server Launcher Connected](/readme_img/server3.png)

### Slicer
Start Slicer by clicking a shortcut to it. If no shortcut to Slicer was created during its installation, the application may still be launched by running the `Slicer` executable from its repository.

Once Slicer is started, the ASTM Phantom Test module can be accessed via the dropdown menu in the `Tracking` category or via the shortcut in the menu bar (if [previously created](#moduleShortcut)).

![Module access](/readme_img/start_module.svg)

## Running the tests<a name="tests"></a>
### Preliminary steps
When the module starts, a dialog window pops up and the user has to select the folder where the [output files](#results) (including the log) will be saved.

On the left panel, the tracking status of the pointer and the reference array (attached to the phantom) is displayed. These labels correspond to the three [transforms streamed](#transformsStream) by the Plus Server and show up either as `OK` or `MISSING`.

![Status missing](/readme_img/status_missing.png)

The program won't start until both the pointer and the phantom reference array are being tracked (even briefly), i.e. until all transforms are displayed as `OK`.

![Status ok](/readme_img/status_ok.png)

Once the program is started, the working volume and the target locations are previewed from the top and the front of the scene. The choice in working volume may be changed while [setting the parameters](#parameterSetting) in the left panel.

![Top and front views](/readme_img/views.svg)

The first parameter the operator is expected to input is the tracker serial number (1).

![Parameter input 1](/readme_img/parameter_input1.svg)

<a name="parameterSetting"></a>Once filled in, the other parameters are unlocked and the user can choose the appropriate [pointer file](#pointerFile) (2), [phantom file](#phantomFile) (3) and [working volume file](#wvFile) (4). The user also has to choose the [point acquisition mode](#ptAcquiMode) (5) and input his id in the `Operator` field (6).

![Parameter input 2](/readme_img/parameter_input2.svg)

<a name="ptAcquiMode"></a>There are **three point acquisition modes** available:
- **1-frame**: the point coordinates are those measured in a *single frame* in the middle of the acquisition. In this mode, the acquisition length is set to 0.5 sec.
- **mean**: the point coordinates are the *mean* of those measured across *N* frames (default is 30). In this mode, the point acquisition lasts *N* frames.
- **median**: the point coordinates are the *median* of those measured across *N* frames (default is 30). In this mode, the point acquisition lasts *N* frames.

Once the operator id is filled in, the choice in locations is unlocked (7). By default, all [five locations](#wvFile) in the working volume are enabled as recommended by the standard, but the user can, at any time during the session, to disable and skip locations if necessary. <a name="enableTests"></a>Likewise, by default all five tests are enabled (8) as recommended by the standard, but the user can disable certain tests **before** the phantom hits a target location in the working volume, if necessary.

The [moving tolerance](#movTol) slidebar (9) allows the user to monitor and adjust the sensibility to pointer motion. The operator may interact with the 3D scene with the mouse and the optimal view can be automatically reset with the `Reset Camera` button (10).

![Locations & tests](/readme_img/locations_tests.svg)

The filling in of operator id also triggers the phantom calibration, which determines the geometrical relationship between the coordinate system of the phantom (and thereby its divots) and the reference array attached to it. To perform the calibration, the user only needs to successively pick three separate divots that defines the referential frame (indicated in the [phantom file](#phantomFile) by `REF`).

|<a name="acquiMech"></a>For any **point acquisition**, the targets are indicated by a red sphere and their id. Once the pointer hit the target (the correct divot), the point acquisition starts, indicated by the target becoming smaller and greener. The duration of the acquisition depends on the [point acquisition mode](#ptAcquiMode). The point acquisition is done when the target becomes large and green, and a "pop" sound is played. Removing the pointer from the divot then prompts the program to show the next target, if any. Removing the pointer before the point acquisition is done will reset the current target.|
|---|

![Calibration](/readme_img/calib.svg)

Once the calibration is over, the actual tests may start but first the phantom needs to be placed at one of the designated locations in the working volume. To help the user in this task, the interface switches back to "working volume guidance". In the top and front views, the user can now see where the phantom is located with respect to the target locations. Once the phantom is stabily placed at one of the enabled locations, a specific sound is played and the first test starts.

![Working volume guidance](/readme_img/wv_guidance.svg)

### Single Point Test
Referred to as the *Single Point Accuracy and Precision Test* in the ASTM standard, this test aims at assessing the performance of the tracking system for single point measurements. To do so, the user must repeatedly acquire the central divot for a certain number of times. The progression of the test is displayed in the top right corner.

![Single point test](/readme_img/tests_single.png)

### Rotation Tests
As described in the ASTM standard, these *Rotation Tests* aim at assessing the stability in measurement of a single point while the pointer rotates around specific axes (roll, pitch, yaw). The definition of these axes are defined in the [pointer file](#pointerFile) and in the [working volume file](#wvFile) in their respective coordinate system.

To start the test, the user must lodge the pointer in the central divot, which will toggle the display of the pointer angles with respect to each rotation axes. The current rotation axis to be measured is highlighted by the symbols > and <. The pointer must be **rotated only around that specific axis**, i.e. the other angles shall remain as close to 0 as possible during the test.

To start the actual measurements, the user must first rotate the pointer as detailed above until it is not tracked anymore. Then, performing a counter rotation, the pointer is tracked again, which will trigger the program to begin saving the measurements. The user shall continue rotating that way until they reach the opposite end of the angular range, i.e. until the tracking stops again, which will stop the measurements.

This routine is to be repeated for each axis corresponding to the [enabled rotation tests](#enableTests) in the parameter panel.

|<a name="artifOutOfTracking"></a>Certain rotations may lead to the pointer colliding with parts of the phantom or escaping the divot before it gets out of tracking. It is preferable to prematurly stop the measurements (and hence the rotation test) slightly before reaching these dead-ends. To artificially set the pointer out of tracking, swiftly occlude the pointer with the hand while remaining in the central divot.
|---|

![Rotation test](/readme_img/tests_rotation.png)

### Multi-Point Test
As explained in the ASTM standard, this test consists in picking various points on the phantom and comparing the resulting point cloud to the ground truth given by the [phantom file](#phantomFile). For a same set of acquisitions, this comparison is done in two ways: comparing point-to-point distances and actual point cloud registration. The results constitute an assessment of the accuracy of the tracking system in multi-point picking.

To perform the test, the user only needs to measure with the pointer a sequence of points, defined in the [phantom file](#phantomFile) by `SEQ`. During the test, the current target is shown in red and the acquired points become green.

![Multi-point test](/readme_img/tests_multi.png)

## Getting the results<a name="results"></a>
Once all the enabled tests for all the enabled locations are done, the program generates various files in the output folder.
- a **report in HTML** format (to be open with any internet browser), that contains all the statistical analysis of the measurements for each test.
- a **json file** containing all the parameters and the actual measurements. This is meant to perform some more analysis if desired.
- a **log file**, which contains all the events that occured during the session. The log is written in real-time, so even if the program crashes, the events are saved. The log file is common for all the sessions performed on a same day.

# Troubleshooting<a name="trouble"></a>

1. <a name="tbRemainingStatic"></a>*I'm having trouble acquiring a divot although my pointer is static (i.e. placed in a divot).*
   - Check that there is no occlusion of any of the markers.
   - Check the environment for interferences. For optical systems, use the manufacturer's tools to visually assess in the camera images the absence of reflections that could affect the detection of the markers, typically on the phantom.
   - Increase the [moving tolerance](#movTol) by increments of 10% of the total range. If the maximum tolerance is reached, you may slightly increase that maximum value in the [working volume file](#wvFile) and restart Slicer. However, increasing the moving tolerance further will hinder the reliability of the tests.

2. <a name="tbPlusServerConnection"></a>*The Plus Server Launcher does not connect to my device or gives me errors.*
   - Check that the installed version of [PLUS Toolkit](#plusDownload) is the appropriate one for my system.
   - Check that the SDK version of my system is compatible with PLUS Toolkit. In doubt, you may [contact the PLUS Toolkit development team](https://plustoolkit.github.io/contact.html).
   - Check that the device is powered on and connected to the computer as per the manufacturer's guidelines.
   - Check that the computer is well configured for the tracking system as per the manufacturer's guidelines (typically network configuration if connected through ethernet).
   - Check that the [configuration file](#configFile) has been correctly written.

3. <a name="noCommunication"></a>*The status for the phantom and/or the pointer remains MISSING despite being visible by the tracker.* => There is a problem of communication between Slicer and the Plus Server.
   - Check that the Plus Server is launched **with the appropriate configuration file** and successfully connected to the tracking system.
   - In Slicer, head to the Transforms module via the dropdown menu and check the Active Transform list at the top. If "PhantomToTracker" or "PointerToTracker" is missing, check that the [geometry files](#geometryFile) are correct and that their paths in the configuration file are valid.

4. <a name="tbOutOfTracking"></a>*I can't naturally trigger the out of tracking of the pointer during the rotation tests.*
   - See the recommendation for [artificially ending the rotation measurements](#artifOutOfTracking) prematurly.
   
5. <a name="tbWrongOrientation"></a>*The pointer is misoriented in the rendering and/or the angle values are not near 0 when "facing" the tracker.*
   - There is a mismatch between the rotation axes in the tracker's coordinate system (in the [working volume file](#wvRotAxes)) and the rotation axes in the pointer's coordinate system (in the [pointer file](#ptrRotAxes)). Those axes should be the same in the world's coordinate system. These axes are important as they allow for 1) a correct interpretation of the pointer rotations with respect to the tracker and 2) a correct orientation of the 3D pointer model in the display.

![RotationAxes](/readme_img/rotation_axes_light.svg#gh-light-mode-only)
![RotationAxes](/readme_img/rotation_axes_dark.svg#gh-dark-mode-only)

6. <a name="tbCustomSTL"></a>*I imported my own 3D models in STL format for the phantom, the pointer or tracker, and it shows in the wrong orientation in the 3D scene.*
   - Slicer uses the [RAS convention](http://www.grahamwideman.com/gw/brain/orientation/orientterms.htm) for axes, which differs from the typical X,Y,Z spatial axes. For a correct interpretation of the STL file, it must be edited (e.g, using Notepad) and its first line shall include `SPACE=RAS`. For example, the first few lines of the STL can be:
   ```
   solid SPACE=RAS
    facet normal 0 0.987688 -0.156434
     outer loop
      vertex -150 50 0
      vertex 150 50 0
	  ...
   ```