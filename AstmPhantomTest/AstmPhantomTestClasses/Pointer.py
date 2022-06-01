import vtk
import logging
import slicer
import numpy as np
import qt
import os
import math
from .Utils import PosQueue

#
# Pointer class
#

class Pointer(vtk.vtkObject):
  """This is a custom class for the pointer
  """
  def __init__(self):
    super().__init__()
    self.id = "XXXXX" # pointer id, typically its serial number
    self.pq = PosQueue(20)  # queue to continuously store the last 20 pointer positions
    self.ptrRefTransfoNode = None
    self.ptrTransfoNode = None
    self.model = None
    self.obsId = None
    # pointer moving, moved, stopped
    self.moving = False
    self.movingTol = 0.5
    self.movedEvent = vtk.vtkCommand.UserEvent + 1
    self.stoppedEvent = vtk.vtkCommand.UserEvent + 2
    self.movingTolChanged = vtk.vtkCommand.UserEvent + 3
    # pointer tracking status
    self.tracking = False
    self.trackingStoppedEvent = vtk.vtkCommand.UserEvent + 4
    self.trackingStartedEvent = vtk.vtkCommand.UserEvent + 5
    # static and acquisition status
    self.staticConstraint = False
    self.staticFailEvent = vtk.vtkCommand.UserEvent + 6
    self.acquiring = False
    self.acquiDone = False
    self.acquiProgEvent = vtk.vtkCommand.UserEvent + 7
    self.acquiDoneEvent = vtk.vtkCommand.UserEvent + 8
    self.acquiDoneOutEvent = vtk.vtkCommand.UserEvent + 9
    # accumulator and timer
    self.acquiMode = 0  # 0: 1-frame, 1: mean, 2: median
    self.coordAccumulator = np.array([])  # stores all incoming coordinates during acquisition
    self.numFrames = 30  # number of successive frames considered in the acquisition of a single point
    self.timer = qt.QTimer()
    self.timerDuration = 0
    self.timer.setInterval(50)  # timer ticks every 50 ms
    self.timer.connect('timeout()', self.staticTimerCallback)
    # tilt
    self.monitorTilt = True
    self.maxTilt = 60 # default value
    # angles wrt to standard reference axes
    self.emitAngles = False
    self.anglesChangedEvent = vtk.vtkCommand.UserEvent + 11
    # standard reference axes in tracker referential (default values)
    self.trkRollAxis = [0,0,1]
    self.trkPitchAxis = [-1,0,0]
    self.trkYawAxis = [0,-1,0]
    # standard reference axes in pointer referential (default values)
    self.ptrRollAxis = [0,0,-1]
    self.ptrPitchAxis = [-1,0,0]
    self.ptrYawAxis = [0,1,0]
    self.modelTransfoNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'ptrModelTransfo')
    # init matrices to identity
    self.ptrRefMat = np.identity(4)
    self.ptrMat = np.identity(4)
    self.stdPtrMat = np.identity(4)
    self.ptrRotMat = np.identity(4)
    self.trkRotMat = np.identity(4)
    # pointer height (in mm, important for pointer visibility near top of the working volume)
    self.height = 0

  def readModel(self, path):
    prevModelNode = slicer.mrmlScene.GetFirstNodeByName('PointerModel')
    if prevModelNode:
      slicer.mrmlScene.RemoveNode(prevModelNode)
    logging.info("Read pointer model")
    self.model = slicer.mrmlScene.GetFirstNodeByName('PointerModel')
    if self.model == None:
      self.model = slicer.util.loadModel(path)
      self.model.SetName('PointerModel')
      self.model.GetDisplayNode().VisibilityOff()

  def setMovingTolerance(self, val):
    self.movingTol = val
    self.InvokeEvent(self.movingTolChanged, str(val))

  def setTransfoNodes(self, ptrRefTransfoNode, ptrTransfoNode):
    # apply transformation to the model according to rotation axes
    self.model.SetAndObserveTransformNodeID(self.modelTransfoNode.GetID())
    # apply the ptr from ref transform to the pointer model in post-multiply
    self.ptrRefTransfoNode = ptrRefTransfoNode
    self.modelTransfoNode.SetAndObserveTransformNodeID(self.ptrRefTransfoNode.GetID())
    # observe the ptrRef transform
    self.ptrRefTransfoNode.AddObserver(slicer.vtkMRMLTransformNode.TransformModifiedEvent, \
          self.onPtrRefTransformModified)

    self.ptrTransfoNode = ptrTransfoNode
    # observe the ptr transform
    self.ptrTransfoNode.AddObserver(slicer.vtkMRMLTransformNode.TransformModifiedEvent, \
      self.onPtrTransformModified)

  def readPointerFile(self, path):
    """
    Reads and parse the orientation of the pointer standard axes
    """
    logging.info('Read pointer file')
    self.id = os.path.basename(path).split('.txt')[0] # retrieve filename only
    # read the file content
    file = open(path, 'r')
    lines = file.readlines()
    for l in lines:
      q = np.fromstring(l.split('=')[1], dtype=float, sep=' ')
      if l.startswith('MAXTILT'):
        self.maxTilt = q[0]
      if l.startswith('ROLL'):
        self.ptrRollAxis = q.tolist()
      if l.startswith('PITCH'):
        self.ptrPitchAxis = q.tolist()
      if l.startswith('YAW'):
        self.ptrYawAxis = q.tolist()
      if l.startswith('HEIGHT'):
        self.height = q[0]
    self.checkPtrAxes()
    # calculate the model transformation necessary to align with yaw and roll axes
    ptsFrom = vtk.vtkPoints()
    ptsFrom.InsertNextPoint([0,0,0]) # model origin
    ptsFrom.InsertNextPoint([0,1,0]) # yaw axis in original model
    ptsFrom.InsertNextPoint([0,0,-1]) # roll axis in original model
    ptsTo = vtk.vtkPoints()
    ptsTo.InsertNextPoint([0,0,0])
    ptsTo.InsertNextPoint(self.ptrYawAxis)
    ptsTo.InsertNextPoint(self.ptrRollAxis)
    ldmkTransfo = vtk.vtkLandmarkTransform()
    ldmkTransfo.SetSourceLandmarks(ptsFrom)
    ldmkTransfo.SetTargetLandmarks(ptsTo)
    ldmkTransfo.SetModeToSimilarity()
    ldmkTransfo.Update()
    self.modelTransfoNode.SetMatrixTransformToParent(ldmkTransfo.GetMatrix())
    return True

  def checkPtrAxes(self):
    # make sure the standard referential frames provided for
    # the pointer are orthonormal and direct
    self.ptrRollAxis = self.ptrRollAxis/np.linalg.norm(self.ptrRollAxis)
    self.ptrPitchAxis = np.cross(self.ptrYawAxis/np.linalg.norm(self.ptrYawAxis),
      self.ptrRollAxis)
    self.ptrYawAxis = np.cross(self.ptrRollAxis, self.ptrPitchAxis)
    # build rotation matrix from axes: X = roll, Y = pitch, Z = yaw
    self.ptrRotMat = np.array([self.ptrRollAxis, self.ptrPitchAxis, self.ptrYawAxis])

  def checkTrkAxes(self):
    # make sure the standard referential frames provided for
    # the tracker are orthonormal and direct
    self.trkRollAxis = self.trkRollAxis/np.linalg.norm(self.trkRollAxis)
    self.trkPitchAxis = np.cross(self.trkYawAxis/np.linalg.norm(self.trkYawAxis),
      self.trkRollAxis)
    self.trkYawAxis = np.cross(self.trkRollAxis, self.trkPitchAxis)
    # build rotation matrix from axes: X = roll, Y = pitch, Z = yaw
    self.trkRotMat = np.array([self.trkRollAxis, self.trkPitchAxis, self.trkYawAxis])

  def __rotmat2euler(self, mat):
    angRoll = math.atan2(mat[2,1], mat[2,2])
    angPitch = math.atan2(-mat[2,0], math.sqrt(mat[2,1]**2 + mat[2,2]**2))
    angYaw = math.atan2(mat[1,0], mat[0,0])
    return [angRoll*180/math.pi, angPitch*180/math.pi, angYaw*180/math.pi]

  # returns pointer euler angles in standard referential frame
  def angles(self):
    return self.__rotmat2euler(self.stdPtrMat)

  # returns the unsigned tilt from roll axis in std ref frame
  def tilt(self):
    return math.acos(self.stdPtrMat[0,0])*180/math.pi

  # returns the position from ptr from ref transform
  def pos(self):
    return self.ptrRefMat[:-1,3]

  @vtk.calldata_type(vtk.VTK_STRING)
  def onPtrTransformModified(self, caller, event=None, calldata=None):
    if self.ptrTransfoNode.GetAttribute("TransformStatus") == "MISSING":
      if self.tracking:
        self.tracking = False
        # logging.info('/!\ Tracking stopped')
        self.InvokeEvent(self.trackingStoppedEvent)
    elif self.ptrTransfoNode.GetAttribute("TransformStatus") == "OK":
      if not self.tracking:
        self.tracking = True
        # logging.info(" => Tracking started")
        self.InvokeEvent(self.trackingStartedEvent)
      # update current matrices
      self.ptrMat = slicer.util.arrayFromTransformMatrix(self.ptrTransfoNode)
      self.stdPtrMat = self.trkRotMat.dot(self.ptrMat[:3,:3].dot(self.ptrRotMat.T))
      # emit tilt value
      if self.monitorTilt:
        prog = (self.maxTilt-self.tilt())/self.maxTilt # normalize discrepancy from 0 deg tilt goal
        self.model.GetDisplayNode().SetColor(1-prog, prog, 0) # color with respect to discrepancy

  @vtk.calldata_type(vtk.VTK_STRING)
  def onPtrRefTransformModified(self, caller, event=None, calldata=None):
    if self.ptrTransfoNode.GetAttribute("TransformStatus") == "OK":
      # update current matrix
      self.ptrRefMat = slicer.util.arrayFromTransformMatrix(self.ptrRefTransfoNode)
      # if angles are to be emitted, emit them alongside the current pointer position
      if self.emitAngles:
        self.InvokeEvent(self.anglesChangedEvent, str(self.angles()+self.pos().tolist()))
      # retrieve pointer position
      self.pq.push(self.pos())
      # if moved by more than the moving tolerance from last position in queue
      if self.pq.stride() > self.movingTol:
        if not self.moving:
          self.moving = True
          self.InvokeEvent(self.movedEvent)
          self.model.GetDisplayNode().SetOpacity(0.4)
          if self.staticConstraint: # pointer needs to be static
            if self.acquiDone: # acquisition done
              self.acquiDone = False
              self.staticConstraint = False
              self.InvokeEvent(self.acquiDoneOutEvent)
            else:
              if self.acquiring:
                self.acquiring = False
                self.coordAccumulator = np.array([])
                if self.acquiMode == 0 and self.timer.isActive():
                  self.timer.stop()
              self.InvokeEvent(self.staticFailEvent)
      else:
        if self.moving:
          self.moving = False
          self.model.GetDisplayNode().SetOpacity(1.0)
          # emit event with pointer position attached to it as a string
          self.InvokeEvent(self.stoppedEvent, str(self.pq.queue[-1].tolist()))
        if self.acquiring:
          if not self.coordAccumulator.any():
            self.coordAccumulator = np.array([self.pq.queue[-1].tolist()])  # [[]] important for stacking
          else:
            self.coordAccumulator = np.append(self.coordAccumulator, [self.pq.queue[-1].tolist()], axis=0)
          # if not 1-frame acquisition
          if self.acquiMode != 0:
            prog = min(np.size(self.coordAccumulator,0)/self.numFrames, 1.0)  # estimate progression (btw 0.0 and 1.0)
            self.InvokeEvent(self.acquiProgEvent, str(prog))
            if np.size(self.coordAccumulator,0) == self.numFrames: # if accumulator full
              self.acquiring = False
              self.acquiDone = True
              if self.acquiMode == 1:  # mean
                p = np.mean(self.coordAccumulator, axis=0)
              if self.acquiMode == 2:  # median
                p = np.median(self.coordAccumulator, axis=0)
              self.coordAccumulator = np.array([])
              self.InvokeEvent(self.acquiDoneEvent, str(p.tolist()))

  @vtk.calldata_type(vtk.VTK_STRING)
  def startAcquiring(self, caller, event = None, calldata = None):
    if not self.moving:
      self.staticConstraint = True
      self.acquiring = True
      self.coordAccumulator = np.array([])
      if self.acquiMode == 0:
        self.maxTicks = int(self.timerDuration / self.timer.interval) + 1
        self.ticks = 0
        self.timer.start()
        logging.info(f'   Timer started for {self.maxTicks} ticks')

  def staticTimerCallback(self):
    if not self.moving and self.timer.isActive():
      self.ticks += 1
      prog = min(self.ticks / self.maxTicks, 1.0)  # estimate progression (btw 0.0 and 1.0)
      self.InvokeEvent(self.acquiProgEvent, str(prog))
      if prog >= 1:
        self.timer.stop()
        p = self.coordAccumulator[int(np.size(self.coordAccumulator,0)/2)]  # get middle coordinates
        self.acquiring = False
        self.acquiDone = True
        self.InvokeEvent(self.acquiDoneEvent, str(p.tolist()))
