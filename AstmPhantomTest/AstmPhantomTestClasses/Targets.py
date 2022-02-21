import vtk
import logging
import numpy as np
import qt
import ast
from .Utils import Dist

#
# Targets class
#

class Targets(vtk.vtkObject):

  def __init__(self, renderer):
    super().__init__()
    self.renderer = renderer
    self.targets = {}
    self.firstLbl = None
    # used to automatically detect target from pointer position
    self.proxiDetect = False
    # distance threshold from pointer to a target to be considered hit
    self.proxiThresh = 2  # mm
    self.targetHitEvent = vtk.vtkCommand.UserEvent + 1
    self.targetOutEvent = vtk.vtkCommand.UserEvent + 2
    self.targetDoneEvent = vtk.vtkCommand.UserEvent + 3
    self.targetDoneOutEvent = vtk.vtkCommand.UserEvent + 4
    self.lblHit = None

  def addTarget(self, lbl, pos, vis = True, hidelbl = False, radius = 5, \
                colorIni = [1.0,0.0,0.0,0.6], colorFin = [0.0,1.0,0.0,0.6]):
    self.targets[lbl] = Target(radius, colorIni, colorFin)
    self.targets[lbl].setPos(pos, lbl)
    self.targets[lbl].visible(vis)
    self.renderer.AddActor(self.targets[lbl].actor)
    if not hidelbl:
      self.renderer.AddActor(self.targets[lbl].lblActor)
    if not self.firstLbl:
      # storing label of first target
      self.firstLbl = next(iter(self.targets))

  def resetTarget(self, lbl):
    self.targets[lbl].reset()

  def removeTarget(self, lbl):
    if lbl in self.targets:
      self.renderer.RemoveActor(self.targets[lbl].actor)
      self.renderer.RemoveActor(self.targets[lbl].lblActor)
      self.targets.pop(lbl)
      # updating label of first target, None if empty
      self.firstLbl = next(iter(self.targets), None)
      if self.firstLbl:
        self.targets[self.firstLbl].visible(True)
  
  def removeAllTargets(self):
    for t in self.targets.values():
      self.renderer.RemoveActor(t.actor)
      self.renderer.RemoveActor(t.lblActor)
    self.targets = {}
    self.firstLbl = None
    self.lblHit = None

  def allTargetsVisible(self, tof):
    for t in self.targets.values():
      t.visible(tof)

  @vtk.calldata_type(vtk.VTK_STRING)
  def onTargetFocus(self, caller, event, calldata):
    p = ast.literal_eval(calldata)  # parsing string into [pos_x, pos_y, pos_z]
    if self.proxiDetect:
      for k in self.targets:
        dist = Dist(p, self.targets[k].pos)
        if dist < self.proxiThresh:
          self.lblHit = k
          logging.info(f'   Target [{self.lblHit}]{np.around(self.targets[k].pos,2).tolist()} hit at {np.around(p,2).tolist()}! (d={dist:.2f})')
          # gathering the calldata
          p.insert(0, self.lblHit)
          self.InvokeEvent(self.targetHitEvent, str(p))
          break
    else:
      if self.firstLbl:
        logging.info(f'   Stopped for target [{self.firstLbl}]')
        self.lblHit = self.firstLbl
        # gathering the calldata
        p.insert(0, self.lblHit)
        self.InvokeEvent(self.targetHitEvent, str(p))

  @vtk.calldata_type(vtk.VTK_STRING)
  def onTargetIn(self, caller, event, calldata):
    cd = ast.literal_eval(calldata)
    if not isinstance(cd, list):
      cd = [cd]
    if self.lblHit:
      prog = max(min(cd[0], 1.0), 0)  # restrict progress between 0 and 1
      self.targets[self.lblHit].onTargetIn(prog)

  @vtk.calldata_type(vtk.VTK_STRING)
  def onTargetOut(self, caller, event = None, calldata = None):
    if self.lblHit:
      logging.info(f'   Target [{self.lblHit}] << Pointer out >>')
      self.targets[self.lblHit].onTargetOut()
      cd = self.lblHit
      self.lblHit = None # reset hit label
      self.InvokeEvent(self.targetOutEvent, str(cd))

  @vtk.calldata_type(vtk.VTK_STRING)
  def onTargetDone(self, caller, event, calldata):
    if self.lblHit:
      self.targets[self.lblHit].onTargetDone()
      p = ast.literal_eval(calldata)  # parsing string into [px, py, pz]
      logging.info(f'   Target [{self.lblHit}] == Done == with {np.around(p,2).tolist()}')
      cd = [self.lblHit] + p
      self.InvokeEvent(self.targetDoneEvent, str(cd))

  @vtk.calldata_type(vtk.VTK_STRING)
  def onTargetDoneOut(self, caller, event = None, calldata = None):
    if self.lblHit:
      logging.info(f'   Target [{self.lblHit}] <= Done and out =>')
      cd = self.lblHit
      self.lblHit = None # reset hit label
      self.InvokeEvent(self.targetDoneOutEvent, str(cd))


#
# Target class
#

class Target():

  def __init__(self, radius = 5, colorIni = [1.0,0.0,0.0,0.6],
                colorFin = [0.0,1.0,0.0,0.6]):
    self.pos = np.array([np.nan,np.nan,np.nan])
    self.radius = radius
    self.colorIni = np.array(colorIni)  # RGBA
    self.colorFin = np.array(colorFin)  # RGBA
    # sphere pipeline
    self.src = vtk.vtkSphereSource()
    self.src.SetPhiResolution(20)
    self.src.SetThetaResolution(20)
    self.src.SetRadius(radius)
    self.src.SetCenter(0,0,0)
    self.mapper = vtk.vtkPolyDataMapper()
    self.mapper.SetInputConnection(self.src.GetOutputPort())
    self.actor = vtk.vtkActor()
    self.actor.SetMapper(self.mapper)
    self.actor.GetProperty().SetColor(self.colorIni[:-1])
    self.actor.GetProperty().SetOpacity(self.colorIni[-1])
    self.actor.VisibilityOff()
    # label pipeline
    self.lblActor = vtk.vtkBillboardTextActor3D()
    self.lblActor.VisibilityOff()
    self.lblActor.GetTextProperty().SetColor(self.colorIni[:-1])
    self.lblActor.GetTextProperty().SetOpacity(1.0)
    self.lblActor.GetTextProperty().ShadowOn()
    self.lblActor.GetTextProperty().BoldOn()
    self.lblActor.GetTextProperty().SetFontSize(18)

  def reset(self):
    self.actor.GetProperty().SetColor(self.colorIni[:-1])
    self.actor.GetProperty().SetOpacity(self.colorIni[-1])
    self.lblActor.GetTextProperty().SetColor(self.colorIni[:-1])
    self.src.SetRadius(self.radius)

  def visible(self, tof):
    self.actor.SetVisibility(tof)
    self.lblActor.SetVisibility(tof)

  def setPos(self, pos, lbl):
    self.pos = pos
    self.src.SetCenter(self.pos)
    self.lblActor.SetInput(str(lbl))
    self.lblActor.SetPosition(self.pos)
    self.lblActor.SetDisplayOffset(0,25)

  def onTargetIn(self, prog):
    # prog gives the current progress of the target acquisition (between 0.0 and 1.0)
    color = (1-prog)*self.colorIni[:-1] + prog*self.colorFin[:-1]
    opacity = (1-prog)*self.colorIni[-1] + prog*self.colorFin[-1]
    self.src.SetRadius((1-0.5*prog)*self.radius)
    self.actor.GetProperty().SetColor(color)
    self.actor.GetProperty().SetOpacity(opacity)
    self.lblActor.GetTextProperty().SetColor(color)

  def onTargetOut(self):
    self.reset()

  def onTargetDone(self):
    self.actor.GetProperty().SetColor(self.colorFin[:-1])
    self.actor.GetProperty().SetOpacity(self.colorFin[-1])
    self.lblActor.GetTextProperty().SetColor(self.colorFin[:-1])
    self.src.SetRadius(self.radius)
