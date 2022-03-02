# ASTM Phantom Test
This software is a module for [3D Slicer](https://www.slicer.org) to perform the accuracy test of a tracking system as described in the [standard ASTM F2554](https://www.astm.org/f2554-18.html). (:warning: The procedures described hereafter slightly differ from those of the current version of the standard because they are based on a future revision).

This test relies on a calibration object, hereafter referred to as the "phantom", of known dimensions. Performing measurements on such a phantom provides a reliable assessment of the tracking system accuracy and precision.

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
- [ ] A **phantom** with an array of divots and a reference tracked array rigidly attached. See the [standard](https://www.astm.org/f2554-18.html) for requirements and recommendations for its design and manufacturing.
- [ ] The tested **tracking system**, typically including
  - [ ] A **pointer** composed of a tracked array and a shaft with a pointy end fitting the divots.
  - [ ] A **tracker** which spatially locates the various arrays aforementionned. Various technologies can be utilized (optical, magnetic, etc).
  - [ ] A **computer** to receive and analyze the tracking data. The present software is to be installed on this computer, alongside the various supporting tools and libraries. Since this software also provides visual guidance to perform the test, a computer monitor is recommended.

# Required software<a name="requiredSoft"></a>
## PLUS Toolkit<a name="plusInstall"></a>
[PLUS Toolkit](https://plustoolkit.github.io/) is a free, open-source set of software tools for Computer-Assisted Surgery, which includes a wrapper for SDK's from many manufacturers of tracking systems. This enables a standardization of the tracking data streaming from the tracker to the computer, thanks to an [OpenIGTLink](http://openigtlink.org) server (the **Plus Server**).

### Installation<a name="plusDownload"></a>
Pre-built installers more than twenty systems are available for Windows from the [Download page](https://plustoolkit.github.io/download.html). To know which installer to choose, the user may refer to the table at the bottom of that page. Until a new stable release is available, it is important to download from the **Latest Development Snapshot**, as it includes new features necessary for the tests.

:warning: PLUS Toolkit offers a wrapper to a system SDK, but **does not include the actual SDK**, which needs to be installed separately on the computer. Moreover, there may be a version requirement (e.g, the Atracsys SDK has to be 4.5.2 or more recent).

To install on Linux or Mac OS, please refer to the [Developer's guide](https://plustoolkit.github.io/developersguide).

### Configuration file<a name="configFile"></a>
The **Plus Server** relies on a configuration file, in XML format, to set the tracking parameters. There are several configuration files already included with PLUS Toolkit (in `/config` for installed versions, in `/PlusLibData/ConfigFiles` for built versions). The structure of a configuration file is also detailed in the [Configuration page](http://perk-software.cs.queensu.ca/plus/doc/nightly/user/Configuration.html) in the User Manual.

The ASTM Phantom Test requires certain server parameters to be set, as described in the configuration file example below.

```xml
<PlusConfiguration version="2.7">
 <DataCollection StartupDelaySec="1.0">
  <DeviceSet
   Name="PlusServer: ASTM Phantom Test"
   Description="Broadcasting through OpenIGTLink the tracking data from a pointer with respect to a phantom."/>
  <Device
   Id="TrackerDevice"
   Type="CompanyTracker"
   MaxMissingFiducials="0"
   MaxMeanRegistrationErrorMm="1.0"
   ToolReferenceFrame="Tracker" >
   <DataSources>
    <DataSource Type="Tool" Id="Phantom" TrackingType="PASSIVE" GeometryFile="geometries/geomPhant.ini" />
    <DataSource Type="Tool" Id="Pointer" TrackingType="PASSIVE" GeometryFile="geometries/array02.ini" />
   </DataSources>
   <OutputChannels>
    <OutputChannel Id="TrackerStream">
     <DataSource Type="Tool" Id="Phantom" />
     <DataSource Type="Tool" Id="Pointer" />
    </OutputChannel>
   </OutputChannels>
  </Device>
 </DataCollection>

 <PlusOpenIGTLinkServer
  MaxNumberOfIgtlMessagesToSend="1"
  MaxTimeSpentWithProcessingMs="50"
  ListeningPort="18944"
  SendValidTransformsOnly="FALSE"
  OutputChannelId="TrackerStream" >
  <DefaultClientInfo>
   <MessageTypes>
    <Message Type="TRANSFORM" />
   </MessageTypes>
   <TransformNames>
    <Transform Name="PointerToPhantom" />
    <Transform Name="PhantomToTracker" />
    <Transform Name="PointerToTracker" />
   </TransformNames>
  </DefaultClientInfo>
 </PlusOpenIGTLinkServer>  
</PlusConfiguration>
```

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

* The Plus Server is an OpenIGTLink server, which sends messages of type `TRANSFORM`. These represent 4x4 matrices describing the transform from one item to another. For the ASTM Phantom Test, we need three transforms:
  - the transform from the pointer (`Pointer`) to the phantom (`Phantom`), which results in `PointerToPhantom`
  - the transform from the phantom (`Phantom`) to the tracker (`Tracker`), which results in `PhantomToTracker`
  - the transform from the pointer (`Pointer`) to the tracker (`Tracker`), which results in `PointerToTracker`
  <br>**DO NOT** change the names of the output transforms, as these are hardcoded in the Slicer module.
  
  The option `SendValidTransformsOnly` has to be set to `FALSE`.

* Other device-specific parameters can be set, depending on the manufacturer and/or the tracker. For example, for Atracsys trackers, the device parameter `SymmetriseCoordinates="1"` also needs to be set.

## 3D Slicer<a name="slicerInstall"></a>
[3D Slicer](https://www.slicer.org) (or "Slicer" for short) is a free, open-source software dedicated to medical image analysis. One of strengths of Slicer is its modularity, as it is possible to develop extensions to further expand its features or use its platform to create a dedicated software. The latter is the approach chosen for this project. Our Slicer module sets up an **OpenIGTLink client**, connects to the **Plus Server** and receives and analyzes the tracking data to perform the ASTM Phantom Test.

### Installation
From Slicer's [download page](https://download.slicer.org), choose the **Preview Release** corresponding to the computer OS. Do not download the Stable Release, as it does yet not include all necessary features.
Moreover, since our module requires Slicer to run an OpenIGTLink client, the extension **SlicerOpenIGTLink** also needs to be installed. To do so, start Slicer and head to the Extensions Manager and install the extension as shown below.

![Extension Manager Button](/readme_img/ext_manager_button.svg)

![Extension Manager](/readme_img/extension_manager.svg)

### Adding the module
Now that Slicer is all set up, the ASTM Phantom Test module can be added. First, clone or download the present repository to have the `AstmPhantomTest` folder locally on the computer. Then, head to the `Applications Settings` via the menu.

![Application Settings](/readme_img/application_settings.svg)

In `Modules`, select the `AstmPhantomTest` folder to be added as an `Additional Module Path`. This will require a restart of Slicer to take effect.

![Module import](/readme_img/module_import.svg)

The ASTM Phantom Test module is now installed and a shortcut for it can be set in the main menu bar by returning to `Application Settings` > `Modules`.<a name="moduleShortcut"></a>

![Module shortcut](/readme_img/module_shortcut.svg)

# Parameter files<a name="paramFiles"></a>
The module relies on several parameter files to accomodate for the hardware used.

## Pointer file<a name="pointerFile"></a>
Located in `AstmPhantomTest\Resources\ptr`, this parameter file contains the maximum tilt angle (`MAXTILT`) beyond which the pointer manufacturer does not guarantee tracking.
This value typically depends on the type of tracking technology and that of the fiducials/markers attached to the pointer.
The parameter file also describes the pointer rotation axes (`ROLL`, `PITCH`, `YAW`) **in the coordinate system of the pointer**. This information allows a correct interpretation of the pointer rotations with respect to the tracker.

## Working volume file<a name="wvFile"></a>
Located in `AstmPhantomTest\Resources\wv`, this parameter file contains various information:
- the coordinates of the locations that the phantom should be placed at in the working volume. Beside the center location (`PC`), all other locations lie at the edges of the working volume, as described in the ASTM standard.
`PBT` is located at the very bottom from the center, `PL` the very left, `PR` the very right and `PBK` the very back. All these coordinates are expressed in the referential of the tracker.

![Locations](/readme_img/wv_locations_light.svg#gh-light-mode-only)
![Locations](/readme_img/wv_locations_dark.svg#gh-dark-mode-only)

- the actual working volume is described by the `NODES` coordinates (again in the tracker referential frame). The working volume is assumed to be composed of a succession of quadrilateral planes, but their number can vary.

![Nodes](/readme_img/wv_nodes_light.svg#gh-light-mode-only)
![Nodes](/readme_img/wv_nodes_dark.svg#gh-dark-mode-only)

- the moving tolerance<a name="movTol"></a> is the threshold that separates actual pointer motion from the slight "wiggle" that typically occurs with most tracking technologies even when the pointer tip is static. Since the magnitude of this wiggle often depends on the distance to the tracker, the range for the moving tolerance is given by two extreme values. `MOVTOLMIN` sets the minimum threshold when the pointer is the closest possible to the tracker (e.g, 0.4mm at 920mm in depth) and `MOVTOLMAX` the maximum when the pointer is the farthest possible (e.g, 1.0mm at 2850mm in depth). The **moving tolerance is automatically set by the module** during the tests within the provided range. Nonetheless, if the user experiences trouble acquiring a divot because the program keeps detecting tip motion when there is none, the moving tolerance can be manually increased live (see [troubleshoot](#tbRemainingStatic)).

- the working volume file also describes the pointer rotation axes (`ROLL`, `PITCH`, `YAW`) **in the coordinate system of the tracker**. This information allows a correct interpretation of the pointer rotations with respect to the tracker.

## Phantom file<a name="phantomFile"></a>
Located in `AstmPhantomTest\Resources\gt`, this parameter file describes the divots on the phantom and their use. All the divots coordinates are listed (`POINT id`,`X`,`Y`,`Z`) and given in the referential frame of the phantom. This referential frame is defined by three divots which ids are given by `REF` in the following order O, X and Y.

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

Then, if the setup is correct, a 3D view of the phantom should appear as below, with **no visible pointer**.

![Good start view](/readme_img/start_ok.svg)

If the phantom model appears from another angle with a **yellow visible pointer**, then there is a problem of communication between Slicer and the Plus Server (see [Throubleshooting](#noCommunication)).

![Wrong start views](/readme_img/start_wrong.svg)

On the left, there is a parameter panel that requires user input. First, the tracker serial number is prompted (1).

![Parameter input 1](/readme_img/parameter_input1.svg)

Once filled in, the other parameters are unlocked and the user can choose the appropriate [pointer file](#pointerFile) (2), [working volume file](#wvFile) (3) and [phantom file](#phantomFile) (4). The user also has to choose the [point acquisition mode](#ptAcquiMode) (5) and input his id in the `Operator` field (6).

![Parameter input 2](/readme_img/parameter_input2.svg)

<a name="ptAcquiMode"></a>There are **three point acquisition modes** available:
- **1-frame**: the point coordinates are those measured in a *single frame* in the middle of the acquisition. In this mode, the acquisition length is set to 0.5 sec.
- **mean**: the point coordinates are the *mean* of those measured across *N* frames (default is 30). In this mode, the point acquisition lasts *N* frames.
- **median**: the point coordinates are the *median* of those measured across *N* frames (default is 30). In this mode, the point acquisition lasts *N* frames.

Once the operator id is filled in, the choice in locations is unlocked (7). By default, all [five locations](#wvFile) in the working volume are enabled as recommended by the standard, but the user can, at any time during the session, to disable and skip locations if necessary. <a name="enableTests"></a>Likewise, by default all five tests are enabled (8) as recommended by the standard, but the user can disable certain tests **before** the phantom hits a target location in the working volume, if necessary.

The [moving tolerance](#movTol) slidebar (9) allows the user to monitor and adjust the sensibility to pointer motion. The `Reset Camera` button (10) resets the view of the phantom to an optimum at any time, if the user happened to have moved the scene around with the mouse.

![Locations & tests](/readme_img/locations_tests.svg)

The filling in of operator id also triggers the phantom calibration, which determines the geometrical relationship between the referential frame of the phantom (and thereby its divots) and the reference array attached to it. To perform the calibration, the user only needs to successively pick three separate divots that defines the referential frame (indicated in the [phantom file](#phantomFile) by `REF`).

|<a name="acquiMech"></a>For any **point acquisition**, the targets are indicated by a red sphere and their id. Once the pointer hit the target (the correct divot), the point acquisition starts, indicated by the target becoming smaller and greener. The duration of the acquisition depends on the [point acquisition mode](#ptAcquiMode). The point acquisition is done when the target becomes large and green, and a "pop" sound is played. Removing the pointer from the divot then prompts the program to show the next target, if any. Removing the pointer before the point acquisition is done will reset the current target.|
|---|

![Calibration](/readme_img/calib.svg)

Once the calibration is over, the actual tests may start but first the phantom needs to be placed at one of the designated locations in the working volume. To help the user in this task, the interface switches to "working volume guidance" by showing a top view of the working volume on the left and a front view on the right. In these views, the user can see where the phantom is located with respect to the target locations, indicated by red spheres. Once the phantom is stabily placed at one of the enabled locations, a particular sound is played and the first test starts.

![Working volume guidance](/readme_img/wv_guidance.svg)

### Single Point Test
Referred to as the *Single Point Accuracy and Precision Test* in the ASTM standard, this test aims at assessing the performance of the tracking system for a single point measurements. To do so, the user must repeatedly acquire the central divot for a certain number of times. The progression of the test is displayed in the top right corner.

![Single point test](/readme_img/tests_single.png)

### Rotation Tests
As described in the ASTM standard, these *Rotation Tests* aim at assessing the stability in measurement of a single point while the pointer rotates around specific axes (roll, pitch, yaw). The definition of these axes are defined in the [pointer file](#pointerFile) and in the [working volume file](#wvFile) in their respective referential frames.

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

3. <a name="noCommunication"></a>*I don't have the phantom well-oriented at the beginning and I see the yellow pointer.* => There is a problem of communication between Slicer and the Plus Server.
   - Check that the Plus Server is launched **with the appropriate configuration file** and successfully connected to the tracking system.
   - In Slicer, head to the Transforms module via the dropdown menu and check the Active Transform list at the top. If "PhantomToTracker" or "PointerToTracker" is missing, check that the [geometry files](#geometryFile) are correct and that their paths in the configuration file are valid.

4. <a name="tbOutOfTracking"></a>*I can't naturally trigger the out of tracking of the pointer during the rotation tests.*
   - See the recommendation for [artificially ending the rotation measurements](#artifOutOfTracking) prematurly.
