import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import numpy as np
import re
import ast
import json
from datetime import datetime
import uuid, hashlib

from AstmPhantomTestClasses import *

#
# AstmPhantomTest
#

class AstmPhantomTest(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "ASTM Phantom Test"
    self.parent.categories = ["Tracking"]
    self.parent.dependencies = ["OpenIGTLinkIF"]
    self.parent.contributors = ["Sylvain Bernhardt (Atracsys LLC)"]
    self.parent.helpText = """
This module is a tool to perform the tracking accuracy tests as described in the ASTM standard F2554-22.
It provides visual guidance, navigation and all the statistical analysis.
For more information about the module and its usage, please refer to the <a href="https://github.com/Atracsys/astm-phantom-test">home page</a>.
"""
    self.parent.acknowledgementText = """
This module has been developed by Sylvain Bernhardt, Atracsys LLC. It is based on a scripted module
template originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
Thanks a lot to Andras Lasso and his team for his help during the development of this project.
"""

#
# AstmPhantomTestWidget
#

class AstmPhantomTestWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self.waitingForAllNodes = True
    self.ptrNode = None
    self.refNode = None
    self.ptrRefNode = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    slicer.util.mainWindow().setMaximumHeight(1080)
    slicer.util.mainWindow().setMaximumWidth(1920)
    slicer.util.mainWindow().showMaximized()

    # Custom layout
    customLayout = """
    <layout type="horizontal" split="true">
      <item>
      <view class="vtkMRMLViewNode" singletontag="Main">
        <property name="viewlabel" action="default">M</property>
      </view>
      </item>
      <item>
      <view class="vtkMRMLViewNode" singletontag="TopWV">
        <property name="viewlabel" action="default">T</property>
      </view>
      </item>
      <item>
      <view class="vtkMRMLViewNode" singletontag="FrontWV">
        <property name="viewlabel" action="default">S</property>
      </view>
      </item>
    </layout>
    """

    # Built-in layout IDs are all below 100, so custom layout ID must be larger.
    customLayoutId=401
    layoutManager = slicer.app.layoutManager()
    layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(customLayoutId, customLayout)
    layoutManager.setLayout(customLayoutId)

    # Hide box and axis labels
    viewNodes = slicer.util.getNodesByClass("vtkMRMLViewNode")
    for viewNode in viewNodes:
      viewNode.SetAxisLabelsVisible(False)
      viewNode.SetBoxVisible(False)

    # Load widget from .ui file (created by Qt Designer).
    # Additional widgets can be instantiated manually and added to self.layout.
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/AstmPhantomTest.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    self.saveDialog = qt.QFileDialog()
    self.saveDialog.setFileMode(qt.QFileDialog().DirectoryOnly)

    if self.saveDialog.exec():
      # Path where the ouput files (including the log) will be saved
      savePath = self.saveDialog.selectedFiles()[0]
      # The log file doesn't overwrite itself and is named after the date,
      # so any use of this module on a same day will be logged in the same file
      fh = logging.FileHandler(savePath + "/AstmPhantomTest_log_" + datetime.now().strftime("%Y.%m.%d") + ".log")
      fh.setLevel(logging.INFO)
      logging.getLogger().addHandler(fh)
      logging.info(f"Save path set to {savePath}")

      # Create logic class. Logic implements all computations that should be possible to run
      # in batch mode, without a graphical user interface.
      self.logic = AstmPhantomTestLogic(self.resourcePath('models/phantom_RAS.stl'),
        self.resourcePath('models/pointer_RAS.stl'), self.resourcePath('models/simpPhantom_RAS.stl'),
        self.resourcePath(''), savePath)

      # Forward some rendering handles to the logic class
      self.logic.mainWidget = slicer.app.layoutManager().threeDWidget('ViewMain')
      self.logic.mainWidget.show()
      self.logic.mainRenderer = self.logic.mainWidget.threeDView().renderWindow().GetRenderers().GetItemAsObject(0)
      self.logic.mainRenderer.ResetCamera()

      self.logic.topWVWidget = slicer.app.layoutManager().threeDWidget('ViewTopWV')
      self.logic.topWVWidget.hide()
      self.logic.topWVRenderer = self.logic.topWVWidget.threeDView().renderWindow().GetRenderers().GetItemAsObject(0)

      self.logic.frontWVWidget = slicer.app.layoutManager().threeDWidget('ViewFrontWV')
      self.logic.frontWVWidget.hide()
      self.logic.frontWVRenderer = self.logic.frontWVWidget.threeDView().renderWindow().GetRenderers().GetItemAsObject(0)

      self.logic.initialize()

      # Adding models to the various displays
      # Display of the full phantom and pointer to the main scene
      self.logic.phantom.model.GetDisplayNode().AddViewNodeID('vtkMRMLViewNodeMain')
      self.logic.pointer.model.GetDisplayNode().AddViewNodeID('vtkMRMLViewNodeMain')
      # Display of the simplified phantom to the working volume guidance scenes
      self.logic.workingVolume.simpPhantomModel.GetDisplayNode().VisibilityOff()
      self.logic.workingVolume.simpPhantomModel.GetDisplayNode().AddViewNodeID('vtkMRMLViewNodeTopWV')
      self.logic.workingVolume.simpPhantomModel.GetDisplayNode().AddViewNodeID('vtkMRMLViewNodeFrontWV')
      # Forward models folder path
      self.logic.workingVolume.modelsFolderPath = self.resourcePath('models/')

      ## Connections

      # These connections ensure that we update parameter node when scene is closed
      self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
      self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

      # UI connections
      self.ui.trackerLineEdit.connect('editingFinished()', self.onTrackerIdChanged)
      self.ui.pointAcqui1frameButton.connect('clicked()', self.onPointAcqui1frameSet)
      self.ui.pointAcquiMeanButton.connect('clicked()', self.onPointAcquiMeanSet)
      self.ui.pointAcquiMedianButton.connect('clicked()', self.onPointAcquiMedianSet)
      self.ui.pointAcquiNumFramesLineEdit.connect('editingFinished()', self.onPointAcquiNumFramesChanged)
      self.ui.operatorLineEdit.connect('editingFinished()', self.onOperatorIdChanged)
      self.ui.movingTolSlider.connect('sliderMoved(int)', self.onMovingTolSliderMoved)
      self.ui.movingTolSlider.connect('sliderReleased()', self.onMovingTolSliderReleased)

      self.ui.testCheckBox1.connect('stateChanged(int)', self.onTestCheckBox1Changed)
      self.ui.testCheckBox2.connect('stateChanged(int)', self.onTestCheckBox2Changed)
      self.ui.testCheckBox3.connect('stateChanged(int)', self.onTestCheckBox3Changed)
      self.ui.testCheckBox4.connect('stateChanged(int)', self.onTestCheckBox4Changed)
      self.ui.testCheckBox5.connect('stateChanged(int)', self.onTestCheckBox5Changed)
      self.ui.locCheckBoxCL.connect('stateChanged(int)', self.onLocCheckBoxCLChanged)
      self.ui.locCheckBoxBL.connect('stateChanged(int)', self.onLocCheckBoxBLChanged)
      self.ui.locCheckBoxTL.connect('stateChanged(int)', self.onLocCheckBoxTLChanged)
      self.ui.locCheckBoxLL.connect('stateChanged(int)', self.onLocCheckBoxLLChanged)
      self.ui.locCheckBoxRL.connect('stateChanged(int)', self.onLocCheckBoxRLChanged)
      self.ui.resCamButton.connect('clicked()', self.logic.resetCam)

      self.ui.hackCalibButton.connect('clicked()', self.hackCalib)
      self.ui.hackCLButton.connect('clicked()', self.hackCL)
      self.ui.hackBLButton.connect('clicked()', self.hackBL)
      self.ui.hackTLButton.connect('clicked()', self.hackTL)
      self.ui.hackLLButton.connect('clicked()', self.hackLL)
      self.ui.hackRLButton.connect('clicked()', self.hackRL)
      self.ui.hackXButton.connect('clicked()', self.logic.stopSinglePtTest)

      self.intval = qt.QIntValidator(1,999) # input validator for point acqui line edit
      self.ui.pointAcquiNumFramesLineEdit.setValidator(self.intval)

      # Add observers for custom events
      self.logic.pointer.AddObserver(self.logic.pointer.movingTolChanged,
        self.onMovingTolChangedFromLocation)
      self.logic.phantom.AddObserver(self.logic.phantom.calibStartedEvent,
        self.onCalibratingPhantom)
      self.logic.phantom.AddObserver(self.logic.phantom.calibratedEvent,
        self.onPhantomCalibrated)
      self.logic.wvTargetsTop.AddObserver(self.logic.wvTargetsTop.targetHitEvent, self.onLocHit)
      self.logic.AddObserver(self.logic.sessionEndedEvent, self.onSessionEnded)
      self.logic.AddObserver(self.logic.testNamesUpdated, self.onTestNamesUpdated)

      # Initialize default values for UI elements
      self.ui.movingTolValue.setText(f'{self.logic.pointer.movingTol:.2f} mm')
      self.onMovingTolChangedFromLocation(self.logic.pointer) # update slider with pointer moving tol default value
      self.ui.hackCollapsibleButton.setText("\u26d4 dev shortcuts \u26d4")
      self.ui.hackXButton.setText("\u26a1")

      # Parse resource folder for pointer files (ptr/____.txt)
      ptrFiles = [f for f in os.listdir(self.resourcePath('./ptr')) if re.match(r'.*\.txt', f)]
      self.ui.pointerFileSelector.addItems(ptrFiles)
      self.ui.pointerFileSelector.currentIndexChanged.connect(self.onPointerFileChanged)
      # call as the first item is automatically selected
      self.onPointerFileChanged()

      # Parse resource folder for ground truth files (gt/SN____.txt)
      gtFiles = [f for f in os.listdir(self.resourcePath('./gt')) if re.match(r'SN[0-9]+.*\.txt', f)]
      self.ui.groundTruthFileSelector.addItems(gtFiles)
      self.ui.groundTruthFileSelector.currentIndexChanged.connect(self.onGroundTruthFileChanged)
      # call as the first item is automatically selected
      self.onGroundTruthFileChanged()

      # Parse resource folder for working volume files (wv/____.txt)
      wvFiles = [f for f in os.listdir(self.resourcePath('./wv')) if re.match(r'.*\.txt', f)]
      self.ui.workingVolumeFileSelector.addItems(wvFiles)
      self.ui.workingVolumeFileSelector.currentIndexChanged.connect(self.onWorkingVolumeFileChanged)
      # call as the first item is automatically selected
      self.onWorkingVolumeFileChanged()

      # Adding the observer watching out for the new transform node after openigtlink connection
      slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, self.onNodeAdded)

      # Adding welcome message
      self.welcomeText = vtk.vtkCornerAnnotation()
      self.welcomeText.GetTextProperty().SetFontSize(200)
      self.welcomeText.SetText(2, "Welcome to the ASTM Phantom Test module.\nTo start, make sure that both the pointer and\nthe reference array attached to the phantom\nare visible by the tracker.\n<--")
      self.logic.mainRenderer.AddActor(self.welcomeText)

      # Test if OpenIGTLink connection already open
      testNode = slicer.mrmlScene.GetFirstNodeByName('PointerConnector')
      if testNode != None: # if so, remove it
        slicer.mrmlScene.RemoveNode(testNode)
      # Create OpenIGTLink connection
      logging.info('Creating PointerConnector')
      self.cnode = slicer.vtkMRMLIGTLConnectorNode()
      self.cnode.SetName('PointerConnector')
      slicer.mrmlScene.AddNode(self.cnode)
      if self.cnode.Start() != 1:
        msg = "PointerConnector: Cannot connect to openIGTLink"
        logging.error(msg)
        slicer.util.errorDisplay(msg)

  def onPointerFileChanged(self):
    """
    Called when another pointer file is selected
    """
    logging.info('Pointer file changed')
    if not self.logic.readPointerFile(self.resourcePath(
      'ptr/' + self.ui.pointerFileSelector.currentText)):
      msg = "Pointer: Cannot read file"
      logging.error(msg)
      slicer.util.errorDisplay(msg)

  def onWorkingVolumeFileChanged(self):
    """
    Called when another working volume file is selected
    """
    logging.info('Working volume file changed')
    if not self.logic.readWorkingVolumeFile(self.resourcePath(
      'wv/' + self.ui.workingVolumeFileSelector.currentText)):
      msg = "Working volume: Error while reading file"
      logging.error(msg)
      slicer.util.errorDisplay(msg)
    else:
      self.ui.locCheckBoxCL.checked = "CL" in self.logic.workingVolume.locs
      self.ui.locCheckBoxBL.checked = "BL" in self.logic.workingVolume.locs
      self.ui.locCheckBoxTL.checked = "TL" in self.logic.workingVolume.locs
      self.ui.locCheckBoxLL.checked = "LL" in self.logic.workingVolume.locs
      self.ui.locCheckBoxRL.checked = "RL" in self.logic.workingVolume.locs
      # reset camera for renderers
      ResetCameraScreenSpace(self.logic.topWVRenderer)
      ResetCameraScreenSpace(self.logic.frontWVRenderer)
      # update moving tolerance slider
      self.onMovingTolSliderMoved()
      self.onMovingTolSliderReleased()

  def onGroundTruthFileChanged(self):
    """
    Called when another ground truth file is selected
    """
    logging.info('Groundtruth file changed')
    if not self.logic.readGroundTruthFile(self.resourcePath(
      'gt/' + self.ui.groundTruthFileSelector.currentText)):
      msg = "Ground truth: Cannot read file"
      logging.error(msg)
      slicer.util.errorDisplay(msg)

  def __movingTolSliderToValue(self):
    vmin = self.logic.workingVolume.movingTolMin["tol"]
    vmax = self.logic.workingVolume.movingTolMax["tol"]
    val = vmin + (vmax-vmin) * self.ui.movingTolSlider.value / self.ui.movingTolSlider.maximum
    return val

  def onMovingTolSliderMoved(self):
    """
    Called when the moving tolerance slider is moved
    """
    val = self.__movingTolSliderToValue()
    self.ui.movingTolValue.setText(f'{val:.2f} mm')

  def onMovingTolSliderReleased(self):
    """
    Called when the moving tolerance slider is released
    """
    val = self.__movingTolSliderToValue()
    logging.info(f'Pointer moving tolerance manually changed to {val:.2f} mm')
    self.logic.pointer.movingTol = val

  @vtk.calldata_type(vtk.VTK_STRING)
  def onCalibratingPhantom(self, caller, event = None, calldata = None):
    """
    Called when the phantom calibration is started
    """
    self.ui.trackerLineEdit.enabled = False
    self.ui.pointerFileSelector.enabled = False
    self.ui.workingVolumeFileSelector.enabled = False
    self.ui.groundTruthFileSelector.enabled = False
    self.ui.pointAcqui1frameButton.enabled = False
    self.ui.pointAcquiMeanButton.enabled = False
    self.ui.pointAcquiMedianButton.enabled = False
    self.ui.pointAcquiNumFramesLineEdit.enabled = False
    self.ui.pointAcquiFramesLabel.enabled = False

  @vtk.calldata_type(vtk.VTK_STRING)
  def onPhantomCalibrated(self, caller, event = None, calldata = None):
    """
    Called when the phantom is calibrated
    """
    self.ui.hackCalibButton.enabled = False
    self.ui.operatorLineEdit.enabled = False
    self.onMovingTolChangedFromLocation(self.logic.phantom)

  @vtk.calldata_type(vtk.VTK_STRING)
  def onMovingTolChangedFromLocation(self, caller, event = None, calldata = None):
    """
    Called when the moving tolerance is automatically changed by moving the phantom
    in the working volume
    """
    logging.info(f'Pointer moving tolerance automatically changed to {self.logic.pointer.movingTol:.2f} mm')
    # update slider in UI
    self.ui.movingTolValue.setText(f'{self.logic.pointer.movingTol:.2f} mm')
    vmin = self.logic.workingVolume.movingTolMin["tol"]
    vmax = self.logic.workingVolume.movingTolMax["tol"]
    self.ui.movingTolSlider.setValue((self.logic.pointer.movingTol-vmin)/(vmax-vmin) * self.ui.movingTolSlider.maximum)

  @vtk.calldata_type(vtk.VTK_STRING)
  def onLocHit(self, caller, event, calldata):
    cd = ast.literal_eval(calldata)
    loc = cd[0]
    if loc in self.logic.workingVolume.locs: # check but should always be true
      if loc == "CL":
        self.ui.locCheckBoxCL.enabled = False
        self.ui.hackCLButton.enabled = False
      if loc == "BL":
        self.ui.locCheckBoxBL.enabled = False
        self.ui.hackBLButton.enabled = False
      if loc == "TL":
        self.ui.locCheckBoxTL.enabled = False
        self.ui.hackTLButton.enabled = False
      if loc == "LL":
        self.ui.locCheckBoxLL.enabled = False
        self.ui.hackLLButton.enabled = False
      if loc == "RL":
        self.ui.locCheckBoxRL.enabled = False
        self.ui.hackRLButton.enabled = False

  @vtk.calldata_type(vtk.VTK_STRING)
  def onSessionEnded(self, caller, event = None, calldata = None):
    self.ui.locCheckBoxCL.enabled = False
    self.ui.locCheckBoxBL.enabled = False
    self.ui.locCheckBoxTL.enabled = False
    self.ui.locCheckBoxLL.enabled = False
    self.ui.locCheckBoxRL.enabled = False
    self.ui.hackCalibButton.enabled = False
    self.ui.hackCLButton.enabled = False
    self.ui.hackBLButton.enabled = False
    self.ui.hackTLButton.enabled = False
    self.ui.hackLLButton.enabled = False
    self.ui.hackRLButton.enabled = False

  @vtk.calldata_type(vtk.VTK_STRING)
  def onTestNamesUpdated(self, caller, event, calldata):
    names = ast.literal_eval(calldata)
    self.ui.testCheckBox1.text = names[0]
    self.ui.testCheckBox2.text = names[1]
    self.ui.testCheckBox3.text = names[2]
    self.ui.testCheckBox4.text = names[3]
    self.ui.testCheckBox5.text = names[4]

  def onTestCheckBox1Changed(self, val):
    self.logic.tests[0][1] = val
  
  def onTestCheckBox2Changed(self, val):
    self.logic.tests[1][1] = val
  
  def onTestCheckBox3Changed(self, val):
    self.logic.tests[2][1] = val
  
  def onTestCheckBox4Changed(self, val):
    self.logic.tests[3][1] = val
  
  def onTestCheckBox5Changed(self, val):
    self.logic.tests[4][1] = val
  
  def onLocCheckBoxCLChanged(self, val):
    if val:
      self.logic.addWorkingVolumeTarget("CL")
      self.ui.hackCLButton.enabled = True
    else:
      self.logic.removeWorkingVolumeTarget("CL")
      self.ui.hackCLButton.enabled = False
  
  def onLocCheckBoxBLChanged(self, val):
    if val:
      self.logic.addWorkingVolumeTarget("BL")
      self.ui.hackBLButton.enabled = True
    else:
      self.logic.removeWorkingVolumeTarget("BL")
      self.ui.hackBLButton.enabled = False

  def onLocCheckBoxTLChanged(self, val):
    if val:
      self.logic.addWorkingVolumeTarget("TL")
      self.ui.hackTLButton.enabled = True
    else:
      self.logic.removeWorkingVolumeTarget("TL")
      self.ui.hackTLButton.enabled = False

  def onLocCheckBoxLLChanged(self, val):
    if val:
      self.logic.addWorkingVolumeTarget("LL")
      self.ui.hackLLButton.enabled = True
    else:
      self.logic.removeWorkingVolumeTarget("LL")
      self.ui.hackLLButton.enabled = False

  def onLocCheckBoxRLChanged(self, val):
    if val:
      self.logic.addWorkingVolumeTarget("RL")
      self.ui.hackRLButton.enabled = True
    else:
      self.logic.removeWorkingVolumeTarget("RL")
      self.ui.hackRLButton.enabled = False
  
  def onOperatorIdChanged(self):
    opId = self.ui.operatorLineEdit.text
    if opId != "" and opId != self.logic.operatorId: # not empty and not the same
      if not self.logic.operatorId: # if the first time
        # Enable locations checkboxes
        self.ui.locCheckBoxCL.enabled = self.ui.locCheckBoxCL.checked
        self.ui.locCheckBoxBL.enabled = self.ui.locCheckBoxBL.checked
        self.ui.locCheckBoxTL.enabled = self.ui.locCheckBoxTL.checked
        self.ui.locCheckBoxLL.enabled = self.ui.locCheckBoxLL.checked
        self.ui.locCheckBoxRL.enabled = self.ui.locCheckBoxRL.checked

        # Enable test checkboxes
        self.ui.testCheckBox1.enabled = True
        self.ui.testCheckBox2.enabled = True
        self.ui.testCheckBox3.enabled = True
        self.ui.testCheckBox4.enabled = True
        self.ui.testCheckBox5.enabled = True

      self.logic.operatorId = opId
      # Checking for dev
      pw = '8ee930e3474f1b9a4a0d7524f3527b93f1ff2e4fa89a385f1ede01a15d7cc9e4'
      salt = '68835c9b8f744414b1e1d2f262e7a911'
      if pw == hashlib.sha256(salt.encode() + self.logic.operatorId.encode()).hexdigest():
        logging.info("----- Oh, it's you! Welcome back, Sir! -----")
        self.ui.hackCollapsibleButton.collapsed = False
        self.ui.hackCollapsibleButton.enabled = True
        self.ui.hackCalibButton.enabled = True
        self.ui.hackCLButton.enabled = self.ui.locCheckBoxCL.checked
        self.ui.hackBLButton.enabled = self.ui.locCheckBoxBL.checked
        self.ui.hackTLButton.enabled = self.ui.locCheckBoxTL.checked
        self.ui.hackLLButton.enabled = self.ui.locCheckBoxLL.checked
        self.ui.hackRLButton.enabled = self.ui.locCheckBoxRL.checked
        self.ui.hackXButton.enabled = True
      else: # normal user
        logging.info(f"----- Welcome {opId} :) -----")
        self.ui.hackCollapsibleButton.collapsed = True
        self.ui.hackCollapsibleButton.enabled = False
      # if phantom calibration not done and not started, launch it
      if not self.logic.phantom.calibrated and not self.logic.calibratingPhantom:
        self.logic.startPhantomCalibration()

  def onTrackerIdChanged(self):
    tk = self.ui.trackerLineEdit.text
    if tk != "" and tk != self.logic.trackerId: # not empty and not the same
      if not self.logic.trackerId: # if the first time
        self.ui.pointerFileSelector.enabled = True
        self.ui.workingVolumeFileSelector.enabled = True
        self.ui.groundTruthFileSelector.enabled = True
        self.ui.operatorLineEdit.enabled = True
        # Enable point acquisition parametrization
        self.ui.pointAcqui1frameButton.enabled = True
        self.ui.pointAcquiMeanButton.enabled = True
        self.ui.pointAcquiMedianButton.enabled = True
        self.ui.pointAcquiNumFramesLineEdit.text = str(self.logic.pointer.numFrames)

    self.logic.trackerId = tk
    logging.info(f"Tracker Serial Number: {self.logic.trackerId}")

  def onPointAcqui1frameSet(self):
    self.ui.pointAcquiNumFramesLineEdit.enabled = False
    self.ui.pointAcquiFramesLabel.enabled = False
    self.logic.pointer.acquiMode = 0
    logging.info("Point acquisition set to 1-frame")
  
  def onPointAcquiMeanSet(self):
    self.ui.pointAcquiNumFramesLineEdit.enabled = True
    self.ui.pointAcquiFramesLabel.enabled = True
    self.logic.pointer.acquiMode = 1
    logging.info(f"Point acquisition set to MEAN across {self.logic.pointer.numFrames} frames")

  def onPointAcquiMedianSet(self):
    self.ui.pointAcquiNumFramesLineEdit.enabled = True
    self.ui.pointAcquiFramesLabel.enabled = True
    self.logic.pointer.acquiMode = 2
    logging.info(f"Point acquisition set to MEDIAN across {self.logic.pointer.numFrames} frames")

  def onPointAcquiNumFramesChanged(self):
    val = int(self.ui.pointAcquiNumFramesLineEdit.text)
    if val != self.logic.pointer.numFrames:
      self.logic.pointer.numFrames = val
      logging.info(f"Number of frames for point acquisition set to {self.logic.pointer.numFrames}")

  @vtk.calldata_type(vtk.VTK_OBJECT)
  def onNodeAdded(self, caller, event, calldata):
    """
    Called when a new node is added to the scene
    """
    calledNode = calldata
    logging.info('onNodeAdded: Called for ' + calledNode.GetName())
    if calledNode.GetName() == 'PointerToPhantom':
      self.ptrRefNode = calledNode
      self.ptrRefNode.AddObserver(slicer.vtkMRMLTransformNode.TransformModifiedEvent, \
        self.onNodeChanged)
    if calledNode.GetName() == 'PhantomToTracker':
      self.refNode = calledNode
      self.refNode.AddObserver(slicer.vtkMRMLTransformNode.TransformModifiedEvent, \
        self.onNodeChanged)
    if calledNode.GetName() == 'PointerToTracker':
      self.ptrNode = calledNode
      self.ptrNode.AddObserver(slicer.vtkMRMLTransformNode.TransformModifiedEvent, \
        self.onNodeChanged)

  @vtk.calldata_type(vtk.VTK_OBJECT)
  def onNodeChanged(self, caller, event=None, calldata=None):
    """
    Called when a node has changed
    """
    # set color with respect to status for each transform nodes
    def colorStatus(qlabel):
      if qlabel.text == "OK":
        qlabel.setStyleSheet("QLabel { color : green; }")
      elif qlabel.text == "MISSING":
        qlabel.setStyleSheet("QLabel { color : red; }")
      else:
        qlabel.setStyleSheet("QLabel { color : black; }")

    if caller.GetName() == 'PointerToTracker':
      self.ui.ptrStatusValue.text = caller.GetAttribute("TransformStatus")
      colorStatus(self.ui.ptrStatusValue)
    if caller.GetName() == 'PhantomToTracker':
      self.ui.refStatusValue.text = caller.GetAttribute("TransformStatus")
      colorStatus(self.ui.refStatusValue)
    if caller.GetName() == 'PointerToPhantom':
      self.ui.ptrRefStatusValue.text = caller.GetAttribute("TransformStatus")
      colorStatus(self.ui.ptrRefStatusValue)
    
    # set frame border to red if one transform status is "MISSING"
    if self.ui.ptrStatusValue.text != "OK" or \
    self.ui.refStatusValue.text != "OK" or \
    self.ui.ptrRefStatusValue.text != "OK":
      self.ui.statusFrame.setStyleSheet("#statusFrame { border: 1px solid red; }")
    else:
      self.ui.statusFrame.setStyleSheet("#statusFrame { border: 1px solid green; }")
    
    # Checking that all transform nodes are assigned and
    # in tracker's field of view (transform status "OK")
    if self.waitingForAllNodes and self.ptrNode and self.refNode and self.ptrRefNode:
      if self.ptrNode.GetAttribute("TransformStatus") == "OK"  and \
      self.refNode.GetAttribute("TransformStatus") == "OK" and \
      self.ptrRefNode.GetAttribute("TransformStatus") == "OK":
        self.waitingForAllNodes = False
        logging.info('onNodeChanged: all required transform nodes are valid, let\'s process!')
        self.logic.mainRenderer.RemoveActor(self.welcomeText)
        self.ui.trackerLineEdit.enabled = True
        self.ui.trackerLineEdit.setFocus()
        self.logic.process(self.ptrRefNode, self.refNode, self.ptrNode)
        # Selectors call since combobox already selected first item in each
        self.onPointerFileChanged()
        self.onWorkingVolumeFileChanged()
        self.onGroundTruthFileChanged()

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()

  def enter(self):
    """
    Called each time the user opens this module.
    """

  def exit(self):
    """
    Called each time the user opens a different module.
    """

  def onSceneStartClose(self, caller, event):
    """
    Called just before the scene is closed.
    """

  def onSceneEndClose(self, caller, event):
    """
    Called just after the scene is closed.
    """

  # ~~~~~~~~~~~~~~~~~~~ Hacks ~~~~~~~~~~~~~~~~~~~
  def hackCalib(self):
    if not os.path.isfile(self.resourcePath('defaultCalibs.txt')):
      logging.info("defaultCalibs file not found !")
    else:
      with open(self.resourcePath('defaultCalibs.txt'), 'r') as file:
        if not self.logic.calibratingPhantom:
          self.logic.startPhantomCalibration()
        lines = file.readlines()
        iLines = [i for i, s in enumerate(lines)]
        for i in iLines:
          # if line matches current working volume id
          if lines[i].startswith(self.logic.workingVolume.id):
            logging.info('~~~~~~~~~~~~ Hack calib ! ~~~~~~~~~~~~')
            for l in [lines[i+1], lines[i+2],lines[i+3]]: # take the three next lines
              if l.startswith("O =") or l.startswith("X =") or l.startswith("Y ="): # simple check
                lp = l.split("=")[1].split()
                cd = str([int(lp[0]), float(lp[1]),float(lp[2]),float(lp[3])])
                logging.info(cd)
                self.logic.onCalibrationPointDone(self.logic, 0, cd)
                self.logic.onCalibrationPointDoneOut(self.logic, 0, cd)

  def hackLoc(self, loc):
    if loc in self.logic.workingVolume.locs:
      logging.info(f"~~~~~~~~~~~~ Hack working volume {loc} ! ~~~~~~~~~~~~")
      cd = str([loc] + self.logic.workingVolume.simpPhantPosWithOffset())
      self.logic.wvTargetsTop.InvokeEvent(self.logic.wvTargetsTop.targetHitEvent, cd)
    else:
      logging.info(f"Cannot hack {loc}: not defined in working volume file")

  def hackCL(self):
    self.hackLoc('CL')
  
  def hackBL(self):
    self.hackLoc('BL')

  def hackTL(self):
    self.hackLoc('TL')
  
  def hackLL(self):
    self.hackLoc('LL')

  def hackRL(self):
    self.hackLoc('RL')

#
# AstmPhantomTestLogic
#

class AstmPhantomTestLogic(ScriptedLoadableModuleLogic, vtk.vtkObject):
  # added vtkObject as parent to enable invoking event from logic
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, phantomModelPath, pointerModelPath, simpPhantomPath, resourcePath, savePath):
    """
    Called when the logic class is instantiated. Can be used for initializing member variables.
    """    
    ScriptedLoadableModuleLogic.__init__(self)
    self.simpPhantomPath = simpPhantomPath
    self.resourcePath = resourcePath
    self.savePath = savePath
    self.testNamesUpdated = vtk.vtkCommand.UserEvent + 1
    self.sessionEndedEvent = vtk.vtkCommand.UserEvent + 2

    # If rendering is used, 3D views and renderers are made available by the widget class
    self.mainWidget = None
    self.mainRenderer = None
    self.topWVWidget = None
    self.topWVRenderer = None
    self.frontWVWidget = None
    self.frontWVRenderer = None

    # Creating core objects
    self.operatorId = None
    self.trackerId = None
    self.phantom = Phantom()
    self.phantom.readModel(phantomModelPath)
    self.calibratingPhantom = False
    self.pointer = Pointer()
    self.pointer.maxTilt = 50
    self.pointer.readModel(pointerModelPath)

    # Loading some sounds
    self.sounds = {}
    self.sounds["plop"] = qt.QSound(self.resourcePath + "sounds/plop.wav")
    self.sounds["done"] = qt.QSound(self.resourcePath + "sounds/done.wav")
    self.sounds["danger"] = qt.QSound(self.resourcePath + "sounds/danger.wav")
    self.sounds["error"] = qt.QSound(self.resourcePath + "sounds/error.wav")
    self.sounds["touchdown"] = qt.QSound(self.resourcePath + "sounds/touchdown.wav")

  def initialize(self):
    # Creating the targets and the working volume
    self.targets = Targets(self.mainRenderer)
    self.targetsDone = Targets(self.mainRenderer)
    self.workingVolume = WorkingVolume(self.topWVRenderer, self.frontWVRenderer)
    self.workingVolume.readSimpPhantomModel(self.simpPhantomPath)
    self.wvTargetsTop = Targets(self.workingVolume.renTop)
    self.wvTargetsFront = Targets(self.workingVolume.renFront)
    self.curLoc = "X" # null location in the working volume

    self.tests = [[]] # initialization
    self.testsToDo = []
    # Create all the tests (even if they might not be used)
    #   Single point accuracy and precision test
    self.singlePointMeasurement = SinglePointMeasurement()
    self.singleAnn = None
    #   Precision during rotation tests (0 = roll, 1 = pitch, 2 = yaw)
    self.rotMeasurements = [RotationMeasurement(0), RotationMeasurement(1), RotationMeasurement(2)]
    self.angleAnn = None # annotation actor for angle values
    #   Distance accuracy test
    self.distMeasurement = DistMeasurement()

  def process(self, ptrRefTransfoNode, refTransfoNode, ptrTransfoNode):
    """
    Run the processing algorithm.
    Can be used without GUI widget.
    """
    logging.info('Logic process launched !')

    if not ptrRefTransfoNode:
      raise ValueError("pointer from ref transform is invalid")
    else:
      self.ptrRefTransfoNode = ptrRefTransfoNode

    if not refTransfoNode:
      raise ValueError("reference transform is invalid")
    else:
      self.refTransfoNode = refTransfoNode

    if not ptrTransfoNode:
      raise ValueError("pointer transform is invalid")
    else:
      self.ptrTransfoNode = ptrTransfoNode

    # forward the transforms given by the tracker to the pointer model
    self.pointer.setTransfoNodes(ptrRefTransfoNode, ptrTransfoNode)
    # hide pointer model until phantom calibrated
    self.phantom.model.GetDisplayNode().VisibilityOn()

    # connections between the targets object (empty for now) and the pointer
    self.pointer.AddObserver(self.pointer.stoppedEvent, self.targets.onTargetFocus)
    self.pointer.AddObserver(self.pointer.acquiProgEvent, self.targets.onTargetIn)
    self.pointer.AddObserver(self.pointer.staticFailEvent, self.targets.onTargetOut)
    self.pointer.AddObserver(self.pointer.acquiDoneEvent, self.targets.onTargetDone)
    self.pointer.AddObserver(self.pointer.acquiDoneOutEvent, self.targets.onTargetDoneOut)

    # This list stores the tests order and if they are enabled
    self.tests = [['single',1], ['yaw',1], ['pitch',1], ['roll',1], ['dist',1]]
    self.InvokeEvent(self.testNamesUpdated, str([t[0] for t in self.tests]))

    # make sure the correct scene is rendered
    if self.mainWidget and self.topWVWidget and self.frontWVWidget:
      self.mainWidget.hide()
      self.topWVWidget.show()
      self.frontWVWidget.show()
      self.resetCam()

    # time beginning of process
    self.startTime = datetime.now()

    logging.info('All set !')

  def resetCam(self):
    if self.mainWidget.isVisible():
      if len(self.testsToDo) == 0:
        self.placeCamWrtPhantom(False)
      elif self.testsToDo[0] in ['roll', 'pitch', 'yaw']:
        self.placeCamWrtPhantom(True)
      else:
        self.placeCamWrtPhantom(False)
    elif self.topWVWidget.isVisible() and self.frontWVWidget.isVisible():
      self.workingVolume.resetCameras()

  def placeCamWrtPhantom(self, pointer = False):
    def placeCam(self, camPos, camDir):
      O = self.phantom.divPos(self.phantom.lblO)
      X = self.phantom.divPos(self.phantom.lblX)
      Y = self.phantom.divPos(self.phantom.lblY)
      vx = (X - O)/Dist(X, O)
      vy = (Y - O)/Dist(Y, O)
      vz = np.cross(vx, vy)
      rpos = O + camPos[0]*vx + camPos[1]*vy + camPos[2]*vz # real pos
      rcamDir = camDir[0]*vx + camDir[1]*vy + camDir[2]*vz # real cam dir
      rfpt = np.array([np.NaN,np.NaN,np.NaN]) # real focal point (declaration)
      # Caculate the focal point as the intersection of the phantom plane (O,X,Y) and cam direction
      if abs(np.dot(rcamDir, vz)) < 1e-4: # if plane and cam dir parallel
        rfpt = rpos + rcamDir*Dist(O, rpos) # set focal point at reasonable distance
      else:
        rfpt = rpos + rcamDir*np.dot(O-rpos, vz)/np.dot(rcamDir, vz)
      cam = self.mainRenderer.GetActiveCamera()
      cam.SetPosition(rpos)
      cam.SetFocalPoint(rfpt)
      cam.SetViewUp(vz)
      self.mainRenderer.ResetCameraClippingRange()

    if self.mainRenderer:
      if not pointer:
        # empirical good camera placement without the pointer
        camPos = np.array([65.101, -191.804, 204.762])
        camDir = np.array([0.006, 0.795, -0.606])
        placeCam(self, camPos, camDir)
      else:
        # empirical good camera placement with the pointer
        camPos = np.array([63.977, -242.82, 272.015])
        camDir = np.array([0.006, 0.795, -0.606])
        placeCam(self, camPos, camDir)

  def readPointerFile(self, path):
    if self.pointer.readPointerFile(path):
      return True
    else:
      return False

  def readWorkingVolumeFile(self, path):
    if self.workingVolume.readWorkingVolumeFile(path):
      # Remove previous targets
      self.wvTargetsTop.removeAllTargets()
      self.wvTargetsFront.removeAllTargets()
      # Add the new ones
      for k in self.workingVolume.locs:
        self.addWorkingVolumeTarget(k)
      # Forward to pointer the tracker axes for standard referential frame
      self.pointer.trkRollAxis = self.workingVolume.rollAxis
      self.pointer.trkPitchAxis = self.workingVolume.pitchAxis
      self.pointer.trkYawAxis = self.workingVolume.yawAxis
      self.pointer.checkTrkAxes()
      return True
    else:
      return False
  
  def addWorkingVolumeTarget(self, targetId):
    if targetId in self.workingVolume.locs:
      # check that target does not already exist, this may be possible as both locCheckBoxes
      # and readWorkingVolumeFile call addWorkingVolumeTarget
      if not targetId in self.wvTargetsTop.targets:
        p = self.workingVolume.locs[targetId]
        # if the location is at the top of the working volume, the pointer may go
        # out of the tracker's field of view
        if targetId == "TL" and self.pointer.height > 0:
          # the target position is then offset downward by the phantom's height
          # from the central divot (z-coord of divots 43-47) + the pointer's height
          offset = self.phantom.gtPts[47][2] + self.pointer.height
          # yaw axis is supposed to be tracker's "upward" vector
          p = p - self.workingVolume.yawAxis*offset
        self.wvTargetsTop.addTarget(targetId, p, True, False, 50)
      if not targetId in self.wvTargetsFront.targets:
        self.wvTargetsFront.addTarget(targetId, p, True, False, 50)
  
  def removeWorkingVolumeTarget(self, targetId):
    self.wvTargetsTop.removeTarget(targetId)
    self.wvTargetsFront.removeTarget(targetId)
    if not self.wvTargetsTop.targets and len(self.testsToDo) == 0:  # targets empty and tests done
      self.EndSession()

  def readGroundTruthFile(self, path):
    if self.phantom.readGroundTruthFile(path):
      self.placeCamWrtPhantom(False)
      return True
    else:
      return False

  # --------------------- Calibration ---------------------
  def startPhantomCalibration(self):
    logging.info('Calibration started')
    # make sure the correct scene is rendered
    if self.mainWidget and self.topWVWidget and self.frontWVWidget:
      self.mainWidget.show()
      self.topWVWidget.hide()
      self.frontWVWidget.hide()
    # if the phantom was already calibrated
    if self.phantom.calibrated:
      self.phantom.resetCalib()
      self.pointer.model.GetDisplayNode().VisibilityOff()

    # if another acquisition was already started
    self.pointer.timer.stop()
    self.targets.RemoveAllObservers()
    self.targets.removeAllTargets()  # making sure targets is empty

    # start the calibration
    self.pointer.timerDuration = 500  # ms
    self.targets.addTarget(self.phantom.lblO, self.phantom.divPos(self.phantom.lblO), True)
    self.targets.addTarget(self.phantom.lblX, self.phantom.divPos(self.phantom.lblX), False)
    self.targets.addTarget(self.phantom.lblY, self.phantom.divPos(self.phantom.lblY), False)

    self.calibObs1 = self.targets.AddObserver(self.targets.targetHitEvent, self.onCalibrationPointCheck)
    self.calibObs2 = self.targets.AddObserver(self.targets.targetDoneEvent, self.onCalibrationPointDone)
    self.calibObs3 = self.targets.AddObserver(self.targets.targetDoneOutEvent, self.onCalibrationPointDoneOut)

    self.calibratingPhantom = True
    self.phantom.InvokeEvent(self.phantom.calibStartedEvent)

  @vtk.calldata_type(vtk.VTK_STRING)
  def onCalibrationPointCheck(self, caller, event, calldata):
    cd = ast.literal_eval(calldata)
    valid = True
    for k in self.phantom.calGtPts:
      theoDist = Dist(self.phantom.gtPts[k], self.phantom.gtPts[cd[0]])
      dist = Dist(self.phantom.calGtPts[k], cd[1:4])
      err = abs(theoDist - dist)
      if err > 1.0:
        logging.info(f'   Invalid distance [{k}, {int(cd[0])}] (err = {err:.2f})')
        valid = False
    if valid:
      self.pointer.startAcquiring(caller)

  @vtk.calldata_type(vtk.VTK_STRING)
  def onCalibrationPointDone(self, caller, event, calldata):
    # play sound
    self.sounds["plop"].play()
    cd = ast.literal_eval(calldata)  # parse [id, px, py, pz]
    if cd[0] == self.phantom.lblO:
      self.phantom.calGtPts[self.phantom.lblO] = np.array(cd[1:4])
    if cd[0] == self.phantom.lblX:
      self.phantom.calGtPts[self.phantom.lblX] = np.array(cd[1:4])
    if cd[0] == self.phantom.lblY:
      self.phantom.calGtPts[self.phantom.lblY] = np.array(cd[1:4])

  @vtk.calldata_type(vtk.VTK_STRING)
  def onCalibrationPointDoneOut(self, caller, event, calldata):
    cd = ast.literal_eval(calldata)  # parse id
    if not isinstance(cd, list):
      cd = [cd]
    if cd[0] == self.phantom.lblO:
      self.targets.removeTarget(self.phantom.lblO)
    if cd[0] == self.phantom.lblX:
      self.targets.removeTarget(self.phantom.lblX)
    if cd[0] == self.phantom.lblY:
      self.targets.removeTarget(self.phantom.lblY)
    # try to calibrate (will skip if not all three corner targets acquired)
    self.phantom.calibrate()

    if self.phantom.calibrated:
      self.calibratingPhantom = False

      if self.phantom.model:
        # permanently transform the phantom model according to the calibration matrix
        self.phantom.model.SetAndObserveTransformNodeID(self.phantom.calibTransfoNode.GetID())
        self.phantom.model.HardenTransform()
        self.phantom.model.GetDisplayNode().VisibilityOn() # make it visible
        slicer.app.processEvents() # makes sure the rendering/display is done before continuing

      # new calib => new calibrated ground truth for the accuracy measurements
      if self.singlePointMeasurement:
        self.singlePointMeasurement.fullReset(self.phantom.calGtPts, self.phantom.centralDivot)
      if self.distMeasurement:
        self.distMeasurement.fullReset(self.phantom.calGtPts, self.phantom.seq)
      # but also reset rotation measurements then
      for r in self.rotMeasurements:
        r.fullReset()

      if self.workingVolume.simpPhantomModel:
        # similarly permanently transform the simplified phantom model
        self.workingVolume.simpPhantomModel.SetAndObserveTransformNodeID(
            self.phantom.calibTransfoNode.GetID())
        self.workingVolume.simpPhantomModel.HardenTransform()
        # but this time, the hardened model is also transformed
        self.workingVolume.setTransfoNode(self.refTransfoNode)
        slicer.app.processEvents() # makes sure the rendering/display is done before continuing
      
      # Add offset to simp phantom position (in ref marker referential!)
      # so that the central divot hits the wv targets
      self.workingVolume.offset = self.phantom.calGtPts[self.phantom.centralDivot]

      self.placeCamWrtPhantom()
      self.pointer.model.GetDisplayNode().VisibilityOn()
      self.targets.RemoveObserver(self.calibObs1)
      self.targets.RemoveObserver(self.calibObs2)
      self.targets.RemoveObserver(self.calibObs3)
      self.startWorkingVolumeGuidance()

  # --------------------- Working volume guidance ---------------------
  def startWorkingVolumeGuidance(self):
    logging.info('Starting working volume guidance')
    # make sure the correct scene is rendered
    if self.mainWidget and self.topWVWidget and self.frontWVWidget:
      self.mainWidget.hide()
      self.topWVWidget.show()
      self.frontWVWidget.show()
      self.workingVolume.simpPhantomModel.GetDisplayNode().VisibilityOn()

    slicer.app.processEvents() # makes sure the rendering/display is done before continuing
    if self.topWVRenderer:
      ResetCameraScreenSpace(self.topWVRenderer)
    if self.frontWVRenderer:
      ResetCameraScreenSpace(self.frontWVRenderer)
    if len(self.wvTargetsTop.targets) > 0:
      self.workingVolume.watchTransfoNode() # monitor phantom model placement
      self.wvTargetsTop.proxiDetect = True
      self.wvTargetsTop.proxiThresh = 100
      # the observer is set for the top view renderer only
      self.wvgObs1 = self.workingVolume.AddObserver(self.workingVolume.stoppedEvent,
        self.wvTargetsTop.onTargetFocus)
      self.wvgObs2 = self.wvTargetsTop.AddObserver(self.wvTargetsTop.targetHitEvent,
        self.stopWorkingVolumeGuidance)
    else:
      logging.info('====== All done, good job ^_^ ======')
      self.EndSession()

  @vtk.calldata_type(vtk.VTK_STRING)
  def stopWorkingVolumeGuidance(self, caller, event, calldata):
    cd = ast.literal_eval(calldata)
    self.curLoc = cd[0]
    logging.info(f'   Phantom placed for location {self.curLoc} at {np.around(cd[1:4],2).tolist()}')
    self.sounds["touchdown"].play()
    # make sure the correct scene is rendered
    if self.mainWidget and self.topWVWidget and self.frontWVWidget:
      self.mainWidget.show()
      self.topWVWidget.hide()
      self.frontWVWidget.hide()

    self.workingVolume.watchTransfoNode(False) # stop phantom model placement monitoring
    self.workingVolume.RemoveObserver(self.wvgObs1)
    self.wvTargetsTop.proxiDetect = False
    self.wvTargetsTop.RemoveObserver(self.wvgObs2)
    self.pointer.setMovingTolerance(self.workingVolume.movingToleranceFromPos(cd[1:4]))
    # Initialize tests todo list
    self.testsToDo = []
    for t in self.tests:
      if t[1]:
        self.testsToDo.append(t[0])

    self.removeWorkingVolumeTarget(self.curLoc)
    self.startNextTest()

  # ---------------------------- Tests Control -----------------------------
  def startNextTest(self):
    if len(self.testsToDo) == 0:
      self.startWorkingVolumeGuidance()
    else:
      if self.testsToDo[0] == 'single':
        self.startSinglePtTest()
      if self.testsToDo[0] == 'roll':
        self.startRotationTest(0)
      if self.testsToDo[0] == 'pitch':
        self.startRotationTest(1)
      if self.testsToDo[0] == 'yaw':
        self.startRotationTest(2)
      if self.testsToDo[0] == 'dist':
        self.startDistTest()

  # ---------------------------- Single Point Test -----------------------------
  def startSinglePtTest(self):
    logging.info(f'***** [{self.curLoc}] Single Point Test Start *****')
    self.singlePointMeasurement.acquiNumMax = 20
    self.singlePointMeasurement.curLoc = self.curLoc
    self.singlePointMeasurement.measurements[self.curLoc] = np.empty((0,3), float)
    if self.mainRenderer:
      if not self.singleAnn:
        self.singleAnn = vtk.vtkCornerAnnotation()
        self.singleAnn.GetTextProperty().SetFontSize(180)
        self.singleAnn.SetLinearFontScaleFactor(20)
        self.singleAnn.GetTextProperty().SetColor(1,0,0)
        self.singleAnn.GetTextProperty().BoldOn()
        self.singleAnn.GetTextProperty().ShadowOn()
      self.mainRenderer.AddActor(self.singleAnn)
      self.placeCamWrtPhantom() # place camera wrt phantom only

    self.targets.proxiDetect = True
    self.pointer.timerDuration = 500 # ms
    self.test1Obs1 = self.targets.AddObserver(self.targets.targetHitEvent, self.pointer.startAcquiring)
    self.test1Obs2 = self.targets.AddObserver(self.targets.targetDoneEvent, self.onSingPtMeasTargetDone)
    self.test1Obs3 = self.targets.AddObserver(self.targets.targetDoneOutEvent, self.onSingPtMeasTargetDoneOut)

    self.singleAnn.SetText(3, str(self.singlePointMeasurement.acquiNum)
        + "/" + str(self.singlePointMeasurement.acquiNumMax)) # 3 = top right
    self.singPtMeasNext()

  def singPtMeasNext(self):
    if self.singlePointMeasurement.acquiNum < self.singlePointMeasurement.acquiNumMax:
      gtpos = self.phantom.divPos(self.singlePointMeasurement.divot)
      self.targets.addTarget(self.singlePointMeasurement.divot, gtpos, True)
    else:
      # play sound
      self.sounds["done"].play()
      self.stopSinglePtTest()

  @vtk.calldata_type(vtk.VTK_STRING)
  def onSingPtMeasTargetDone(self, caller, event, calldata):
    cd = ast.literal_eval(calldata)
    lblHit = int(cd[0])
    pos = np.array(cd[1:4])
    if lblHit == self.phantom.centralDivot:  # just a verification
      self.singlePointMeasurement.onDivDone(pos)
      # play sound
      self.sounds["plop"].play()
      self.singleAnn.SetText(3, str(self.singlePointMeasurement.acquiNum)
        + "/" + str(self.singlePointMeasurement.acquiNumMax)) # 3 = top right

  @vtk.calldata_type(vtk.VTK_STRING)
  def onSingPtMeasTargetDoneOut(self, caller, event, calldata):
    self.targets.removeTarget(self.singlePointMeasurement.divot)
    # display the next divot
    self.singPtMeasNext()

  def stopSinglePtTest(self):
    logging.info(f'----- [{self.curLoc}] Single Point Test Stop -----')
    if self.mainRenderer:
      self.mainRenderer.RemoveActor(self.singleAnn)
    self.targets.proxiDetect = False
    self.targets.removeAllTargets()
    self.targets.RemoveObserver(self.test1Obs1)
    self.targets.RemoveObserver(self.test1Obs2)
    self.targets.RemoveObserver(self.test1Obs3)
    # Forward measured average position to rotation tests
    for m in self.rotMeasurements:
      m.basePos = self.singlePointMeasurement.avgPos
    # Reset
    self.singlePointMeasurement.reset()
    self.testsToDo.pop(0) # remove the test
    self.startNextTest()

  # ---------------------------- Rotation Tests -----------------------------
  def startRotationTest(self, i):
    self.curRotMeas = self.rotMeasurements[i]
    self.curRotAxis = self.curRotMeas.rotAxis
    self.curRotAxisName = self.curRotMeas.rotAxisName
    logging.info(f'***** [{self.curLoc}] {self.curRotAxisName} Rotation Test Start *****')
    self.curRotMeas.curLoc = self.curLoc # assign current location
    self.curRotMeas.measurements[self.curLoc] = np.empty((0,4), float)
    if not self.angleAnn:
      self.angleAnn = vtk.vtkCornerAnnotation()
      self.angleAnn.GetTextProperty().SetFontSize(180)
      self.angleAnn.SetLinearFontScaleFactor(20)
      self.angleAnn.GetTextProperty().SetColor(1,0,0)
      self.angleAnn.GetTextProperty().BoldOn()
      self.angleAnn.GetTextProperty().ShadowOn()
    self.angleAnn.SetText(2, "-.-") # 2 = top left
    self.placeCamWrtPhantom(True) # place camera wrt phantom while showing pointer

    self.targets.proxiDetect = True
    self.rotTestObs1 = self.targets.AddObserver(self.targets.targetHitEvent,
      self.onRotMeasTargetHit)
    self.rotTestObs2 = self.targets.AddObserver(self.targets.targetOutEvent,
      self.onRotMeasTargetOut)
    div = self.singlePointMeasurement.divot # use same central divot as Single Point Test 
    self.targets.addTarget(div, self.phantom.divPos(div), True)

    self.rotTestAcquiring = False

  @vtk.calldata_type(vtk.VTK_STRING)
  def onRotMeasTargetHit(self, caller, event = None, calldata = None):
    self.pointer.staticConstraint = True
    self.pointer.emitAngles = True
    self.rotTestObs3 = self.pointer.AddObserver(self.pointer.anglesChangedEvent,
      self.onPointerAnglesChanged)
    self.rotTestObs4 = self.pointer.AddObserver(self.pointer.trackingStartedEvent,
      self.onPointerTrackingStarted)
    self.rotTestObs5 = self.pointer.AddObserver(self.pointer.trackingStoppedEvent,
      self.onPointerTrackingStopped)
    if self.mainRenderer:
      self.mainRenderer.AddActor(self.angleAnn)

  @vtk.calldata_type(vtk.VTK_STRING)
  def onRotMeasTargetOut(self, caller, event = None, calldata = None):
    self.pointer.staticConstraint = False
    self.pointer.emitAngles = False
    self.pointer.RemoveObserver(self.rotTestObs3)
    self.pointer.RemoveObserver(self.rotTestObs4)
    self.pointer.RemoveObserver(self.rotTestObs5)
    if self.mainRenderer:
      self.mainRenderer.RemoveActor(self.angleAnn)

  @vtk.calldata_type(vtk.VTK_STRING)
  def onPointerAnglesChanged(self, caller, event=None, calldata=None):
    cd = ast.literal_eval(calldata)
    if self.curRotAxis == 0:
      self.angleAnn.SetText(2, f">Roll={cd[0]:.1f}<\n  Pitch={cd[1]:.1f}\n  Yaw={cd[2]:.1f}")
    elif self.curRotAxis == 1:
      self.angleAnn.SetText(2, f"  Roll={cd[0]:.1f}\n>Pitch={cd[1]:.1f}<\n  Yaw={cd[2]:.1f}")
    elif self.curRotAxis == 2:
      self.angleAnn.SetText(2, f"  Roll={cd[0]:.1f}\n  Pitch={cd[1]:.1f}\n>Yaw={cd[2]:.1f}<")
    else:
      self.angleAnn.SetText(2, '~(*_*)~')
    self.rotAng = cd[self.curRotAxis]
    self.rotPos = cd[3:]
    if self.rotTestAcquiring:
      # compare the current angle to that from the last sample
      # the first angle sign prevents sampling backwards
      firstA = self.curRotMeas.measurements[self.curLoc][0,0]
      lastA = self.curRotMeas.measurements[self.curLoc][-1,0]
      if firstA < 0 and self.rotAng - lastA > self.curRotMeas.angStep or \
        firstA > 0 and lastA - self.rotAng > self.curRotMeas.angStep:
          logging.info(f"  {self.curRotAxisName} rotation sampled at {self.rotAng:.1f} "
            f"=> pos {np.around(self.rotPos, 2).tolist()}")
          # store measurement
          self.curRotMeas.measurements[self.curLoc] = np.append(
            self.curRotMeas.measurements[self.curLoc],
            [np.append(self.rotAng, self.rotPos)], axis = 0)
    
  @vtk.calldata_type(vtk.VTK_STRING)
  def onPointerTrackingStarted(self, caller, event=None, calldata=None):
    if not self.rotTestAcquiring:
      # play sound
      self.sounds["plop"].play()
      logging.info("    Rotation Acquisition Started !")
      # store the first measurement
      logging.info(f"  {self.curRotAxisName} rotation sampled at {self.rotAng:.1f} "
        f"=> pos {np.around(self.rotPos, 2).tolist()}")
      self.curRotMeas.measurements[self.curLoc] = np.append(
        self.curRotMeas.measurements[self.curLoc],
        [np.append(self.rotAng, self.rotPos)], axis = 0)
      self.rotTestAcquiring = True

  @vtk.calldata_type(vtk.VTK_STRING)
  def onPointerTrackingStopped(self, caller, event=None, calldata=None):
    # check that the acquisition is undergoing and that at least 6 measurements have been taken
    if self.rotTestAcquiring and len(self.curRotMeas.measurements[self.curLoc]) > 6:
      self.rotTestAcquiring = False
      logging.info(f"    Rotation Acquisition Stopped !")
      # play sound
      self.sounds["done"].play()
      self.stopRotationTest()

  def stopRotationTest(self):
    logging.info(f'----- [{self.curLoc}] {self.curRotAxisName} Rotation Test Stop -----')
    self.placeCamWrtPhantom(False) # place camera wrt phantom ignoring pointer
    self.onRotMeasTargetOut(self) # stop monitoring tracking and angles
    self.targets.proxiDetect = False
    self.targets.removeAllTargets()
    self.targets.RemoveObserver(self.rotTestObs1)
    self.targets.RemoveObserver(self.rotTestObs2)

    self.curRotMeas.updateStats()
    self.curRotMeas.reset() # make it ready for next acquisition at a different location
    self.testsToDo.pop(0) # remove the test
    self.startNextTest()

  # ---------------------------- Multi-point Test -----------------------------
  def startDistTest(self):
    logging.info(f'***** [{self.curLoc}] Multi-point Test Start *****')
    self.targets.proxiDetect = True
    self.pointer.timerDuration = 500 # ms
    self.distMeasurement.curLoc = self.curLoc
    self.distMeasurement.measurements[self.curLoc] = {}

    self.targets.AddObserver(self.targets.targetHitEvent, self.pointer.startAcquiring)
    self.targets.AddObserver(self.targets.targetDoneEvent, self.onDistMeasTargetDone)
    self.targets.AddObserver(self.targets.targetDoneOutEvent, self.onDistMeasTargetDoneOut)
    self.distMeasNextDiv()

  def distMeasNextDiv(self):
    if len(self.distMeasurement.divotsToDo) > 0:
      self.distMeasurement.currLbl = self.distMeasurement.divotsToDo[0]
      gtpos = self.phantom.divPos(self.distMeasurement.currLbl)
      self.targets.addTarget(self.distMeasurement.currLbl, gtpos, True)
    else:
      # play sound
      self.sounds["done"].play()
      self.stopDistTest()

  @vtk.calldata_type(vtk.VTK_STRING)
  def onDistMeasTargetDone(self, caller, event, calldata):
    cd = ast.literal_eval(calldata)
    lblHit = int(cd[0])
    pos = np.array(cd[1:4])
    if lblHit == self.distMeasurement.currLbl:  # just a verification
      self.distMeasurement.onDivDone(pos)
      # play sound
      self.sounds["plop"].play()

  @vtk.calldata_type(vtk.VTK_STRING)
  def onDistMeasTargetDoneOut(self, caller, event, calldata):
    self.targets.removeTarget(self.distMeasurement.currLbl)
    # add a smaller green ball to indicate that this divot has been acquired
    gtPos = self.phantom.divPos(self.distMeasurement.currLbl)
    self.targetsDone.addTarget(self.distMeasurement.currLbl, gtPos, True, False, 3, [0.0,1.0,0.0,0.7])
    # display the next divot
    self.distMeasNextDiv()

  def stopDistTest(self):
    logging.info(f'----- [{self.curLoc}] Multi-point Test Stop -----')
    self.targets.proxiDetect = False
    self.targets.removeAllTargets()
    self.targets.RemoveAllObservers()
    self.targetsDone.removeAllTargets()
    self.targetsDone.RemoveAllObservers()
    # Reset
    self.distMeasurement.reset(self.phantom.seq)
    self.testsToDo.pop(0) # remove the test
    self.startNextTest()

  # -------------------------------------------------------------------
  def EndSession(self):
    self.InvokeEvent(self.sessionEndedEvent)
    logging.info("---------------------Global Stats---------------------")

    def keyToEnd(d,k): # if key k exists in dict d, place it at the end
      if k in d:
        tmp = d[k].copy()
        d.pop(k, None)
        d[k] = tmp

    if self.singlePointMeasurement:
      if "ALL" in self.singlePointMeasurement.accuracyStats:
        keyToEnd(self.singlePointMeasurement.accuracyStats, "ALL") # move "ALL" to end of dictionary
        logging.info(f'>> Single Point Accuracy ({self.singlePointMeasurement.accuracyStats["ALL"]["num"]}): '
          f'mean = {self.singlePointMeasurement.accuracyStats["ALL"]["avg err"]:.2f}, '
          f'max = {self.singlePointMeasurement.accuracyStats["ALL"]["max"]:.2f}')
      if "ALL" in self.singlePointMeasurement.precisionStats:
        keyToEnd(self.singlePointMeasurement.precisionStats, "ALL")
        logging.info(f'>> Single Point Precision ({self.singlePointMeasurement.precisionStats["ALL"]["num"]}): '
          f'span = {self.singlePointMeasurement.precisionStats["ALL"]["span"]:.2f}, '
          f'RMS = {self.singlePointMeasurement.precisionStats["ALL"]["rms"]:.2f}')

    for rm in self.rotMeasurements:
      if "ALL" in rm.stats:
        keyToEnd(rm.stats, "ALL")
        logging.info(f'>> {rm.rotAxisName} Rotation Precision ({rm.stats["ALL"]["num"]}): '
          f'rangeMin = {rm.stats["ALL"]["rangeMin"]:.2f}, '
          f'rangeMax = {rm.stats["ALL"]["rangeMax"]:.2f}, '
          f'span = {rm.stats["ALL"]["span"]:.2f}, '
          f'RMS = {rm.stats["ALL"]["rms"]:.2f}')

    if self.distMeasurement:
      if "ALL" in self.distMeasurement.distStats:
        keyToEnd(self.distMeasurement.distStats, "ALL")
        logging.info(f'>> Distance errors ({self.distMeasurement.distStats["ALL"]["num"]}): '
          f'mean = {self.distMeasurement.distStats["ALL"]["mean"]:.2f}, '
          f'min = {self.distMeasurement.distStats["ALL"]["min"]:.2f}, '
          f'max = {self.distMeasurement.distStats["ALL"]["max"]:.2f}, '
          f'RMS = {self.distMeasurement.distStats["ALL"]["rms"]:.2f}')
      if "ALL" in self.distMeasurement.regStats:
        keyToEnd(self.distMeasurement.regStats, "ALL")
        logging.info(f'>> Registration errors ({self.distMeasurement.regStats["ALL"]["num"]}): '
          f'mean = {self.distMeasurement.regStats["ALL"]["mean"]:.2f}, '
          f'min = {self.distMeasurement.regStats["ALL"]["min"]:.2f}, '
          f'max = {self.distMeasurement.regStats["ALL"]["max"]:.2f}, '
          f'RMS = {self.distMeasurement.regStats["ALL"]["rms"]:.2f}')

    logging.info("------------------------------------------------------")

    # All data serialization
    dts = self.startTime.strftime("%Y.%m.%d_%H.%M.%S")
    jsonPath =  self.savePath + f"/AstmPhantomTest_data_{dts}.json"
    self.endTime = datetime.now()
    td = self.endTime - self.startTime # time delta
    durStr = f"{td.days*24+td.seconds//3600}h{td.seconds%3600//60}min{td.seconds%60}s"
    if self.pointer.acquiMode == 0:
      pointAcquiMode = "1-frame"
    elif self.pointer.acquiMode == 1:
      pointAcquiMode = f"Mean ({self.pointer.numFrames} frames)"
    elif self.pointer.acquiMode == 2:
      pointAcquiMode = f"Median ({self.pointer.numFrames} frames)"
    else:
      pointAcquiMode = "unknown"

    obj = json.dumps({"Tracker Serial Number": self.trackerId,
      "Pointer": self.pointer.id,
      "Working Volume": self.workingVolume.id,
      "Phantom": self.phantom.id,
      "Operator": self.operatorId,
      "Start date_time": dts,
      "Duration": durStr,
      "Central Divot": self.phantom.centralDivot,
      "Point acquisition": pointAcquiMode,
      "Calibrated Ground Truth": self.phantom.calGtPts,
      "Single Point Measurements": self.singlePointMeasurement.measurements,
      f"{self.rotMeasurements[0].rotAxisName} Rotation Measurements": self.rotMeasurements[0].measurements,
      f"{self.rotMeasurements[1].rotAxisName} Rotation Measurements": self.rotMeasurements[1].measurements,
      f"{self.rotMeasurements[2].rotAxisName} Rotation Measurements": self.rotMeasurements[2].measurements,
      "Multi-point Measurements": self.distMeasurement.measurements},
      indent = 2,
      cls=NumpyEncoder) # important to use the custom class to handle nd-array serialization
    with open(jsonPath, 'w') as outfile:
      outfile.write(obj)
      logging.info(f'All measurements written in {jsonPath}')

    # Generating report in HTML
    # Stack all values
    locations = ["ALL", "CL", "BL", "TL", "LL", "RL"] # match html order
    def lookup(d, k, locs): # look up key k in dict d at locations locs
      lst = []
      for l in locs:
        if l in d:
          if k in d[l]:
            if isinstance(d[l][k], float):
              lst.append(round(d[l][k],2)) # if float, round to 2 decimal places
            else:
              lst.append(d[l][k])
            continue
        lst.append("-")
      return lst

    sv = [lookup(self.singlePointMeasurement.accuracyStats,"num", locations),
        lookup(self.singlePointMeasurement.accuracyStats,"avg err", locations),
        lookup(self.singlePointMeasurement.accuracyStats,"max", locations),
        lookup(self.singlePointMeasurement.precisionStats,"span", locations),
        lookup(self.singlePointMeasurement.precisionStats,"rms", locations)]
    r0v = [lookup(self.rotMeasurements[0].stats,"num", locations),
        lookup(self.rotMeasurements[0].stats,"rangeMin", locations),
        lookup(self.rotMeasurements[0].stats,"rangeMax", locations),
        lookup(self.rotMeasurements[0].stats,"span", locations),
        lookup(self.rotMeasurements[0].stats,"rms", locations)]
    r1v = [lookup(self.rotMeasurements[1].stats,"num", locations),
        lookup(self.rotMeasurements[1].stats,"rangeMin", locations),
        lookup(self.rotMeasurements[1].stats,"rangeMax", locations),
        lookup(self.rotMeasurements[1].stats,"span", locations),
        lookup(self.rotMeasurements[1].stats,"rms", locations)]
    r2v = [lookup(self.rotMeasurements[2].stats,"num", locations),
        lookup(self.rotMeasurements[2].stats,"rangeMin", locations),
        lookup(self.rotMeasurements[2].stats,"rangeMax", locations),
        lookup(self.rotMeasurements[2].stats,"span", locations),
        lookup(self.rotMeasurements[2].stats,"rms", locations)]
    mv = [lookup(self.distMeasurement.regStats,"num", locations),
        lookup(self.distMeasurement.distStats,"num", locations),
        lookup(self.distMeasurement.distStats,"mean", locations),
        lookup(self.distMeasurement.distStats,"min", locations),
        lookup(self.distMeasurement.distStats,"max", locations),
        lookup(self.distMeasurement.distStats,"rms", locations),
        lookup(self.distMeasurement.regStats,"mean", locations),
        lookup(self.distMeasurement.regStats,"min", locations),
        lookup(self.distMeasurement.regStats,"max", locations),
        lookup(self.distMeasurement.regStats,"rms", locations)]
    f = open(self.savePath + f"/AstmPhantomTest_report_{dts}.html", "w")
    f.write(
      f'<!DOCTYPE html>\n'
      f'<html>\n'
      f'<head>\n'
      f'<style>\n'
      f'table {{\n'
      f'  font-family: arial, sans-serif;\n'
      f'  border-collapse: collapse;\n'
      f'}}\n'
      f'\n'
      f'td, th {{\n'
      f'  border: 1px solid #00355B;\n'
      f'  text-align: center;\n'
      f'  padding: 8px;\n'
      f'}}\n'
      f'\n'
      f'td {{'
      f'  min-width: 40px;\n'
      f'}}\n'
      f'\n'
      f'tr:nth-child(even) {{\n'
      f'  background-color: #D2F1FF;\n'
      f'}}\n'
      f'td:nth-child(1) {{\n'
      f'  text-align: right;\n'
      f'}}\n'
      f'</style>\n'
      f'</head>\n'
      f'<body>\n'
      f'\n'
      f'<h2>ASTM Phantom Tests Report</h2>\n'
      f'<div style="overflow-x: auto;">\n'
      f'<table style="min-width: 400px;">\n'
      f'  <tr><td width="175px">Start date_time</td><td>{dts}</td></tr>\n'
      f'  <tr><td>Duration</td><td>{durStr}</td></tr>\n'
      f'  <tr><td>Operator id</td><td>{self.operatorId}</td></tr>\n'
      f'  <tr><td>Tracker Serial number</td><td>{self.trackerId}</td></tr>\n'
      f'</table>\n'
      f'<p>\n'
      f'<table style="min-width: 400px;">\n'
      f'  <tr><td width="175px">Pointer id</td><td>{self.pointer.id}</td></tr>\n'
      f'  <tr><td>Working volume id</td><td>{self.workingVolume.id}</td></tr>\n'
      f'  <tr><td>Phantom id</td><td>{self.phantom.id}</td></tr>\n'
      f'  <tr><td>Central divot id</td><td>{self.phantom.centralDivot}</td></tr>\n'
      f'  <tr><td>Point acquisition</td><td>{pointAcquiMode}</td></tr>\n'
      f'</table>\n'
      f'\n'
      f'<h3>Single Point Accuracy and Precision Test</h3>\n'
      f'This test measures the accuracy and precision of single point acquisition by repeatedly picking the central divot. The number of measurements is reported in the table below.<br>\n'
      f'For accuracy, the errors are the vectors from the corresponding reference point (central divot) to each measurement. The accuracy mean is the length of the average of these vectors. The accuracy max is the length of the longest vector.<br>\n'
      f'For precision, the maximum distance of between two measurements (span) is reported. Also, the deviations are calculated as the distances of all the measurements from their average. Calculated as such, the Root Mean Square (RMS) of the deviations equates their standard deviation and is reported.\n'
      f'<p>\n'
      f'<table style="max-width: 700px;" class="hide">\n'
      f'  <tr><td colspan="2">Locations</td><td><b>ALL</td><td>CL</td><td>BL</td><td>TL</td><td>LL</td><td>RL</td></tr>\n'
      f'  <tr><td width="175px" colspan="2">Measurements</td><td><b>{sv[0][0]}</td><td>{sv[0][1]}</td><td>{sv[0][2]}</td><td>{sv[0][3]}</td><td>{sv[0][4]}</td><td>{sv[0][5]}</td></tr>\n'
      f'  <tr><td rowspan="2">Accuracy (mm)</td>\n'
      f'      <td>Mean</td><td><b>{sv[1][0]}</td><td>{sv[1][1]}</td><td>{sv[1][2]}</td><td>{sv[1][3]}</td><td>{sv[1][4]}</td><td>{sv[1][5]}</td></tr>\n'
      f'  <tr><td>Max</td><td><b>{sv[2][0]}</td><td>{sv[2][1]}</td><td>{sv[2][2]}</td><td>{sv[2][3]}</td><td>{sv[2][4]}</td><td>{sv[2][5]}</td></tr>\n'
      f'  <tr><td rowspan="2">Precision (mm)</td>\n'
      f'      <td>Span</td><td><b>{sv[3][0]}</td><td>{sv[3][1]}</td><td>{sv[3][2]}</td><td>{sv[3][3]}</td><td>{sv[3][4]}</td><td>{sv[3][5]}</td></tr>\n'
      f'  <tr><td>RMS</td><td><b>{sv[4][0]}*</td><td>{sv[4][1]}</td><td>{sv[4][2]}</td><td>{sv[4][3]}</td><td>{sv[4][4]}</td><td>{sv[4][5]}</td></tr>\n'
      f'</table>\n'
      f'* The RMS for <b>ALL</b> is the RMS of the standard deviations (i.e. the RMS) at each location.<br>\n'
      f'\n'
      f'<h3>Rotation Precision Tests</h3>\n'
      f'The rotation tests measure the precision of single point acquisition under various orientations of the pointer. These orientations consists of <b>successive</b> rotations around the roll, pitch and yaw axes of the pointer.<br>\n'
      f'The measurements consist in sampling the position of the pointer every 1° during a rotation. The number of measurements is reported in the table below.<br>\n'
      f'For each rotation axis (roll, pitch, yaw), the minimum and maximum angles for which tracking is possible are reported.<br>\n'
      f'For precision, the maximum distance of between two measurements (span) and the RMS of the deviations are reported. The deviations are calculated as the distances of each measurement from the average position previously determined in the Single Point Test. If the Single Point Test is not performed, then the ground truth position of the measured divot is used instead of the average position.\n'
      f'\n'
      f'<h4>{self.rotMeasurements[0].rotAxisName} Rotation Precision Test</h4>\n'
      f'\n'
      f'<table style="max-width: 700px;">\n'
      f'  <tr><td colspan="2">Locations</td><td><b>ALL</td><td>CL</td><td>BL</td><td>TL</td><td>LL</td><td>RL</td></tr>\n'
      f'  <tr><td width="175px" colspan="2">Measurements</td><td><b>{r0v[0][0]}</td><td>{r0v[0][1]}</td><td>{r0v[0][2]}</td><td>{r0v[0][3]}</td><td>{r0v[0][4]}</td><td>{r0v[0][5]}</td></tr>\n'
      f'  <tr><td rowspan="2">Angle (°)</td>\n'
      f'      <td>Min</td><td><b>{r0v[1][0]}</td><td>{r0v[1][1]}</td><td>{r0v[1][2]}</td><td>{r0v[1][3]}</td><td>{r0v[1][4]}</td><td>{r0v[1][5]}</td></tr>\n'
      f'  <tr><td>Max</td><td><b>{r0v[2][0]}</td><td>{r0v[2][1]}</td><td>{r0v[2][2]}</td><td>{r0v[2][3]}</td><td>{r0v[2][4]}</td><td>{r0v[2][5]}</td></tr>\n'
      f'  <tr><td rowspan="2">Precision (mm)</td>\n'
      f'      <td>Span</td><td><b>{r0v[3][0]}</td><td>{r0v[3][1]}</td><td>{r0v[3][2]}</td><td>{r0v[3][3]}</td><td>{r0v[3][4]}</td><td>{r0v[3][5]}</td></tr>\n'
      f'  <tr><td>RMS</td><td><b>{r0v[4][0]}*</td><td>{r0v[4][1]}</td><td>{r0v[4][2]}</td><td>{r0v[4][3]}</td><td>{r0v[4][4]}</td><td>{r0v[4][5]}</td></tr>\n'
      f'</table>\n'
      f'* The RMS for <b>ALL</b> is the RMS of the standard deviations (i.e. the RMS) at each location.<br>\n'
      f'\n'
      f'<h4>{self.rotMeasurements[1].rotAxisName} Rotation Precision Test</h4>\n'
      f'\n'
      f'<table style="max-width: 700px;">\n'
      f'  <tr><td colspan="2">Locations</td><td><b>ALL</td><td>CL</td><td>BL</td><td>TL</td><td>LL</td><td>RL</td></tr>\n'
      f'  <tr><td width="175px" colspan="2">Measurements</td><td><b>{r1v[0][0]}</td><td>{r1v[0][1]}</td><td>{r1v[0][2]}</td><td>{r1v[0][3]}</td><td>{r1v[0][4]}</td><td>{r1v[0][5]}</td></tr>\n'
      f'  <tr><td rowspan="2">Angle (°)</td>\n'
      f'      <td>Min</td><td><b>{r1v[1][0]}</td><td>{r1v[1][1]}</td><td>{r1v[1][2]}</td><td>{r1v[1][3]}</td><td>{r1v[1][4]}</td><td>{r1v[1][5]}</td></tr>\n'
      f'  <tr><td>Max</td><td><b>{r1v[2][0]}</td><td>{r1v[2][1]}</td><td>{r1v[2][2]}</td><td>{r1v[2][3]}</td><td>{r1v[2][4]}</td><td>{r1v[2][5]}</td></tr>\n'
      f'  <tr><td rowspan="2">Precision (mm)</td>\n'
      f'      <td>Span</td><td><b>{r1v[3][0]}</td><td>{r1v[3][1]}</td><td>{r1v[3][2]}</td><td>{r1v[3][3]}</td><td>{r1v[3][4]}</td><td>{r1v[3][5]}</td></tr>\n'
      f'  <tr><td>RMS</td><td><b>{r1v[4][0]}*</td><td>{r1v[4][1]}</td><td>{r1v[4][2]}</td><td>{r1v[4][3]}</td><td>{r1v[4][4]}</td><td>{r1v[4][5]}</td></tr>\n'
      f'</table>\n'
      f'* The RMS for <b>ALL</b> is the RMS of the standard deviations (i.e. the RMS) at each location.<br>\n'
      f'\n'
      f'<h4>{self.rotMeasurements[2].rotAxisName} Rotation Precision Test</h4>\n'
      f'\n'
      f'<table style="max-width: 700px;">\n'
      f'  <tr><td colspan="2">Locations</td><td><b>ALL</td><td>CL</td><td>BL</td><td>TL</td><td>LL</td><td>RL</td></tr>\n'
      f'  <tr><td width="175px" colspan="2">Measurements</td><td><b>{r2v[0][0]}</td><td>{r2v[0][1]}</td><td>{r2v[0][2]}</td><td>{r2v[0][3]}</td><td>{r2v[0][4]}</td><td>{r2v[0][5]}</td></tr>\n'
      f'  <tr><td rowspan="2">Angle (°)</td>\n'
      f'      <td>Min</td><td><b>{r2v[1][0]}</td><td>{r2v[1][1]}</td><td>{r2v[1][2]}</td><td>{r2v[1][3]}</td><td>{r2v[1][4]}</td><td>{r2v[1][5]}</td></tr>\n'
      f'  <tr><td>Max</td><td><b>{r2v[2][0]}</td><td>{r2v[2][1]}</td><td>{r2v[2][2]}</td><td>{r2v[2][3]}</td><td>{r2v[2][4]}</td><td>{r2v[2][5]}</td></tr>\n'
      f'  <tr><td rowspan="2">Precision (mm)</td>\n'
      f'      <td>Span</td><td><b>{r2v[3][0]}</td><td>{r2v[3][1]}</td><td>{r2v[3][2]}</td><td>{r2v[3][3]}</td><td>{r2v[3][4]}</td><td>{r2v[3][5]}</td></tr>\n'
      f'  <tr><td>RMS</td><td><b>{r2v[4][0]}*</td><td>{r2v[4][1]}</td><td>{r2v[4][2]}</td><td>{r2v[4][3]}</td><td>{r2v[4][4]}</td><td>{r2v[4][5]}</td></tr>\n'
      f'</table>\n'
      f'* The RMS for <b>ALL</b> is the RMS of the standard deviations (i.e. the RMS) at each location.<br>\n'
      f'\n'
      f'<h3>Multi-point Accuracy Test</h3>\n'
      f'This test measures the spatial relationship between various acquired points and compare it to the reference values. This can be done in two ways: distances or point cloud registration.<br>\n'
      f'The distances are calculated for all combinations of pair of points. So, for N points measured, there are N(N-1)/2 distances (e.g. 20 measured points gives 190 distances). For each pair of points, the error is calculated as the difference with the corresponding reference pair in terms of distance. The number of distances and the mean, minimum, maximum and RMS of these errors are reported below.<br>\n'
      f'The registration is performed between the point clouds from the measurements and from the reference. The mean, minimum, maximum, RMS of the registration residuals are reported below.\n'
      f'<p>\n'
      f'<table style="max-width: 700px;">\n'
      f'  <tr><td colspan="2">Locations</td><td><b>ALL</td><td>CL</td><td>BL</td><td>TL</td><td>LL</td><td>RL</td></tr>\n'
      f'  <tr><td width="175px" colspan="2">Measurements</td><td><b>{mv[0][0]}</td><td>{mv[0][1]}</td><td>{mv[0][2]}</td><td>{mv[0][3]}</td><td>{mv[0][4]}</td><td>{mv[0][5]}</td></tr>\n'
      f'  <tr><td rowspan="5">Distances (mm)</td>\n'
      f'      <td>Num.</td><td><b>{mv[1][0]}</td><td>{mv[1][1]}</td><td>{mv[1][2]}</td><td>{mv[1][3]}</td><td>{mv[1][4]}</td><td>{mv[1][5]}</td></tr>\n'
      f'  <tr><td>Mean</td><td><b>{mv[2][0]}</td><td>{mv[2][1]}</td><td>{mv[2][2]}</td><td>{mv[2][3]}</td><td>{mv[2][4]}</td><td>{mv[2][5]}</td></tr>\n'
      f'  <tr><td>Min</td><td><b>{mv[3][0]}</td><td>{mv[3][1]}</td><td>{mv[3][2]}</td><td>{mv[3][3]}</td><td>{mv[3][4]}</td><td>{mv[3][5]}</td></tr>\n'
      f'  <tr><td>Max</td><td><b>{mv[4][0]}</td><td>{mv[4][1]}</td><td>{mv[4][2]}</td><td>{mv[4][3]}</td><td>{mv[4][4]}</td><td>{mv[4][5]}</td></tr>\n'
      f'  <tr><td>RMS</td><td><b>{mv[5][0]}</td><td>{mv[5][1]}</td><td>{mv[5][2]}</td><td>{mv[5][3]}</td><td>{mv[5][4]}</td><td>{mv[5][5]}</td></tr>\n'
      f'  <tr><td rowspan="4">Registration (mm)</td>\n'
      f'      <td>Mean</td><td><b>{mv[6][0]}</td><td>{mv[6][1]}</td><td>{mv[6][2]}</td><td>{mv[6][3]}</td><td>{mv[6][4]}</td><td>{mv[6][5]}</td></tr>\n'
      f'  <tr><td>Min</td><td><b>{mv[7][0]}</td><td>{mv[7][1]}</td><td>{mv[7][2]}</td><td>{mv[7][3]}</td><td>{mv[7][4]}</td><td>{mv[7][5]}</td></tr>\n'
      f'  <tr><td>Max</td><td><b>{mv[8][0]}</td><td>{mv[8][1]}</td><td>{mv[8][2]}</td><td>{mv[8][3]}</td><td>{mv[8][4]}</td><td>{mv[8][5]}</td></tr>\n'
      f'  <tr><td>RMS</td><td><b>{mv[9][0]}</td><td>{mv[9][1]}</td><td>{mv[9][2]}</td><td>{mv[9][3]}</td><td>{mv[9][4]}</td><td>{mv[9][5]}</td></tr>\n'
      f'</table>\n'
      f'</div>\n'
      f'</body>\n'
      f'</html>\n'
      )
    f.close()
    