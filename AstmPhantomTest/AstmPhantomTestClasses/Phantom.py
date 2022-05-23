import vtk
import logging
import slicer
import os
import numpy as np

#
# Phantom class
#

class Phantom(vtk.vtkObject):
  """This is a custom class for the pointer
  """
  def __init__(self):
    super().__init__()
    self.id = "XXXXXYY" # phantom id, typically its serial number (XXXXX) and maybe also divot shape (YY)
    self.centralDivot = None # id of the central divot
    self.transfoNode = None
    self.model = None
    self.modelPath = None
    self.calibStartedEvent = vtk.vtkCommand.UserEvent + 1
    self.calibratedEvent = vtk.vtkCommand.UserEvent + 2

    # Detects if a transfo node with the same name is already present
    prevTransfoNode = slicer.mrmlScene.GetFirstNodeByName('phantCalibTransfo')
    # if so, remove it
    if prevTransfoNode:
      slicer.mrmlScene.RemoveNode(prevTransfoNode)
    # Create the transfo node
    self.calibTransfoNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode', 'phantCalibTransfo')
    self.lblO = None
    self.lblX = None
    self.lblY = None
    self.gtPts = None  # divot coordinates as given by the geometry file, used only for distance measuring
    self.seq = None # sequence of divots for the distance test
    self.resetCalib()

  def resetCalib(self):
    # divot coordinates after calibration, can be used both for distance and visualization
    self.calGtPts = {}
    self.calibrated = False
    self.readModel()

  def readModel(self, path = None):
    # store model path
    if path:
      self.modelPath = path
    if self.modelPath:
      # check if the model node already exists, if so remove it
      prevModelNode = slicer.mrmlScene.GetFirstNodeByName('PhantomModel')
      if prevModelNode:
        prevModelNode.RemoveAllObservers()
        slicer.mrmlScene.RemoveNode(prevModelNode)
      logging.info("Read phantom model")
      self.model = slicer.util.loadModel(self.modelPath)
      self.model.SetName('PhantomModel')
      self.model.GetDisplayNode().SetColor(0,0.8,1.0)
      self.model.GetDisplayNode().VisibilityOff()

  def readGroundTruthFile(self, path):
    """
    Reads and parse the ground truth coordinates
    """
    # Reset parameters
    self.centralDivot = 1
    self.gtPts = {}
    self.seq = []
    logging.info('Read groundtruth file')
    logging.info(path)
    file = open(path, 'r')
    lines = file.readlines()
    # Read parameters
    for l in lines:
      if not l == "\n":
        if l.startswith("REF"):
          ref = l.split("=")[1].split()
          if len(ref) != 3:
            msg = "Ground truth file must have 3 referential labels (REF)"
            logging.error(msg)
            slicer.util.errorDisplay(msg)
            return False
          else:
            self.lblO = int(ref[0])
            self.lblX = int(ref[1])
            self.lblY = int(ref[2])
        elif l.startswith("SEQ"):
          seq = l.split("=")[1].split()
          self.seq = [int(w) for w in seq]
        elif l.startswith("CTR"):
          self.centralDivot = int(l.split("=")[1])

    # Read ground truth values
    ptIds = [i for i, s in enumerate(lines) if s.startswith('POINT')]
    for p in ptIds:
      id = int(lines[p].split()[1]) # get point id
      x = float(lines[p+1].split()[1]) # get x coord
      y = float(lines[p+2].split()[1]) # get y coord
      z = float(lines[p+3].split()[1]) # get z coord
      self.gtPts[id] = np.array([x,y,z])

    # Check the parameters
    # Referential labels
    if not self.lblO or not self.lblX or not self.lblY:
      msg = "Could not read referential labels (REF)"
      logging.error(msg)
      slicer.util.errorDisplay(msg)
      return False
    for l in [self.lblO, self.lblX, self.lblY]:
      if not l in self.gtPts:
        msg = f"Referential label {l} not amongst given points (REF)"
        logging.error(msg)
        slicer.util.errorDisplay(msg)
        return False
    # Sequence
    if not self.seq: # if sequence list is empty
      self.seq = [int(w) for w in self.gtPts.keys()] # sequence includes all the divots
    else:
      for l in self.seq:
        if not l in self.gtPts:
          msg = f"Referential label {l} not amongst given points (REF)"
          logging.error(msg)
          slicer.util.errorDisplay(msg)
          return False
    # Central divot
    if not self.centralDivot in self.gtPts:
      msg = f"Central divot {self.centralDivot} not amongst given points (CTR)"
      logging.error(msg)
      slicer.util.errorDisplay(msg)
      return False
      
    logging.info("Groundtruth file read")
    logging.info(f'  O = #{self.lblO} {self.divPos(self.lblO).tolist()}')
    logging.info(f'  X = #{self.lblX} {self.divPos(self.lblX).tolist()}')
    logging.info(f'  Y = #{self.lblY} {self.divPos(self.lblY).tolist()}')
    logging.info(f'  seq = {self.seq}')
    logging.info(f'  center = {self.centralDivot}')
    self.id = os.path.basename(path).split('.txt')[0] # retrieve filename only
    return True

  def divPos(self, lbl):
    if self.calibrated and self.gtPts:
      return self.calGtPts[lbl]
    elif self.gtPts:
      return self.gtPts[lbl]
    else:
      return np.array([np.nan,np.nan,np.nan])
  
  def calibrate(self):
    # check no divot position has a NaN coordinate
    if self.lblO in self.calGtPts and self.lblX in self.calGtPts and \
      self.lblY in self.calGtPts:
      logging.info("   Calibrating...")

      ptsFrom = vtk.vtkPoints()
      ptsFrom.InsertNextPoint(self.gtPts[self.lblO])
      ptsFrom.InsertNextPoint(self.gtPts[self.lblX])
      ptsFrom.InsertNextPoint(self.gtPts[self.lblY])
      ptsTo = vtk.vtkPoints()
      ptsTo.InsertNextPoint(self.calGtPts[self.lblO])
      ptsTo.InsertNextPoint(self.calGtPts[self.lblX])
      ptsTo.InsertNextPoint(self.calGtPts[self.lblY])
      ldmkTransfo = vtk.vtkLandmarkTransform()
      ldmkTransfo.SetSourceLandmarks(ptsFrom)
      ldmkTransfo.SetTargetLandmarks(ptsTo)
      ldmkTransfo.SetModeToSimilarity()
      ldmkTransfo.Update()
      transfoMat = ldmkTransfo.GetMatrix()
      self.calibTransfoNode.SetMatrixTransformToParent(transfoMat)
      
      for k in self.gtPts:
        p0 = self.gtPts[k]
        p0 = np.append(p0, 1.0)  # adding 1.0 for homogeneous coords
        p1 = transfoMat.MultiplyDoublePoint(p0) # outputs a tuple
        self.calGtPts[k] = np.array([p1[0], p1[1], p1[2]])

      self.calibrated = True
      logging.info("   Calibration done.")
      self.InvokeEvent(self.calibratedEvent)
