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
For more information about the module and its usage, please refer to the <a href="https://github.com/Atracsys/SlicerAstmPhantomTest">home page</a>.
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
    self.developerMode = False # remove module developer buttons
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
      self.logic = AstmPhantomTestLogic(self.resourcePath('models/pointer_RAS.stl'),
      self.resourcePath('models/simpPhantom_RAS.stl'), self.resourcePath(''), savePath)

      # Forward some rendering handles to the logic class
      self.logic.mainWidget = slicer.app.layoutManager().threeDWidget('ViewMain')
      self.logic.mainWidget.show()
      self.logic.mainRenderer = self.logic.mainWidget.threeDView().renderWindow().GetRenderers().GetItemAsObject(0)

      self.logic.topWVWidget = slicer.app.layoutManager().threeDWidget('ViewTopWV')
      self.logic.topWVWidget.hide()
      self.logic.topWVRenderer = self.logic.topWVWidget.threeDView().renderWindow().GetRenderers().GetItemAsObject(0)

      self.logic.frontWVWidget = slicer.app.layoutManager().threeDWidget('ViewFrontWV')
      self.logic.frontWVWidget.hide()
      self.logic.frontWVRenderer = self.logic.frontWVWidget.threeDView().renderWindow().GetRenderers().GetItemAsObject(0)

      self.logic.initialize()

      # Display of the simplified phantom to the working volume guidance scenes
      self.logic.workingVolume.simpPhantomModel.GetDisplayNode().VisibilityOff()
      self.logic.workingVolume.simpPhantomModel.GetDisplayNode().AddViewNodeID('vtkMRMLViewNodeTopWV')
      self.logic.workingVolume.simpPhantomModel.GetDisplayNode().AddViewNodeID('vtkMRMLViewNodeFrontWV')
      # Forward models folder path
      self.logic.workingVolume.modelsFolderPath = self.resourcePath('models/')
      self.logic.phantom.modelsFolderPath = self.resourcePath('models/')

      ## Connections

      # These connections ensure that we update parameter node when scene is closed
      self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
      self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

      # UI connections
      self.ui.trackerLineEdit.connect('editingFinished()', self.onTrackerIdChanged)
      self.ui.pointAcqui1frameButton.connect('clicked()', self.onPointAcqui1frameSet)
      self.ui.pointAcquiMeanButton.connect('clicked()', self.onPointAcquiMeanSet)
      self.ui.pointAcquiMedianButton.connect('clicked()', self.onPointAcquiMedianSet)
      self.ui.pointAcquiDurationLineEdit.connect('editingFinished()', self.onPointAcquiDurationChanged)
      self.ui.pointAcquiNumFramesLineEdit.connect('editingFinished()', self.onPointAcquiNumFramesChanged)
      self.ui.operatorLineEdit.connect('editingFinished()', self.onOperatorIdChanged)
      self.ui.movingTolSlider.connect('sliderMoved(int)', self.onMovingTolSliderMoved)
      self.ui.movingTolSlider.connect('sliderReleased()', self.onMovingTolSliderReleased)

      self.ui.testCheckBox1L.connect('stateChanged(int)', self.onTestCheckBox1LChanged)
      self.ui.testCheckBox1R.connect('stateChanged(int)', self.onTestCheckBox1RChanged)
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
      self.ui.resetCamButton.connect('clicked()', self.logic.resetCam)
      self.ui.resetStepButton.connect('clicked()', self.logic.resetStep)
      self.ui.anglesCheckbox.connect('stateChanged(int)', self.logic.anglesCheckboxChanged)
      self.ui.recalibOptionCheckBox.connect('stateChanged(int)', self.logic.setRecalibAtLocation)

      self.ui.hackCalibButton.connect('clicked()', self.hackCalib)
      self.ui.hackCLButton.connect('clicked()', self.hackCL)
      self.ui.hackBLButton.connect('clicked()', self.hackBL)
      self.ui.hackTLButton.connect('clicked()', self.hackTL)
      self.ui.hackLLButton.connect('clicked()', self.hackLL)
      self.ui.hackRLButton.connect('clicked()', self.hackRL)
      self.ui.hackXButton.connect('clicked()', self.logic.skipTest)

      # input validators
      self.durationValidator = qt.QIntValidator(1,10000)
      self.ui.pointAcquiDurationLineEdit.setValidator(self.durationValidator)
      self.numFramesValidator = qt.QIntValidator(1,999)
      self.ui.pointAcquiNumFramesLineEdit.setValidator(self.numFramesValidator)

      # Add observers for custom events
      self.logic.pointer.AddObserver(self.logic.pointer.movingTolChanged,
        self.onMovingTolChangedFromLocation)
      self.logic.phantom.AddObserver(self.logic.phantom.calibStartedEvent,
        self.onCalibratingPhantom)
      self.logic.phantom.AddObserver(self.logic.phantom.firstCalibratedEvent,
        self.onPhantomFirstCalibrated)
      self.logic.phantom.AddObserver(self.logic.phantom.calibratedEvent,
        self.onPhantomCalibrated)
      self.logic.wvTargetsTop.AddObserver(self.logic.wvTargetsTop.targetHitEvent, self.onLocHit)
      self.logic.AddObserver(self.logic.testNamesUpdated, self.onTestNamesUpdated)
      self.logic.AddObserver(self.logic.wvGuidanceStarted, self.onWorkingVolumeGuidanceStarted)
      self.logic.AddObserver(self.logic.locationFinished, self.onLocationFinished)
      self.logic.AddObserver(self.logic.testStarted, self.onTestStarted)
      self.logic.AddObserver(self.logic.testFinished, self.onTestFinished)
      self.logic.AddObserver(self.logic.sessionEndedEvent, self.onSessionEnded)

      # Initialize default values for UI elements
      self.ui.movingTolValue.setText(f'{self.logic.pointer.movingTol:.2f} mm')
      self.onMovingTolChangedFromLocation(self.logic.pointer) # update slider with pointer moving tol default value
      self.ui.resetStepButton.setText("\u2B6F Reset Current Step")
      self.ui.hackCollapsibleButton.setText("\u26d4 dev shortcuts \u26d4")
      self.ui.hackXButton.setText("\u26a1")

      # Parse resource folder for pointer files (ptr/____.txt)
      ptrFiles = [f for f in os.listdir(self.resourcePath('./ptr')) if re.match(r'.*\.txt', f)]
      self.ui.pointerFileSelector.addItems(ptrFiles)
      if len(ptrFiles) > 0:
        self.ui.pointerFileSelector.currentIndexChanged.connect(self.onPointerFileChanged)

      # Parse resource folder for ground truth files (gt/SN____.txt)
      gtFiles = [f for f in os.listdir(self.resourcePath('./gt')) if re.match(r'.*\.txt', f)]
      self.ui.groundTruthFileSelector.addItems(gtFiles)
      if len(gtFiles) > 0:
        self.ui.groundTruthFileSelector.currentIndexChanged.connect(self.onGroundTruthFileChanged)

      # Parse resource folder for working volume files (wv/____.txt)
      wvFiles = [f for f in os.listdir(self.resourcePath('./wv')) if re.match(r'.*\.txt', f)]
      self.ui.workingVolumeFileSelector.addItems(wvFiles)
      if len(wvFiles) > 0:
        self.ui.workingVolumeFileSelector.currentIndexChanged.connect(self.onWorkingVolumeFileChanged)

      # Adding the observer watching out for the new transform node after openigtlink connection
      slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, self.onNodeAdded)

      # Welcome message
      self.messageActor = vtk.vtkCornerAnnotation()
      self.messageActor.GetTextProperty().SetFontSize(200)
      self.messageActor.SetText(2, "Welcome to the ASTM Phantom Test module.\nTo start, make sure that both the pointer and\nthe reference array attached to the phantom\nare visible by the tracker.\n<--")
      self.logic.mainRenderer.AddActor(self.messageActor)

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
    self.ui.pointAcquiDurationLineEdit.enabled = False
    self.ui.pointAcquiMillisecLabel.enabled = False
    self.ui.pointAcquiVerticalLine.enabled = False
    self.ui.pointAcquiMeanButton.enabled = False
    self.ui.pointAcquiMedianButton.enabled = False
    self.ui.pointAcquiNumFramesLineEdit.enabled = False
    self.ui.pointAcquiFramesLabel.enabled = False
    self.ui.hackCalibButton.enabled = True

    self.messageActor.SetText(2, "Phantom calibration:\nPick the target divot with the pointer")
    self.logic.mainRenderer.AddActor(self.messageActor)

  @vtk.calldata_type(vtk.VTK_STRING)
  def onPhantomFirstCalibrated(self, caller, event = None, calldata = None):
    """
    Called when the phantom is first calibrated
    """
    # Enable locations checkboxes
    self.ui.locCheckBoxCL.enabled = self.ui.locCheckBoxCL.checked
    self.ui.locCheckBoxBL.enabled = self.ui.locCheckBoxBL.checked
    self.ui.locCheckBoxTL.enabled = self.ui.locCheckBoxTL.checked
    self.ui.locCheckBoxLL.enabled = self.ui.locCheckBoxLL.checked
    self.ui.locCheckBoxRL.enabled = self.ui.locCheckBoxRL.checked
    # Enable test checkboxes
    self.ui.testCheckBox1L.enabled = True
    self.ui.testCheckBox1R.enabled = True
    self.ui.testCheckBox1.enabled = True
    self.ui.testCheckBox2.enabled = True
    self.ui.testCheckBox3.enabled = True
    self.ui.testCheckBox4.enabled = True
    self.ui.testCheckBox5.enabled = True
    # Disable some parameters in UI
    self.ui.hackCalibButton.enabled = False
    self.ui.operatorLineEdit.enabled = False
    self.ui.recalibOptionCheckBox.enabled = False

  @vtk.calldata_type(vtk.VTK_STRING)
  def onPhantomCalibrated(self, caller, event = None, calldata = None):
    """
    Called when the phantom is calibrated
    """
    self.ui.anglesCheckbox.enabled = True
    self.ui.hackCalibButton.enabled = False
    self.logic.mainRenderer.RemoveActor(self.messageActor)
    # Update moving tolerance
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
        self.ui.locCheckBoxCL.setStyleSheet("#locCheckBoxCL { background-color: rgba(0,255,0,30%); }")
        self.ui.hackCLButton.enabled = False
      if loc == "BL":
        self.ui.locCheckBoxBL.enabled = False
        self.ui.locCheckBoxBL.setStyleSheet("#locCheckBoxBL { background-color: rgba(0,255,0,30%); }")
        self.ui.hackBLButton.enabled = False
      if loc == "TL":
        self.ui.locCheckBoxTL.enabled = False
        self.ui.locCheckBoxTL.setStyleSheet("#locCheckBoxTL { background-color: rgba(0,255,0,30%); }")
        self.ui.hackTLButton.enabled = False
      if loc == "LL":
        self.ui.locCheckBoxLL.enabled = False
        self.ui.locCheckBoxLL.setStyleSheet("#locCheckBoxLL { background-color: rgba(0,255,0,30%); }")
        self.ui.hackLLButton.enabled = False
      if loc == "RL":
        self.ui.locCheckBoxRL.enabled = False
        self.ui.locCheckBoxRL.setStyleSheet("#locCheckBoxRL { background-color: rgba(0,255,0,30%); }")
        self.ui.hackRLButton.enabled = False
  
  @vtk.calldata_type(vtk.VTK_STRING)
  def onLocationFinished(self, caller, event, calldata):
    loc = calldata
    if loc == "CL":
      self.ui.locCheckBoxCL.setStyleSheet("")
    if loc == "BL":
      self.ui.locCheckBoxBL.setStyleSheet("")
    if loc == "TL":
      self.ui.locCheckBoxTL.setStyleSheet("")
    if loc == "LL":
      self.ui.locCheckBoxLL.setStyleSheet("")
    if loc == "RL":
      self.ui.locCheckBoxRL.setStyleSheet("")

  @vtk.calldata_type(vtk.VTK_STRING)
  def onWorkingVolumeGuidanceStarted(self, caller, event = None, calldata = None):
    self.ui.testCheckBox1.enabled = True
    self.ui.testCheckBox1L.enabled = True
    self.ui.testCheckBox1R.enabled = True
    self.ui.testCheckBox2.enabled = True
    self.ui.testCheckBox3.enabled = True
    self.ui.testCheckBox4.enabled = True
    self.ui.testCheckBox5.enabled = True

  @vtk.calldata_type(vtk.VTK_STRING)
  def onTestStarted(self, caller, event, calldata):
    test = calldata
    if test in self.logic.testsToDo: # check but should always be true
      if test == self.logic.tests[0][0]:
        self.ui.testCheckBox1L.enabled = False
        self.ui.testCheckBox1L.setStyleSheet("#testCheckBox1L { background-color: rgba(0,255,0,30%); }")
      if test == self.logic.tests[1][0]:
        self.ui.testCheckBox1R.enabled = False
        self.ui.testCheckBox1R.setStyleSheet("#testCheckBox1R { background-color: rgba(0,255,0,30%); }")
      if test == self.logic.tests[2][0]:
        self.ui.testCheckBox1.enabled = False
        self.ui.testCheckBox1.setStyleSheet("#testCheckBox1 { background-color: rgba(0,255,0,30%); }")
      if test == self.logic.tests[3][0]:
        self.ui.testCheckBox2.enabled = False
        self.ui.testCheckBox2.setStyleSheet("#testCheckBox2 { background-color: rgba(0,255,0,30%); }")
      if test == self.logic.tests[4][0]:
        self.ui.testCheckBox3.enabled = False
        self.ui.testCheckBox3.setStyleSheet("#testCheckBox3 { background-color: rgba(0,255,0,30%); }")
      if test == self.logic.tests[5][0]:
        self.ui.testCheckBox4.enabled = False
        self.ui.testCheckBox4.setStyleSheet("#testCheckBox4 { background-color: rgba(0,255,0,30%); }")
      if test == self.logic.tests[6][0]:
        self.ui.testCheckBox5.enabled = False
        self.ui.testCheckBox5.setStyleSheet("#testCheckBox5 { background-color: rgba(0,255,0,30%); }")

  @vtk.calldata_type(vtk.VTK_STRING)
  def onTestFinished(self, caller, event, calldata):
    test = calldata
    if test == self.logic.tests[0][0]:
      self.ui.testCheckBox1L.setStyleSheet("")
    if test == self.logic.tests[1][0]:
      self.ui.testCheckBox1R.setStyleSheet("")
    if test == self.logic.tests[2][0]:
      self.ui.testCheckBox1.setStyleSheet("")
    if test == self.logic.tests[3][0]:
      self.ui.testCheckBox2.setStyleSheet("")
    if test == self.logic.tests[4][0]:
      self.ui.testCheckBox3.setStyleSheet("")
    if test == self.logic.tests[5][0]:
      self.ui.testCheckBox4.setStyleSheet("")
    if test == self.logic.tests[6][0]:
      self.ui.testCheckBox5.setStyleSheet("")

  @vtk.calldata_type(vtk.VTK_STRING)
  def onSessionEnded(self, caller, event = None, calldata = None):
    self.ui.locCheckBoxCL.enabled = False
    self.ui.locCheckBoxBL.enabled = False
    self.ui.locCheckBoxTL.enabled = False
    self.ui.locCheckBoxLL.enabled = False
    self.ui.locCheckBoxRL.enabled = False
    self.ui.testCheckBox1L.enabled = False
    self.ui.testCheckBox1R.enabled = False
    self.ui.testCheckBox1.enabled = False
    self.ui.testCheckBox2.enabled = False
    self.ui.testCheckBox3.enabled = False
    self.ui.testCheckBox4.enabled = False
    self.ui.testCheckBox5.enabled = False
    self.ui.hackCalibButton.enabled = False
    self.ui.hackCLButton.enabled = False
    self.ui.hackBLButton.enabled = False
    self.ui.hackTLButton.enabled = False
    self.ui.hackLLButton.enabled = False
    self.ui.hackRLButton.enabled = False
    self.ui.recalibOptionCheckBox.enabled = False
    # Display message for session end
    self.messageActor.GetTextProperty().SetColor(0,1,0)
    self.messageActor.GetTextProperty().BoldOn()
    self.messageActor.SetLinearFontScaleFactor(8)
    self.messageActor.SetText(2, "Session done !")
    self.logic.topWVRenderer.AddActor(self.messageActor)

  @vtk.calldata_type(vtk.VTK_STRING)
  def onTestNamesUpdated(self, caller, event, calldata):
    names = ast.literal_eval(calldata)
    self.ui.testCheckBox1L.text = names[0]
    self.ui.testCheckBox1R.text = names[1]
    self.ui.testCheckBox1.text = names[2]
    self.ui.testCheckBox2.text = names[3]
    self.ui.testCheckBox3.text = names[4]
    self.ui.testCheckBox4.text = names[5]
    self.ui.testCheckBox5.text = names[6]

  def onTestCheckBox1LChanged(self, val):
    self.logic.tests[0][1] = val
    if val and self.logic.tests[0][0] not in self.logic.testsToDo:
      self.logic.testsToDo.append(self.logic.tests[0][0])
    if not val and self.logic.tests[0][0] in self.logic.testsToDo:
      self.logic.testsToDo.remove(self.logic.tests[0][0])
  
  def onTestCheckBox1RChanged(self, val):
    self.logic.tests[1][1] = val
    if val and self.logic.tests[1][0] not in self.logic.testsToDo:
      self.logic.testsToDo.append(self.logic.tests[1][0])
    if not val and self.logic.tests[1][0] in self.logic.testsToDo:
      self.logic.testsToDo.remove(self.logic.tests[1][0])
  
  def onTestCheckBox1Changed(self, val):
    self.logic.tests[2][1] = val
    if val and self.logic.tests[2][0] not in self.logic.testsToDo:
      self.logic.testsToDo.append(self.logic.tests[2][0])
    if not val and self.logic.tests[2][0] in self.logic.testsToDo:
      self.logic.testsToDo.remove(self.logic.tests[2][0])
  
  def onTestCheckBox2Changed(self, val):
    self.logic.tests[3][1] = val
    if val and self.logic.tests[3][0] not in self.logic.testsToDo:
      self.logic.testsToDo.append(self.logic.tests[3][0])
    if not val and self.logic.tests[3][0] in self.logic.testsToDo:
      self.logic.testsToDo.remove(self.logic.tests[3][0])
  
  def onTestCheckBox3Changed(self, val):
    self.logic.tests[4][1] = val
    if val and self.logic.tests[4][0] not in self.logic.testsToDo:
      self.logic.testsToDo.append(self.logic.tests[4][0])
    if not val and self.logic.tests[4][0] in self.logic.testsToDo:
      self.logic.testsToDo.remove(self.logic.tests[4][0])
  
  def onTestCheckBox4Changed(self, val):
    self.logic.tests[5][1] = val
    if val and self.logic.tests[5][0] not in self.logic.testsToDo:
      self.logic.testsToDo.append(self.logic.tests[5][0])
    if not val and self.logic.tests[5][0] in self.logic.testsToDo:
      self.logic.testsToDo.remove(self.logic.tests[5][0])
  
  def onTestCheckBox5Changed(self, val):
    self.logic.tests[6][1] = val
    if val and self.logic.tests[6][0] not in self.logic.testsToDo:
      self.logic.testsToDo.append(self.logic.tests[6][0])
    if not val and self.logic.tests[6][0] in self.logic.testsToDo:
      self.logic.testsToDo.remove(self.logic.tests[6][0])
  
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
      self.logic.operatorId = opId
      # Checking for dev
      pw = '8ee930e3474f1b9a4a0d7524f3527b93f1ff2e4fa89a385f1ede01a15d7cc9e4'
      salt = '68835c9b8f744414b1e1d2f262e7a911'
      if pw == hashlib.sha256(salt.encode() + self.logic.operatorId.encode()).hexdigest():
        logging.info("----- Oh, it's you! Welcome back, Sir! -----")
        self.ui.hackCollapsibleButton.collapsed = False
        self.ui.hackCollapsibleButton.enabled = True
        self.ui.hackCalibButton.enabled = True
        self.ui.resetCamButton.enabled = True
        self.ui.resetStepButton.enabled = True
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
        # Enable point acquisition parametrization
        self.ui.pointAcqui1frameButton.enabled = True
        self.ui.pointAcquiDurationLineEdit.enabled = True
        self.ui.pointAcquiMillisecLabel.enabled = True
        self.ui.pointAcquiVerticalLine.enabled = True
        self.ui.pointAcquiMeanButton.enabled = True
        self.ui.pointAcquiMedianButton.enabled = True
        self.ui.pointAcquiDurationLineEdit.text = str(self.logic.pointer.timerDuration)
        self.ui.pointAcquiNumFramesLineEdit.text = str(self.logic.pointer.numFrames)
        # Enable other options
        self.ui.operatorLineEdit.enabled = True
        self.ui.recalibOptionCheckBox.enabled = True

    self.logic.trackerId = tk
    logging.info(f"Tracker Serial Number: {self.logic.trackerId}")

  def onPointAcqui1frameSet(self):
    self.ui.pointAcquiDurationLineEdit.enabled = True
    self.ui.pointAcquiMillisecLabel.enabled = True
    self.ui.pointAcquiNumFramesLineEdit.enabled = False
    self.ui.pointAcquiFramesLabel.enabled = False
    self.logic.pointer.acquiMode = 0
    logging.info(f"Point acquisition set to 1-frame from a {self.logic.pointer.timerDuration}ms point acquisition")
  
  def onPointAcquiMeanSet(self):
    self.ui.pointAcquiDurationLineEdit.enabled = False
    self.ui.pointAcquiMillisecLabel.enabled = False
    self.ui.pointAcquiNumFramesLineEdit.enabled = True
    self.ui.pointAcquiFramesLabel.enabled = True
    self.logic.pointer.acquiMode = 1
    logging.info(f"Point acquisition set to MEAN across {self.logic.pointer.numFrames} frames")

  def onPointAcquiMedianSet(self):
    self.ui.pointAcquiDurationLineEdit.enabled = False
    self.ui.pointAcquiMillisecLabel.enabled = False
    self.ui.pointAcquiNumFramesLineEdit.enabled = True
    self.ui.pointAcquiFramesLabel.enabled = True
    self.logic.pointer.acquiMode = 2
    logging.info(f"Point acquisition set to MEDIAN across {self.logic.pointer.numFrames} frames")

  def onPointAcquiDurationChanged(self):
    val = int(self.ui.pointAcquiDurationLineEdit.text)
    if val != self.logic.pointer.timerDuration:
      self.logic.pointer.timerDuration = val
      logging.info(f"Timer duration for point acquisition set to {self.logic.pointer.timerDuration}ms")

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
        self.logic.mainRenderer.RemoveActor(self.messageActor)
        self.ui.trackerLineEdit.enabled = True
        self.ui.trackerLineEdit.setFocus()
        # Selectors call since combobox already selected first item in each
        self.onPointerFileChanged()
        self.onGroundTruthFileChanged()
        self.onWorkingVolumeFileChanged()
        self.logic.process(self.ptrRefNode, self.refNode, self.ptrNode)

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

  def __init__(self, pointerModelPath, simpPhantomPath, resourcePath, savePath):
    """
    Called when the logic class is instantiated. Can be used for initializing member variables.
    """    
    ScriptedLoadableModuleLogic.__init__(self)
    self.pointerModelPath = pointerModelPath
    self.simpPhantomPath = simpPhantomPath
    self.resourcePath = resourcePath
    self.savePath = savePath
    self.testNamesUpdated = vtk.vtkCommand.UserEvent + 1
    self.wvGuidanceStarted = vtk.vtkCommand.UserEvent + 2
    self.locationFinished = vtk.vtkCommand.UserEvent + 3
    self.testStarted = vtk.vtkCommand.UserEvent + 4
    self.testFinished = vtk.vtkCommand.UserEvent + 5
    self.sessionEndedEvent = vtk.vtkCommand.UserEvent + 6

    # If rendering is used, 3D views and renderers are made available by the widget class
    self.mainWidget = None
    self.mainRenderer = None
    self.topWVWidget = None
    self.topWVRenderer = None
    self.frontWVWidget = None
    self.frontWVRenderer = None

    # Loading some sounds
    self.sounds = {}
    self.sounds["plop"] = qt.QSound(self.resourcePath + "sounds/plop.wav")
    self.sounds["done"] = qt.QSound(self.resourcePath + "sounds/done.wav")
    self.sounds["danger"] = qt.QSound(self.resourcePath + "sounds/danger.wav")
    self.sounds["error"] = qt.QSound(self.resourcePath + "sounds/error.wav")
    self.sounds["touchdown"] = qt.QSound(self.resourcePath + "sounds/touchdown.wav")

  def initialize(self):
    self.operatorId = None
    self.trackerId = None
    # Phantom
    self.phantom = Phantom(self.mainRenderer)
    self.calibratingPhantom = False
    # Pointer
    self.pointer = Pointer()
    self.pointer.maxTilt = 50
    if self.mainRenderer is not None: # if rendering is enabled
      self.pointer.readModel(self.pointerModelPath)
    # Targets
    self.targets = Targets(self.mainRenderer)
    self.targetsDone = Targets(self.mainRenderer)
    # Working volume
    self.workingVolume = WorkingVolume(self.topWVRenderer, self.frontWVRenderer)
    self.workingVolume.readSimpPhantomModel(self.simpPhantomPath)
    self.wvTargetsTop = Targets(self.workingVolume.renTop)
    self.wvTargetsFront = Targets(self.workingVolume.renFront)
    self.curLoc = "INIT" # null location in the working volume
    self.wvGuidanceActive = False
    # Tests
    self.tests = [[]] # initialization
    self.testsToDo = []
    self.runningTest = False
    # Angle annotation
    self.dispAngles = False
    self.angleAnn = vtk.vtkCornerAnnotation()
    self.angleAnn.GetTextProperty().SetFontSize(180)
    self.angleAnn.SetLinearFontScaleFactor(18)
    self.angleAnn.GetTextProperty().SetColor(1,0,0)
    self.angleAnn.GetTextProperty().BoldOn()
    self.angleAnn.GetTextProperty().ShadowOn()

    # Create all the tests (even if they might not be used)
    #   Single point accuracy and precision tests
    #   (0 = extreme left, 1 = extreme right, 2 = normal)
    self.singlePointMeasurements = [SinglePointMeasurement(0), SinglePointMeasurement(1), SinglePointMeasurement(2)]
    self.singleAnn = None
    #   Precision during rotation tests (0 = roll, 1 = pitch, 2 = yaw)
    self.rotMeasurements = [RotationMeasurement(0), RotationMeasurement(1), RotationMeasurement(2)]
    #   Distance accuracy test
    self.distMeasurement = DistMeasurement()
    self.recalibAtLocation = True

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
    self.pointer.model.GetDisplayNode().VisibilityOff()
    # assign reference transform to simp phantom
    self.workingVolume.setTransfoNode(self.refTransfoNode)

    # connections between the targets object (empty for now) and the pointer
    self.pointer.AddObserver(self.pointer.stoppedEvent, self.targets.onTargetFocus)
    self.pointer.AddObserver(self.pointer.acquiProgEvent, self.targets.onTargetIn)
    self.pointer.AddObserver(self.pointer.staticFailEvent, self.targets.onTargetOut)
    self.pointer.AddObserver(self.pointer.acquiDoneEvent, self.targets.onTargetDone)
    self.pointer.AddObserver(self.pointer.acquiDoneOutEvent, self.targets.onTargetDoneOut)

    # This list stores the tests order and if they are enabled
    self.tests = [['singleL',1], ['singleR',1], ['single',1], ['yaw',1], ['pitch',1], ['roll',1], ['dist',1]]
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
      if self.calibratingPhantom:
        self.placeCamWrtPhantom(False)
      elif len(self.testsToDo) == 0:
        self.placeCamWrtPhantom(False)
      elif self.testsToDo[0] in ['roll', 'pitch', 'yaw']:
        self.placeCamWrtPhantom(True)
      else:
        self.placeCamWrtPhantom(False)
    elif self.topWVWidget.isVisible() and self.frontWVWidget.isVisible():
      self.workingVolume.resetCameras()

  def resetStep(self):
    if not self.wvGuidanceActive:
      self.resetStepMsgBox = qt.QMessageBox()
      self.resetStepMsgBox.setText("Reset current step ?")
      self.resetStepMsgBox.setIcon(qt.QMessageBox().Warning)
      self.resetStepMsgBox.setStandardButtons(qt.QMessageBox().Yes | qt.QMessageBox().No)
      self.resetStepMsgBox.setDefaultButton(qt.QMessageBox().No)
      ret = self.resetStepMsgBox.exec()
      if ret == qt.QMessageBox().Yes:
        logging.info("***** Reset current step *****")
        if self.calibratingPhantom:
          self.restartPhantomCalibration()
        if self.runningTest:
          self.stopCurrentTest()
          self.startCurrentTest()
  
  @vtk.calldata_type(vtk.VTK_STRING)
  def onPointerAnglesChanged(self, caller, event=None, calldata=None):
      cd = ast.literal_eval(calldata)
      self.angleAnn.SetText(2, f"Roll={cd[0]:.1f}\nPitch={cd[1]:.1f}\nYaw={cd[2]:.1f}")
  
  @vtk.calldata_type(vtk.VTK_STRING)
  def onPointerTrackingChanged(self, caller, event=None, calldata=None):
    if self.mainRenderer:
      if self.pointer.tracking:
        self.mainRenderer.AddActor(self.angleAnn)
      else:
        self.mainRenderer.RemoveActor(self.angleAnn)
  
  def anglesCheckboxChanged(self, val):
    if not self.dispAngles and val:
      self.dispAngles = True
      if self.mainRenderer:
        self.pointer.emitAngles = True
        self.anglesDispObserver = self.pointer.AddObserver(self.pointer.anglesChangedEvent,
          self.onPointerAnglesChanged)
        self.pointerTrackingStartedObserver = self.pointer.AddObserver(self.pointer.trackingStartedEvent,
          self.onPointerTrackingChanged)
        self.pointerTrackingStoppedObserver = self.pointer.AddObserver(self.pointer.trackingStoppedEvent,
          self.onPointerTrackingChanged)
        if self.pointer.tracking:
          self.mainRenderer.AddActor(self.angleAnn)
    elif self.dispAngles and not val:
      self.dispAngles = False
      if self.mainRenderer:
        self.pointer.emitAngles = False
        self.mainRenderer.RemoveActor(self.angleAnn)
        self.pointer.RemoveObserver(self.anglesDispObserver)
        self.pointer.RemoveObserver(self.pointerTrackingStartedObserver)
        self.pointer.RemoveObserver(self.pointerTrackingStoppedObserver)
  
  def setRecalibAtLocation(self, val):
    self.recalibAtLocation = val

  def placeCamWrtPhantom(self, pointer = False):
    def placeCam(self, camPos, camDir):
      # Origin O, X and Y are assumed to be the three first calib labels respectively
      O = self.phantom.divPos(self.phantom.calibLabels[0])
      X = self.phantom.divPos(self.phantom.calibLabels[1])
      Y = self.phantom.divPos(self.phantom.calibLabels[2])
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
      return True
    else:
      return False

  # --------------------- Calibration ---------------------
  def startPhantomCalibration(self):
    logging.info('Calibration started')
    # reset phantom calib transfo
    identityMat = vtk.vtkMatrix4x4()
    self.phantom.calibTransfoNode.SetMatrixTransformToParent(identityMat)
    # make sure the correct scene is rendered
    if self.mainWidget and self.topWVWidget and self.frontWVWidget:
      self.mainWidget.show()
      self.topWVWidget.hide()
      self.frontWVWidget.hide()
    # if the phantom was already calibrated
    if self.phantom.calibrated or len(self.phantom.calGtPts) > 0: # should be the same
      self.phantom.resetCalib() # initialize calibrated points for the current location
      self.pointer.model.GetDisplayNode().VisibilityOff()
    self.phantom.model.GetDisplayNode().VisibilityOn()

    # if another acquisition was already started
    self.pointer.timer.stop()
    self.targets.RemoveAllObservers()
    self.targets.removeAllTargets()  # making sure targets is empty

    # Create all targets but hidden
    for l in self.phantom.calibLabels:
      self.targets.addTarget(l, self.phantom.divPos(l), False)
    # Display first target
    self.targets.targets[self.phantom.calibLabels[0]].visible(True)

    self.calibObs1 = self.targets.AddObserver(self.targets.targetHitEvent, self.onCalibrationPointCheck)
    self.calibObs2 = self.targets.AddObserver(self.targets.targetDoneEvent, self.onCalibrationPointDone)
    self.calibObs3 = self.targets.AddObserver(self.targets.targetDoneOutEvent, self.onCalibrationPointDoneOut)

    self.calibratingPhantom = True
    self.resetCam()
    self.phantom.InvokeEvent(self.phantom.calibStartedEvent)

  @vtk.calldata_type(vtk.VTK_STRING)
  def onCalibrationPointCheck(self, caller, event, calldata):
    cd = ast.literal_eval(calldata)
    valid = True
    for k in self.phantom.calGtPts:
      theoDist = Dist(self.phantom.gtPts[k], self.phantom.gtPts[cd[0]])
      dist = Dist(self.phantom.calGtPts[k], cd[1:4])
      err = abs(theoDist - dist)
      if err > 5.0: #mm
        logging.info(f'   Invalid distance [{k}, {int(cd[0])}] (err = {err:.2f})')
        valid = False
    if valid:
      self.pointer.startAcquiring(caller)

  @vtk.calldata_type(vtk.VTK_STRING)
  def onCalibrationPointDone(self, caller, event, calldata):
    # play sound
    self.sounds["plop"].play()
    cd = ast.literal_eval(calldata)  # parse [id, px, py, pz]
    if not isinstance(cd, list):
      cd = [cd]
    if cd[0] in self.phantom.calibLabels:
      self.phantom.calGtPts[cd[0]] = np.array(cd[1:4])
      logging.info(f'   Divot #{cd[0]} calibrated at {np.around(cd[1:4],2).tolist()}')

  @vtk.calldata_type(vtk.VTK_STRING)
  def onCalibrationPointDoneOut(self, caller, event, calldata):
    cd = ast.literal_eval(calldata)  # parse id
    if not isinstance(cd, list):
      cd = [cd]
    self.targets.removeTarget(cd[0])

    if self.phantom.canBeCalibrated():
      self.stopPhantomCalibration()
      self.finishPhantomCalibration()
  
  def stopPhantomCalibration(self):
    self.targets.RemoveObserver(self.calibObs1)
    self.targets.RemoveObserver(self.calibObs2)
    self.targets.RemoveObserver(self.calibObs3)
    self.calibratingPhantom = False

  def restartPhantomCalibration(self):
    self.stopPhantomCalibration()
    self.startPhantomCalibration()

  def finishPhantomCalibration(self):
    self.phantom.calibrate()
    slicer.app.processEvents() # make sure that
    self.phantom.allCalGtPts[self.curLoc] = self.phantom.calGtPts
    # Add offset to simp phantom position (in ref marker referential!)
    # so that the central divot hits the wv targets
    self.workingVolume.offset = self.phantom.calGtPts[self.phantom.centralDivot]
    # Update the calibration transform of simp phantom with the one from phantom
    self.workingVolume.calibTransfoNode.CopyContent(self.phantom.calibTransfoNode)    
    
    # Full reset of all measurements if first calibration
    if self.phantom.firstCalibration:
      if self.singlePointMeasurements:
        for spm in self.singlePointMeasurements:
          spm.fullReset(self.phantom.calGtPts, self.phantom.centralDivot)
      if self.distMeasurement:
        self.distMeasurement.fullReset(self.phantom.calGtPts, self.phantom.seq)
      # but also reset rotation measurements then
      for r in self.rotMeasurements:
        r.fullReset()

      self.phantom.firstCalibration = False
      self.startWorkingVolumeGuidance()
    else:
      # new calib => new calibrated ground truth for the accuracy measurements
      if self.singlePointMeasurements:
        for spm in self.singlePointMeasurements:
          spm.setGtPts(self.phantom.calGtPts)
      if self.distMeasurement:
        self.distMeasurement.setGtPts(self.phantom.calGtPts)

      # Start the first test
      self.startCurrentTest()

  # --------------------- Working volume guidance ---------------------
  def startWorkingVolumeGuidance(self):
    logging.info('Starting working volume guidance')
    self.wvGuidanceActive = True
    # make sure the correct scene is rendered
    if self.mainWidget and self.topWVWidget and self.frontWVWidget:
      self.mainWidget.hide()
      self.topWVWidget.show()
      self.frontWVWidget.show()
      self.workingVolume.simpPhantomModel.GetDisplayNode().VisibilityOn()
      self.pointer.model.GetDisplayNode().VisibilityOff()

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
      self.InvokeEvent(self.wvGuidanceStarted)
    else:
      logging.info('====== All done, good job ^_^ ======')
      self.EndSession()

  @vtk.calldata_type(vtk.VTK_STRING)
  def stopWorkingVolumeGuidance(self, caller, event, calldata):
    cd = ast.literal_eval(calldata)
    prevLoc = self.curLoc
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
    self.pointer.setMovingTolerance(self.workingVolume.movingToleranceFromDepth(np.linalg.norm(cd[1:4])))

    # Initialize tests (must be done before removing target)
    self.initTests(self.curLoc)
    # Remove target
    self.removeWorkingVolumeTarget(self.curLoc)
    self.wvGuidanceActive = False

    # If no test enabled, loop back to working volume guidance
    if not len(self.testsToDo) > 0:
      self.InvokeEvent(self.locationFinished, self.curLoc)
      self.startWorkingVolumeGuidance()
    # If recalib at location is enabled, start the phantom calibration
    elif self.recalibAtLocation:
      self.startPhantomCalibration()
    # otherwise start the first test
    else:
      self.startCurrentTest()

  # ---------------------------- Tests Control -----------------------------
  def initTests(self, loc):
    # Initialize tests todo list
    self.testsToDo = []
    for t in self.tests:
      if t[1]:
        self.testsToDo.append(t[0])
    # Reset tests
    self.singlePointMeasurements[0].curLoc = loc
    self.singlePointMeasurements[0].reset()
    self.singlePointMeasurements[1].curLoc = loc
    self.singlePointMeasurements[1].reset()
    self.singlePointMeasurements[2].curLoc = loc
    self.singlePointMeasurements[2].reset()
    self.rotMeasurements[0].curLoc = loc
    self.rotMeasurements[0].reset()
    self.rotMeasurements[1].curLoc = loc
    self.rotMeasurements[1].reset()
    self.rotMeasurements[2].curLoc = loc
    self.rotMeasurements[2].reset()
    self.distMeasurement.curLoc = loc
    self.distMeasurement.reset(self.phantom.seq)

  def startCurrentTest(self):
    if len(self.testsToDo) == 0:
      self.InvokeEvent(self.locationFinished, self.curLoc)
      self.startWorkingVolumeGuidance()
    else:
      self.pointer.model.GetDisplayNode().VisibilityOn()
      self.InvokeEvent(self.testStarted, self.testsToDo[0])
      if self.testsToDo[0] == 'singleL':
        self.startSinglePtTest(0)
      if self.testsToDo[0] == 'singleR':
        self.startSinglePtTest(1)
      if self.testsToDo[0] == 'single':
        self.startSinglePtTest(2)
      if self.testsToDo[0] == 'roll':
        self.startRotationTest(0)
      if self.testsToDo[0] == 'pitch':
        self.startRotationTest(1)
      if self.testsToDo[0] == 'yaw':
        self.startRotationTest(2)
      if self.testsToDo[0] == 'dist':
        self.startDistTest()

  def startNextTest(self):
    self.InvokeEvent(self.testFinished, self.testsToDo[0])
    self.testsToDo.pop(0) # remove the test
    self.startCurrentTest()
  
  def stopCurrentTest(self):
    if self.runningTest and len(self.testsToDo) > 0:
      if self.testsToDo[0] in ['singleL', 'singleR', 'single']:
        self.stopSinglePtTest()
      if self.testsToDo[0] in ['roll', 'pitch', 'yaw']:
        self.stopRotationTest()
      if self.testsToDo[0] == 'dist':
        self.stopDistTest()

  # /!\ this function is only to be used for debugging /!\
  def skipTest(self):
      self.stopCurrentTest()
      self.startNextTest()

  # ---------------------------- Single Point Test -----------------------------
  def startSinglePtTest(self, i):
    self.curSingMeas = self.singlePointMeasurements[i]
    logging.info(f'***** [{self.curLoc}] {self.curSingMeas.refOriName} Single Point Test Start*****')
    self.curSingMeas.reset() # reset again, as it could be from a step restart
    self.curSingMeas.acquiNumMax = 20
    if not self.singleAnn:
      self.singleAnn = vtk.vtkCornerAnnotation()
      self.singleAnn.GetTextProperty().SetFontSize(180)
      self.singleAnn.SetLinearFontScaleFactor(20)
      self.singleAnn.GetTextProperty().SetColor(1,0,0)
      self.singleAnn.GetTextProperty().BoldOn()
      self.singleAnn.GetTextProperty().ShadowOn()
    self.mainRenderer.AddActor(self.singleAnn)

    self.targets.proxiDetect = True
    self.test1Obs1 = self.targets.AddObserver(self.targets.targetHitEvent, self.pointer.startAcquiring)
    self.test1Obs2 = self.targets.AddObserver(self.targets.targetDoneEvent, self.onSingPtMeasTargetDone)
    self.test1Obs3 = self.targets.AddObserver(self.targets.targetDoneOutEvent, self.onSingPtMeasTargetDoneOut)

    annTxt = f'{self.curSingMeas.refOriName}\n{self.curSingMeas.acquiNum}/{self.curSingMeas.acquiNumMax}'
    self.singleAnn.SetText(3, annTxt) # 3 = top right
    self.singPtMeasNext()
    self.runningTest = True
    self.resetCam()

  def singPtMeasNext(self):
    if self.curSingMeas.acquiNum < self.curSingMeas.acquiNumMax:
      gtpos = self.phantom.divPos(self.curSingMeas.divot)
      self.targets.addTarget(self.curSingMeas.divot, gtpos, True)
    else:
      # play sound
      self.sounds["done"].play()
      self.finishSinglePtTest()

  @vtk.calldata_type(vtk.VTK_STRING)
  def onSingPtMeasTargetDone(self, caller, event, calldata):
    cd = ast.literal_eval(calldata)
    lblHit = int(cd[0])
    pos = np.array(cd[1:4])
    if lblHit == self.phantom.centralDivot:  # just a verification
      self.curSingMeas.onDivDone(pos)
      # play sound
      self.sounds["plop"].play()
      annTxt = f'{self.curSingMeas.refOriName}\n{self.curSingMeas.acquiNum}/{self.curSingMeas.acquiNumMax}'
      self.singleAnn.SetText(3, annTxt) # 3 = top right

  @vtk.calldata_type(vtk.VTK_STRING)
  def onSingPtMeasTargetDoneOut(self, caller, event, calldata):
    self.targets.removeTarget(self.curSingMeas.divot)
    # display the next divot
    self.singPtMeasNext()

  def stopSinglePtTest(self):
    logging.info(f'_____ [{self.curLoc}] Single Point Test Stop _____')
    if self.mainRenderer:
      self.mainRenderer.RemoveActor(self.singleAnn)
    self.targets.proxiDetect = False
    self.targets.removeAllTargets()
    self.targets.RemoveObserver(self.test1Obs1)
    self.targets.RemoveObserver(self.test1Obs2)
    self.targets.RemoveObserver(self.test1Obs3)
    self.runningTest = False

  def finishSinglePtTest(self):
    logging.info(f'----- [{self.curLoc}] Single Point Test Finished -----')
    self.stopSinglePtTest()
    self.startNextTest()

  # ---------------------------- Rotation Tests -----------------------------
  def startRotationTest(self, i):
    self.curRotMeas = self.rotMeasurements[i]
    self.curRotAxis = self.curRotMeas.rotAxis
    self.curRotAxisName = self.curRotMeas.rotAxisName
    logging.info(f'***** [{self.curLoc}] {self.curRotAxisName} Rotation Test Start *****')
    self.curRotMeas.reset() # reset again, as it could be from a step restart
    # if base position not defined by Single Point Test (with normal orientation),
    # use our other best estimate of it, which comes from the calibration
    if self.singlePointMeasurements[2].avgPos is not None:
      self.curRotMeas.basePos = self.singlePointMeasurements[2].avgPos
      logging.info(f'Using average position from Single Point Test [{self.singlePointMeasurements[2].refOriName}] ({self.curRotMeas.basePos}) as our base position')
    else:
      self.curRotMeas.basePos = self.phantom.calGtPts[self.phantom.centralDivot]
      logging.info(f'Using calibrated central divot ({self.curRotMeas.basePos}) as our base position')

    # if enabled, disable permanent angles display but stores its previous value
    self.prevDispAngles = self.dispAngles
    self.anglesCheckboxChanged(0)

    self.targets.proxiDetect = True
    self.rotTestObs1 = self.targets.AddObserver(self.targets.targetHitEvent,
      self.onRotMeasTargetHit)
    self.rotTestObs2 = self.targets.AddObserver(self.targets.targetOutEvent,
      self.onRotMeasTargetOut)
    self.rotTestObs3 = None
    self.rotTestObs4 = None
    self.rotTestObs5 = None
    div = self.singlePointMeasurements[0].divot # use same central divot as Single Point Test 
    self.targets.addTarget(div, self.phantom.divPos(div), True)

    self.rotTestAcquiring = False
    self.runningTest = True
    self.resetCam()

  @vtk.calldata_type(vtk.VTK_STRING)
  def onRotMeasTargetHit(self, caller, event = None, calldata = None):
    self.pointer.staticConstraint = True
    self.pointer.emitAngles = True
    self.rotTestObs3 = self.pointer.AddObserver(self.pointer.anglesChangedEvent,
      self.onRotPointerAnglesChanged)
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
  def onRotPointerAnglesChanged(self, caller, event=None, calldata=None):
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
      self.finishRotationTest()

  def stopRotationTest(self):
    logging.info(f'_____ [{self.curLoc}] {self.curRotAxisName} Rotation Test Stop _____')
    self.onRotMeasTargetOut(self) # stop monitoring tracking and angles
    self.targets.proxiDetect = False
    self.targets.removeAllTargets()
    self.targets.RemoveObserver(self.rotTestObs1)
    self.targets.RemoveObserver(self.rotTestObs2)
    self.curRotMeas.updateStats()
    self.runningTest = False
    
    # if permanent angles display was previously enabled, re-enable it
    if self.prevDispAngles:
      self.anglesCheckboxChanged(1)

  def finishRotationTest(self):
    logging.info(f'----- [{self.curLoc}] {self.curRotAxisName} Rotation Test Finished -----')
    self.stopRotationTest()
    self.startNextTest()

  # ---------------------------- Multi-point Test -----------------------------
  def startDistTest(self):
    logging.info(f'***** [{self.curLoc}] Multi-point Test Start *****')
    self.distMeasurement.reset(self.phantom.seq) # reset again, as it could be from a step restart
    # Manage targets
    self.targets.proxiDetect = True
    self.targets.AddObserver(self.targets.targetHitEvent, self.pointer.startAcquiring)
    self.targets.AddObserver(self.targets.targetDoneEvent, self.onDistMeasTargetDone)
    self.targets.AddObserver(self.targets.targetDoneOutEvent, self.onDistMeasTargetDoneOut)
    
    self.distMeasNextDiv()
    self.runningTest = True
    self.resetCam()

  def distMeasNextDiv(self):
    if len(self.distMeasurement.divotsToDo) > 0:
      self.distMeasurement.currLbl = self.distMeasurement.divotsToDo[0]
      gtpos = self.phantom.divPos(self.distMeasurement.currLbl)
      self.targets.addTarget(self.distMeasurement.currLbl, gtpos, True)
    else:
      # play sound
      self.sounds["done"].play()
      self.finishDistTest()

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
    logging.info(f'_____ [{self.curLoc}] Multi-point Test Stop _____')
    self.targets.proxiDetect = False
    self.targets.removeAllTargets()
    self.targets.RemoveAllObservers()
    self.targetsDone.removeAllTargets()
    self.targetsDone.RemoveAllObservers()
    self.runningTest = False

  def finishDistTest(self):
    logging.info(f'----- [{self.curLoc}] Multi-point Test Finished -----')
    self.stopDistTest()
    self.startNextTest()

  # -------------------------------------------------------------------
  def EndSession(self):
    self.InvokeEvent(self.sessionEndedEvent)

    # All data serialization
    dts = self.startTime.strftime("%Y.%m.%d_%H.%M.%S")
    jsonPath =  self.savePath + f"/AstmPhantomTest_data_{dts}.json"
    htmlPath = self.savePath + f"/AstmPhantomTest_report_{dts}.html"
    self.endTime = datetime.now()
    td = self.endTime - self.startTime # time delta
    durStr = f"{td.days*24+td.seconds//3600}h{td.seconds%3600//60}min{td.seconds%60}s"
    if self.pointer.acquiMode == 0:
      pointAcquiMode = f"1-frame ({self.pointer.timerDuration}ms)"
    elif self.pointer.acquiMode == 1:
      pointAcquiMode = f"Mean ({self.pointer.numFrames} frames)"
    elif self.pointer.acquiMode == 2:
      pointAcquiMode = f"Median ({self.pointer.numFrames} frames)"
    else:
      pointAcquiMode = "unknown"

    if self.recalibAtLocation:
      recalibAtLocation_str = "Yes"
    else:
      recalibAtLocation_str = "No"

    obj = json.dumps({"Tracker Serial Number": self.trackerId,
      "Pointer": self.pointer.id,
      "Working Volume": self.workingVolume.id,
      "Phantom": self.phantom.id,
      "Operator": self.operatorId,
      "Start date_time": dts,
      "Duration": durStr,
      "Central Divot": self.phantom.centralDivot,
      "Point acquisition": pointAcquiMode,
      "Recalibration at each location": recalibAtLocation_str,
      "Calibrated Ground Truth": self.phantom.allCalGtPts,
      f"Single Point Measurements [{self.singlePointMeasurements[0].refOriName}]": self.singlePointMeasurements[0].measurements,
      f"Single Point Measurements [{self.singlePointMeasurements[1].refOriName}]": self.singlePointMeasurements[1].measurements,
      f"Single Point Measurements [{self.singlePointMeasurements[2].refOriName}]": self.singlePointMeasurements[2].measurements,
      f"{self.rotMeasurements[0].rotAxisName} Rotation Measurements": self.rotMeasurements[0].measurements,
      f"{self.rotMeasurements[1].rotAxisName} Rotation Measurements": self.rotMeasurements[1].measurements,
      f"{self.rotMeasurements[2].rotAxisName} Rotation Measurements": self.rotMeasurements[2].measurements,
      "Multi-point Measurements": self.distMeasurement.measurements},
      indent = 2,
      cls=NumpyEncoder) # important to use the custom class to handle nd-array serialization
    with open(jsonPath, 'w') as jsonFile:
      logging.info(f'Writing all measurements in {jsonPath}')
      jsonFile.write(obj)
      jsonFile.close()

    # Generating report in HTML
    # Stack all values
    locations = ["CL", "BL", "TL", "LL", "RL"] # match html order
    def lookup(d, k, locs): # look up key k in dict d at locations locs
      logging.info(f"d:{d}, k:{k}, locs:{locs}")
      lst = []
      for l in locs:
        if l in d:
          if d[l] is not None:
            if k in d[l]:
              if isinstance(d[l][k], float):
                lst.append(round(d[l][k],2)) # if float, round to 2 decimal places
              else:
                lst.append(d[l][k])
              continue
          # skipped
          lst.append("x")
          continue
        # disabled
        lst.append("-")
      return lst

    s0v = [lookup(self.singlePointMeasurements[0].accuracyStats,"num", locations),
        lookup(self.singlePointMeasurements[0].accuracyStats,"avg err", locations),
        lookup(self.singlePointMeasurements[0].accuracyStats,"max", locations),
        lookup(self.singlePointMeasurements[0].precisionStats,"span", locations),
        lookup(self.singlePointMeasurements[0].precisionStats,"rms", locations)]
    s1v = [lookup(self.singlePointMeasurements[1].accuracyStats,"num", locations),
        lookup(self.singlePointMeasurements[1].accuracyStats,"avg err", locations),
        lookup(self.singlePointMeasurements[1].accuracyStats,"max", locations),
        lookup(self.singlePointMeasurements[1].precisionStats,"span", locations),
        lookup(self.singlePointMeasurements[1].precisionStats,"rms", locations)]
    s2v = [lookup(self.singlePointMeasurements[2].accuracyStats,"num", locations),
        lookup(self.singlePointMeasurements[2].accuracyStats,"avg err", locations),
        lookup(self.singlePointMeasurements[2].accuracyStats,"max", locations),
        lookup(self.singlePointMeasurements[2].precisionStats,"span", locations),
        lookup(self.singlePointMeasurements[2].precisionStats,"rms", locations)]
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

    with open(htmlPath, 'w') as htmlFile:
      logging.info(f'Writing report in {htmlPath}')
      htmlFile.write(
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
        f'  <tr><td>Recalib at each location</td><td>{self.recalibAtLocation}</td></tr>\n'
        f'</table>\n'
        f'\n'
        f'<h3>Single Point Accuracy and Precision Test</h3>\n'
        f'This test measures the accuracy and precision of single point acquisition by repeatedly picking the central divot. The number of measurements is reported in the table below.<br>\n'
        f'For accuracy, the errors are the vectors from the corresponding reference point (central divot) to each measurement. The accuracy mean is the length of the average of these vectors. The accuracy max is the length of the longest vector.<br>\n'
        f'For precision, the maximum distance of between two measurements (span) is reported. Also, the deviations are calculated as the distances of all the measurements from their average. Calculated as such, the Root Mean Square (RMS) of the deviations equates their standard deviation and is reported.\n'
        f'<p>\n'
        f'At each location, the single point test is to be performed with three different phantom orientations: normal, extremes to the left and to the right. The normal orientation is with the phantom rotated such that the attached reference element is optimally located by the tracker. The two extreme orientations correspond to the most extreme left and right rotations of the phantom while maintaining tracking of the attached reference element.\n'
        f'\n'
        f'<h4>{self.singlePointMeasurements[0].refOriName}</h4>\n'
        f'\n'
        f'<table style="max-width: 700px;" class="hide">\n'
        f'  <tr><td colspan="2">Locations</td><td>CL</td><td>BL</td><td>TL</td><td>LL</td><td>RL</td></tr>\n'
        f'  <tr><td width="175px" colspan="2">Measurements</td><td><b>{s0v[0][0]}</td><td>{s0v[0][1]}</td><td>{s0v[0][2]}</td><td>{s0v[0][3]}</td><td>{s0v[0][4]}</td></tr>\n'
        f'  <tr><td rowspan="2">Accuracy (mm)</td>\n'
        f'      <td>Mean</td><td><b>{s0v[1][0]}</td><td>{s0v[1][1]}</td><td>{s0v[1][2]}</td><td>{s0v[1][3]}</td><td>{s0v[1][4]}</td></tr>\n'
        f'  <tr><td>Max</td><td><b>{s0v[2][0]}</td><td>{s0v[2][1]}</td><td>{s0v[2][2]}</td><td>{s0v[2][3]}</td><td>{s0v[2][4]}</td></tr>\n'
        f'  <tr><td rowspan="2">Precision (mm)</td>\n'
        f'      <td>Span</td><td><b>{s0v[3][0]}</td><td>{s0v[3][1]}</td><td>{s0v[3][2]}</td><td>{s0v[3][3]}</td><td>{s0v[3][4]}</td></tr>\n'
        f'  <tr><td>RMS</td><td><b>{s0v[4][0]}</td><td>{s0v[4][1]}</td><td>{s0v[4][2]}</td><td>{s0v[4][3]}</td><td>{s0v[4][4]}</td></tr>\n'
        f'</table>\n'
        f'\n'
        f'<h4>{self.singlePointMeasurements[1].refOriName}</h4>\n'
        f'\n'
        f'<table style="max-width: 700px;" class="hide">\n'
        f'  <tr><td colspan="2">Locations</td><td>CL</td><td>BL</td><td>TL</td><td>LL</td><td>RL</td></tr>\n'
        f'  <tr><td width="175px" colspan="2">Measurements</td><td><b>{s1v[0][0]}</td><td>{s1v[0][1]}</td><td>{s1v[0][2]}</td><td>{s1v[0][3]}</td><td>{s1v[0][4]}</td></tr>\n'
        f'  <tr><td rowspan="2">Accuracy (mm)</td>\n'
        f'      <td>Mean</td><td><b>{s1v[1][0]}</td><td>{s1v[1][1]}</td><td>{s1v[1][2]}</td><td>{s1v[1][3]}</td><td>{s1v[1][4]}</td></tr>\n'
        f'  <tr><td>Max</td><td><b>{s1v[2][0]}</td><td>{s1v[2][1]}</td><td>{s1v[2][2]}</td><td>{s1v[2][3]}</td><td>{s1v[2][4]}</td></tr>\n'
        f'  <tr><td rowspan="2">Precision (mm)</td>\n'
        f'      <td>Span</td><td><b>{s1v[3][0]}</td><td>{s1v[3][1]}</td><td>{s1v[3][2]}</td><td>{s1v[3][3]}</td><td>{s1v[3][4]}</td></tr>\n'
        f'  <tr><td>RMS</td><td><b>{s1v[4][0]}</td><td>{s1v[4][1]}</td><td>{s1v[4][2]}</td><td>{s1v[4][3]}</td><td>{s1v[4][4]}</td></tr>\n'
        f'</table>\n'
        f'\n'
        f'<h4>{self.singlePointMeasurements[2].refOriName}</h4>\n'
        f'\n'
        f'<table style="max-width: 700px;" class="hide">\n'
        f'  <tr><td colspan="2">Locations</td><td>CL</td><td>BL</td><td>TL</td><td>LL</td><td>RL</td></tr>\n'
        f'  <tr><td width="175px" colspan="2">Measurements</td><td><b>{s2v[0][0]}</td><td>{s2v[0][1]}</td><td>{s2v[0][2]}</td><td>{s2v[0][3]}</td><td>{s2v[0][4]}</td></tr>\n'
        f'  <tr><td rowspan="2">Accuracy (mm)</td>\n'
        f'      <td>Mean</td><td><b>{s2v[1][0]}</td><td>{s2v[1][1]}</td><td>{s2v[1][2]}</td><td>{s2v[1][3]}</td><td>{s2v[1][4]}</td></tr>\n'
        f'  <tr><td>Max</td><td><b>{s2v[2][0]}</td><td>{s2v[2][1]}</td><td>{s2v[2][2]}</td><td>{s2v[2][3]}</td><td>{s2v[2][4]}</td></tr>\n'
        f'  <tr><td rowspan="2">Precision (mm)</td>\n'
        f'      <td>Span</td><td><b>{s2v[3][0]}</td><td>{s2v[3][1]}</td><td>{s2v[3][2]}</td><td>{s2v[3][3]}</td><td>{s2v[3][4]}</td></tr>\n'
        f'  <tr><td>RMS</td><td><b>{s2v[4][0]}</td><td>{s2v[4][1]}</td><td>{s2v[4][2]}</td><td>{s2v[4][3]}</td><td>{s2v[4][4]}</td></tr>\n'
        f'</table>\n'
        f'\n'
        f'<h3>Rotation Precision Tests</h3>\n'
        f'The rotation tests measure the precision of single point acquisition under various orientations of the pointer. These orientations consists of <b>successive</b> rotations around the roll, pitch and yaw axes of the pointer.<br>\n'
        f'The measurements consist in sampling the position of the pointer every 1° during a rotation. The number of measurements is reported in the table below.<br>\n'
        f'For each rotation axis (roll, pitch, yaw), the minimum and maximum angles for which tracking is possible are reported.<br>\n'
        f'For precision, the maximum distance of between two measurements (span) and the RMS of the deviations are reported. The deviations are calculated as the distances of each measurement from the average position previously determined in the Single Point Test with the normal orientation. If that Single Point Test with normal orientation was not performed, then the ground truth position of the measured divot is used instead.\n'
        f'\n'
        f'<h4>{self.rotMeasurements[0].rotAxisName} Rotation Precision Test</h4>\n'
        f'\n'
        f'<table style="max-width: 700px;">\n'
        f'  <tr><td colspan="2">Locations</td><td>CL</td><td>BL</td><td>TL</td><td>LL</td><td>RL</td></tr>\n'
        f'  <tr><td width="175px" colspan="2">Measurements</td><td><b>{r0v[0][0]}</td><td>{r0v[0][1]}</td><td>{r0v[0][2]}</td><td>{r0v[0][3]}</td><td>{r0v[0][4]}</td></tr>\n'
        f'  <tr><td rowspan="2">Angle (°)</td>\n'
        f'      <td>Min</td><td><b>{r0v[1][0]}</td><td>{r0v[1][1]}</td><td>{r0v[1][2]}</td><td>{r0v[1][3]}</td><td>{r0v[1][4]}</td></tr>\n'
        f'  <tr><td>Max</td><td><b>{r0v[2][0]}</td><td>{r0v[2][1]}</td><td>{r0v[2][2]}</td><td>{r0v[2][3]}</td><td>{r0v[2][4]}</td></tr>\n'
        f'  <tr><td rowspan="2">Precision (mm)</td>\n'
        f'      <td>Span</td><td><b>{r0v[3][0]}</td><td>{r0v[3][1]}</td><td>{r0v[3][2]}</td><td>{r0v[3][3]}</td><td>{r0v[3][4]}</td></tr>\n'
        f'  <tr><td>RMS</td><td><b>{r0v[4][0]}</td><td>{r0v[4][1]}</td><td>{r0v[4][2]}</td><td>{r0v[4][3]}</td><td>{r0v[4][4]}</td></tr>\n'
        f'</table>\n'
        f'\n'
        f'<h4>{self.rotMeasurements[1].rotAxisName} Rotation Precision Test</h4>\n'
        f'\n'
        f'<table style="max-width: 700px;">\n'
        f'  <tr><td colspan="2">Locations</td><td>CL</td><td>BL</td><td>TL</td><td>LL</td><td>RL</td></tr>\n'
        f'  <tr><td width="175px" colspan="2">Measurements</td><td><b>{r1v[0][0]}</td><td>{r1v[0][1]}</td><td>{r1v[0][2]}</td><td>{r1v[0][3]}</td><td>{r1v[0][4]}</td></tr>\n'
        f'  <tr><td rowspan="2">Angle (°)</td>\n'
        f'      <td>Min</td><td><b>{r1v[1][0]}</td><td>{r1v[1][1]}</td><td>{r1v[1][2]}</td><td>{r1v[1][3]}</td><td>{r1v[1][4]}</td></tr>\n'
        f'  <tr><td>Max</td><td><b>{r1v[2][0]}</td><td>{r1v[2][1]}</td><td>{r1v[2][2]}</td><td>{r1v[2][3]}</td><td>{r1v[2][4]}</td></tr>\n'
        f'  <tr><td rowspan="2">Precision (mm)</td>\n'
        f'      <td>Span</td><td><b>{r1v[3][0]}</td><td>{r1v[3][1]}</td><td>{r1v[3][2]}</td><td>{r1v[3][3]}</td><td>{r1v[3][4]}</td></tr>\n'
        f'  <tr><td>RMS</td><td><b>{r1v[4][0]}</td><td>{r1v[4][1]}</td><td>{r1v[4][2]}</td><td>{r1v[4][3]}</td><td>{r1v[4][4]}</td></tr>\n'
        f'</table>\n'
        f'\n'
        f'<h4>{self.rotMeasurements[2].rotAxisName} Rotation Precision Test</h4>\n'
        f'\n'
        f'<table style="max-width: 700px;">\n'
        f'  <tr><td colspan="2">Locations</td><td>CL</td><td>BL</td><td>TL</td><td>LL</td><td>RL</td></tr>\n'
        f'  <tr><td width="175px" colspan="2">Measurements</td><td><b>{r2v[0][0]}</td><td>{r2v[0][1]}</td><td>{r2v[0][2]}</td><td>{r2v[0][3]}</td><td>{r2v[0][4]}</td></tr>\n'
        f'  <tr><td rowspan="2">Angle (°)</td>\n'
        f'      <td>Min</td><td><b>{r2v[1][0]}</td><td>{r2v[1][1]}</td><td>{r2v[1][2]}</td><td>{r2v[1][3]}</td><td>{r2v[1][4]}</td></tr>\n'
        f'  <tr><td>Max</td><td><b>{r2v[2][0]}</td><td>{r2v[2][1]}</td><td>{r2v[2][2]}</td><td>{r2v[2][3]}</td><td>{r2v[2][4]}</td></tr>\n'
        f'  <tr><td rowspan="2">Precision (mm)</td>\n'
        f'      <td>Span</td><td><b>{r2v[3][0]}</td><td>{r2v[3][1]}</td><td>{r2v[3][2]}</td><td>{r2v[3][3]}</td><td>{r2v[3][4]}</td></tr>\n'
        f'  <tr><td>RMS</td><td><b>{r2v[4][0]}</td><td>{r2v[4][1]}</td><td>{r2v[4][2]}</td><td>{r2v[4][3]}</td><td>{r2v[4][4]}</td></tr>\n'
        f'</table>\n'
        f'\n'
        f'<h3>Multi-point Accuracy Test</h3>\n'
        f'This test measures the spatial relationship between various acquired points and compare it to the reference values. This can be done in two ways: distances or point cloud registration.<br>\n'
        f'The distances are calculated for all combinations of pair of points. So, for N points measured, there are N(N-1)/2 distances (e.g. 20 measured points gives 190 distances). For each pair of points, the error is calculated as the difference with the corresponding reference pair in terms of distance. The number of distances and the mean, minimum, maximum and RMS of these errors are reported below.<br>\n'
        f'The registration is performed between the point clouds from the measurements and from the reference. The mean, minimum, maximum, RMS of the registration residuals are reported below.\n'
        f'<p>\n'
        f'<table style="max-width: 700px;">\n'
        f'  <tr><td colspan="2">Locations</td><td>CL</td><td>BL</td><td>TL</td><td>LL</td><td>RL</td></tr>\n'
        f'  <tr><td width="175px" colspan="2">Measurements</td><td><b>{mv[0][0]}</td><td>{mv[0][1]}</td><td>{mv[0][2]}</td><td>{mv[0][3]}</td><td>{mv[0][4]}</td></tr>\n'
        f'  <tr><td rowspan="5">Distances (mm)</td>\n'
        f'      <td>Num.</td><td><b>{mv[1][0]}</td><td>{mv[1][1]}</td><td>{mv[1][2]}</td><td>{mv[1][3]}</td><td>{mv[1][4]}</td></tr>\n'
        f'  <tr><td>Mean</td><td><b>{mv[2][0]}</td><td>{mv[2][1]}</td><td>{mv[2][2]}</td><td>{mv[2][3]}</td><td>{mv[2][4]}</td></tr>\n'
        f'  <tr><td>Min</td><td><b>{mv[3][0]}</td><td>{mv[3][1]}</td><td>{mv[3][2]}</td><td>{mv[3][3]}</td><td>{mv[3][4]}</td></tr>\n'
        f'  <tr><td>Max</td><td><b>{mv[4][0]}</td><td>{mv[4][1]}</td><td>{mv[4][2]}</td><td>{mv[4][3]}</td><td>{mv[4][4]}</td></tr>\n'
        f'  <tr><td>RMS</td><td><b>{mv[5][0]}</td><td>{mv[5][1]}</td><td>{mv[5][2]}</td><td>{mv[5][3]}</td><td>{mv[5][4]}</td></tr>\n'
        f'  <tr><td rowspan="4">Registration (mm)</td>\n'
        f'      <td>Mean</td><td><b>{mv[6][0]}</td><td>{mv[6][1]}</td><td>{mv[6][2]}</td><td>{mv[6][3]}</td><td>{mv[6][4]}</td></tr>\n'
        f'  <tr><td>Min</td><td><b>{mv[7][0]}</td><td>{mv[7][1]}</td><td>{mv[7][2]}</td><td>{mv[7][3]}</td><td>{mv[7][4]}</td></tr>\n'
        f'  <tr><td>Max</td><td><b>{mv[8][0]}</td><td>{mv[8][1]}</td><td>{mv[8][2]}</td><td>{mv[8][3]}</td><td>{mv[8][4]}</td></tr>\n'
        f'  <tr><td>RMS</td><td><b>{mv[9][0]}</td><td>{mv[9][1]}</td><td>{mv[9][2]}</td><td>{mv[9][3]}</td><td>{mv[9][4]}</td></tr>\n'
        f'</table>\n'
        f'</div>\n'
        f'</body>\n'
        f'</html>\n'
        )
      htmlFile.close()
    