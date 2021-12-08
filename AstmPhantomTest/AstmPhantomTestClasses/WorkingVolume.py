import vtk
import slicer
import logging
import numpy as np
import os
from .Utils import *

class WorkingVolumeActor(vtk.vtkActor):

  def __init__(self):
    super().__init__()
    self.meshPolyData = vtk.vtkPolyData()
    self.meshMapper = vtk.vtkPolyDataMapper()
    self.meshMapper.SetInputData(self.meshPolyData)
    self.SetMapper(self.meshMapper)

    self.edgesPolyData = vtk.vtkPolyData()
    self.edgesMapper = vtk.vtkPolyDataMapper()
    self.edgesMapper.SetInputData(self.edgesPolyData)
    self.edges = vtk.vtkActor()
    self.edges.SetMapper(self.edgesMapper)

    # prevent edges and mesh from brawling in Z-buffer
    vtk.vtkPolyDataMapper().SetResolveCoincidentTopologyToPolygonOffset()

  def __inspoly(self, polys, id0, id1, id2):
    idList = vtk.vtkIdList()
    idList.InsertNextId(id0)
    idList.InsertNextId(id1)
    idList.InsertNextId(id2)
    polys.InsertNextCell(idList)

  def setNodes(self, pts):
    nodes = vtk.vtkPoints()
    for p in pts:
      nodes.InsertPoint(int(p), pts[p])

    # Mesh
    polys = vtk.vtkCellArray()
    ids = list(pts.keys()) # get all the node ids
    # Define lambda to ensure correct connection every k nodes
    lb = lambda i, k=4: i-k if i%k == 0 else i
    # for each face
    for i in range(0,len(ids)-4):
      self.__inspoly(polys, ids[i], ids[lb(i+1)], ids[i+4]) # first triangle
      self.__inspoly(polys, ids[i+4], ids[lb(i+1)], ids[lb(i+5)]) # second triangle
    
    self.meshPolyData.SetPoints(nodes)
    self.meshPolyData.SetPolys(polys)

    # Edges
    lines = vtk.vtkCellArray()
    # Front edges
    for i in range(0,4):
      lines.InsertNextCell(2, [ids[i], ids[lb(i+1)]])
    # Side edges
    for i in range(0,len(ids)-4,4):
      for k in range(0,4):
        lines.InsertNextCell(2, [ids[i]+k, ids[i]+k+4])
    # Back edges
    for i in range(len(ids)-4,len(ids)):
      lines.InsertNextCell(2, [ids[i], ids[lb(i+1)]])

    self.edgesPolyData.SetPoints(nodes)
    self.edgesPolyData.SetLines(lines)

#
# Working Volume class
#

class WorkingVolume(vtk.vtkObject):

  def __init__(self, topWVWidget, sideWVWidget):
    super().__init__()
    self.id = "XXXXX" # working volume id, typically the tracker model (XXXXX)

    self.actorTop = WorkingVolumeActor()
    self.actorTop.GetProperty().SetColor(1,1,1)
    self.actorTop.GetProperty().SetOpacity(0.2)
    self.actorTop.edges.GetProperty().SetColor(0.2,1,0)
    self.renTop = topWVWidget.threeDView().renderWindow().GetRenderers().GetItemAsObject(0)
    self.renTop.GetActiveCamera().ParallelProjectionOn()
    self.renTop.AddActor(self.actorTop)
    self.renTop.AddActor(self.actorTop.edges)

    self.actorSide = WorkingVolumeActor()
    self.actorSide.GetProperty().SetColor(1,1,1)
    self.actorSide.GetProperty().SetOpacity(0.2)
    self.actorSide.edges.GetProperty().SetColor(1,0,0.8)
    self.renSide = sideWVWidget.threeDView().renderWindow().GetRenderers().GetItemAsObject(0)
    self.renSide.GetActiveCamera().ParallelProjectionOn()
    self.renSide.AddActor(self.actorSide)
    self.renSide.AddActor(self.actorSide.edges)

    self.__mat = vtk.vtkMatrix4x4()
    self.pq = PosQueue(20)  # queue to continuously store the last 20 pointer positions
    self.obsId = None
    self.transfoNode = None
    self.moving = False
    self.offset = np.array([0,0,0])
    self.movedEvent = vtk.vtkCommand.UserEvent + 1
    self.stoppedEvent = vtk.vtkCommand.UserEvent + 2

    self.movingTolMin = {"tol": 0.5, "depth":300}
    self.movingTolMax = {"tol": 1.5, "depth":3000}

    self.rollAxis = [0, 0, 1]
    self.pitchAxis = [-1, 0, 0]
    self.yawAxis = [0, -1, 0]

  # Simplified model of the phantom indicating its position in working volume    
  def readSimpPhantomModel(self, path):
    prevModelNode = slicer.mrmlScene.GetFirstNodeByName('SimpPhantomModel')
    if prevModelNode:
      slicer.mrmlScene.RemoveNode(prevModelNode)
    logging.info("Read simplified phantom model")
    self.simpPhantomModel = slicer.util.loadModel(path)
    self.simpPhantomModel.SetName('SimpPhantomModel')
    self.simpPhantomModel.GetDisplayNode().SetColor(0,0.8,1.0)

  def setTransfoNode(self, tNode):
    self.transfoNode = tNode
    self.simpPhantomModel.SetAndObserveTransformNodeID(self.transfoNode.GetID())

  def watchTransfoNode(self, tof = True):
    if not tof and self.obsId:
      self.simpPhantomModel.RemoveObserver(self.obsId)
    if tof:
      self.obsId = self.simpPhantomModel.AddObserver(slicer.vtkMRMLTransformNode.TransformModifiedEvent, \
          self.onTransformModified)

  def readWorkingVolumeFile(self, path):
    """
    Reads and parse the working volume coordinates
    """
    logging.info('Read working volume file')
    logging.info(path)
    file = open(path, 'r')
    lines = file.readlines()
    nodes = {}
    self.locs = {} # locations provided in the file
    for l in lines:
      if not l == "\n":
        ss = l.split('=') # split string
        p = np.fromstring(ss[1], dtype=float, sep=' ')
        logging.info(f'   {ss[0]} {p.tolist()}')
        if l.startswith('NODE'):
          nodes[int(p[0])] = p[1:]
        elif l.startswith('MOVTOLMIN'):
          # min moving tolerance is p[0] at depth p[1]
          self.movingTolMin['tol'] = p[0]
          self.movingTolMin['depth'] = p[1]
        elif l.startswith('MOVTOLMAX'):
          # max moving tolerance is p[0] at depth p[1]
          self.movingTolMax['tol'] = p[0]
          self.movingTolMax['depth'] = p[1]
        else:
          if l.startswith('PC'):
            self.locs['PC'] = p
            self.renTop.GetActiveCamera().SetFocalPoint(p.tolist())
            self.renSide.GetActiveCamera().SetFocalPoint(p.tolist())
          if l.startswith('PR'):
            self.locs['PR'] = p
          if l.startswith('PL'):
            self.locs['PL'] = p
          if l.startswith('PBK'):
            self.locs['PBK'] = p
          if l.startswith('PBT'):
            self.locs['PBT'] = p
          if l.startswith('TCAMPOS'):
            self.renTop.GetActiveCamera().SetPosition((self.locs['PC'] + p).tolist())
          if l.startswith('TCAMVUP'):
            self.renTop.GetActiveCamera().SetViewUp(p.tolist())
          if l.startswith('SCAMPOS'):
            self.renSide.GetActiveCamera().SetPosition((self.locs['PC'] + p).tolist())
          if l.startswith('SCAMVUP'):
            self.renSide.GetActiveCamera().SetViewUp(p.tolist())
          if l.startswith('ROLL'):
            self.rollAxis = p.tolist()
          if l.startswith('PITCH'):
            self.pitchAxis = p.tolist()
          if l.startswith('YAW'):
            self.yawAxis = p.tolist()

    if nodes:
      self.actorTop.setNodes(nodes)
      self.actorSide.setNodes(nodes)
    else:
      msg = "No nodes could be read in the working volume file"
      logging.error(msg)
      slicer.util.errorDisplay(msg)
      return False

    self.id = os.path.basename(path).split('.txt')[0] # retrieve filename only
    return True

  # returns pointer moving tolerance depending on current phantom position
  def movingToleranceFromPos(self, pos):
    if (pos[2] < self.movingTolMin["depth"] or pos[2] > self.movingTolMax["depth"]):
      logging.info("========= /!\\ Depth outside working volume: setting largest moving tolerance for pointer /!\\ =========")
      return self.movingTolMax["tol"] # largest tolerance to be safe
    elif (abs(self.movingTolMax["depth"] - self.movingTolMin["depth"]) < 0.001):
      logging.info("========= /!\\ Working volume too narrow in depth: setting smallest moving tolerance for pointer /!\\ =========")
      return self.movingTolMin["tol"] # smallest tolerance since nearly no difference in depth
    else: # tol = a*depth^2+b as tolerance is a function of depth squared
      a = (self.movingTolMax["tol"] - self.movingTolMin["tol"])/(self.movingTolMax["depth"]**2 - self.movingTolMin["depth"]**2)
      b = self.movingTolMax["tol"] - a * self.movingTolMax["depth"]**2
      return a * pos[2]**2 + b

  # returns the position of the simp phantom from its transform matrix
  def simpPhantPos(self):
    if self.transfoNode:
      self.transfoNode.GetMatrixTransformToParent(self.__mat)
      return np.array([self.__mat.GetElement(0,3), self.__mat.GetElement(1,3),
        self.__mat.GetElement(2,3)])
    else:
      return np.array([np.nan,np.nan,np.nan])

  # returns the position of the simp phantom with the offset
  def simpPhantPosWithOffset(self):
    if self.transfoNode:
      self.transfoNode.GetMatrixTransformToParent(self.__mat)
      pos = self.__mat.MultiplyDoublePoint(np.append(self.offset, 1.0)) # return a tuple
      return list(pos[0:3])
    else:
      return np.array([np.nan,np.nan,np.nan])

  @vtk.calldata_type(vtk.VTK_STRING)
  def onTransformModified(self, caller, event=None, calldata=None):
    self.pq.push(self.simpPhantPos())
    if self.pq.stride() > 1.0:  # if more than 1.0mm from last position in queue
      if not self.moving:
        self.moving = True
        self.InvokeEvent(self.movedEvent)
    else:
      if self.moving:
        self.moving = False
        # calculate position with offset
        pos = self.simpPhantPosWithOffset()
        # emit event with simp phantom position attached as a string
        logging.info(f'   Simp Phantom stopped at {np.around(pos,2).tolist()}')
        self.InvokeEvent(self.stoppedEvent, str(pos))