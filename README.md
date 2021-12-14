# ASTM Phantom Test
This software is a module for [3D Slicer](https://www.slicer.org) to perform the accuracy test of a tracking system as described in the [standard ASTM F2554](https://www.astm.org/f2554-18.html).

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
   - [Performing the tests](#tests)
   - [Getting the results](#results)

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

### Installation
Pre-built installers more than twenty systems are available for Windows from the [Download page](https://plustoolkit.github.io/download.html). To know which installer to choose, you may refer to the table at the bottom of that page. Until a new stable release is available, it is important to download from the **Latest Development Snapshot**, as it includes new features necessary for the tests.

:warning: PLUS Toolkit offers a wrapper to a system SDK, but **does not include the actual SDK**, which needs to be installed separately on the computer. Moreover, there may be a version requirement (e.g, the Atracsys SDK has to be 4.5.2 or more recent).

To install on Linux or Mac OS, please refer to the [Developer's guide](https://plustoolkit.github.io/developersguide).

### Configuration file
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
  Each array can be for `ACTIVE` tracking (with emitting markers) or `PASSIVE` tracking (with reflective markers). `GeometryFile` is set as the path (relative to the xml configuration file) of the geometry of the array (which enables the detection and tracking). For Atracsys trackers for example, the geometry is contained in an .ini file as such:
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
From Slicer's [download page](https://download.slicer.org), choose the **Preview Release** corresponding to your OS. Do not download the Stable Release, as it does yet not include all necessary features.
Moreover, since our module requires Slicer to run an OpenIGTLink client, the extension **SlicerOpenIGTLink** also needs to be installed. To do so, start Slicer and head to the Extensions Manager and install the extension as shown below.

![Extension Manager Button](/readme_img/ext_manager_button.svg)

![Extension Manager](/readme_img/extension_manager.svg)

### Adding the module
Now that Slicer is all set up, the ASTM Phantom Test module can be added. First, clone or download the present repository to have the `AstmPhantomTest` folder locally on the computer. Then, head to the `Applications Settings` via the menu.

![Application Settings](/readme_img/application_settings.svg)

In `Modules`, select the `AstmPhantomTest` folder to be added as an `Additional Module Path`. This will require a restart of Slicer to take effect.

![Module import](/readme_img/module_import.svg)

The ASTM Phantom Test module is now installed, it can be accessed via the dropdown menu in the `Tracking` category.

![Module access](/readme_img/module_access.svg)

Or a shortcut can be set for it in the main menu bar.

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

- the moving tolerance is the threshold that separates actual pointer motion from the slight "wiggle" that typically occurs with most tracking technologies even when the pointer tip is static. Since the magnitude of this wiggle often depends on the distance to the tracker, the range for the moving tolerance is given by two extreme values. `MOVTOLMIN` sets the minimum threshold when the pointer is the closest possible to the tracker (e.g, 0.4mm at 920mm in depth) and `MOVTOLMAX` the maximum when the pointer is the farthest possible (e.g, 1.0mm at 2850mm in depth). The **moving tolerance is automatically set by the module** during the tests within the provided range. Nonetheless, if the user experiences trouble acquiring a divot because the program keeps detecting tip motion when there is none, the moving tolerance can be manually increased live.

- the working volume file also describes the pointer rotation axes (`ROLL`, `PITCH`, `YAW`) **in the coordinate system of the tracker**. This information allows a correct interpretation of the pointer rotations with respect to the tracker.

## Phantom file<a name="phantomFile"></a>

# Usage<a name="usage"></a>
## General guidelines
For a better reliability of the tests results, these guidelines must be followed:
1. the phantom cannot be so close to the working volume borders that the pointer can get out of the device field of view while performing the tests.
2. unless stated otherwise, the pointer shall be oriented so as to ensure an optimal tracking accuracy. For example, on an optical tracker, the arrays should face the cameras as much as possible.

## Setup<a name="setup"></a>
The tracker and the phantom are set up so that:
1. the tracker is installed according to the manufacturer's specifications (typically in orientation).
2. the phantom is placed within the working volume of the tracker (near its center at first).
3. the operator can manipulate the pointer with respect to the phantom with ease, without occluding the device lines of sight. The operator should also be able to monitor the progress of the tests on the screen monitor. See example of setup below.

![Example of setup](/readme_img/setup_example_light.svg#gh-light-mode-only)
![Example of setup](/readme_img/setup_example_dark.svg#gh-dark-mode-only)

## Launching the software<a name="launch"></a>
Performing the ASTM Phantom Test first starts with connecting the tracker to the computer on which the software is installed. For more details about this connection (e.g. cabling, network configuration, drivers), please refer to the tracker manual.
 Then, the Plus Server is launched by running `PlusServerLauncher.exe` from the `bin` repository of PLUS Toolkit.


## Performing the tests<a name="tests"></a>

## Getting the results<a name="results"></a>
- md report
- json
- log file
