import vtk
import logging
import numpy as np
import math
import random
import slicer  # for error popup
import itertools  # for combinations of divots
import json
from .Utils import Dist, rmsDist, RMS, Span, stdDist

#
# Single Point Measurement class
#

class SinglePointMeasurement(vtk.vtkObject):

  def __init__(self, refOri = 0):
    self.acquiNumMax = 20 # some default value, but probably overwritten
    self.refOri = refOri # 0: roll, 1: pitch, 2: yaw
    self.__names = ["Extreme Left", "Extreme Right", "Normal"]
    self.refOriName = self.__names[self.refOri]
    self.stats1Changed = vtk.vtkCommand.UserEvent + 1
    self.stats2Changed = vtk.vtkCommand.UserEvent + 2
    self.curLoc = None

  # Set calibrated points as ground truth
  def setGtPts(self, gtPts):
    self.gtPts = gtPts

  # Reset all stored values, including overall errors and stats
  def fullReset(self, gtPts, divot = None):
    self.curLoc = None
    self.setGtPts(gtPts)
    if divot:
      self.divot = divot
    else:
      self.divot = 1
    # stores the measurements for each location
    self.measurements = {}
    self.precisionStats = {} # stores the precision stats for each location
    self.accuracyStats = {} # stores the accuracy stats for each location
    self.reset()

  # Reset for current location
  def reset(self):
    logging.info(f'   Reset {self.refOriName} Single Point measurements for location [{self.curLoc}]')
    if self.curLoc:
      self.measurements[self.curLoc] = np.empty((0,3), float)
      self.precisionStats[self.curLoc] = None
      self.accuracyStats[self.curLoc] = None
    # acquisition number
    self.acquiNum = 0
    # average measured position, used for comparison in rotation tests
    self.avgPos = None

  def onDivDone(self, pos):
    self.acquiNum = self.acquiNum + 1
    self.measurements[self.curLoc] = np.append(self.measurements[self.curLoc],
      pos.reshape(1,-1), axis=0)
    if self.acquiNum < self.acquiNumMax:
      logging.info(f"   {self.acquiNumMax - self.acquiNum} acquisition(s) left "
        f"for central divot #{self.divot}")
    self.updatePrecisionStats()
    self.updateAccuracyStats()

  def __accuracyStats(self, measurements):
    if len(measurements) > 0:
      # update the average position
      self.avgPos = np.mean(measurements, axis = 0)
      # /!\ the length of the average error vector, not the average of errors
      err = Dist(self.avgPos, self.gtPts[self.divot])
      maxerr = 0
      for m in measurements:
        maxerr = max(maxerr, Dist(m, self.gtPts[self.divot]))
      return {'num':len(measurements), 'avg err':err, 'max':maxerr}
    else:
      return {'num':0, 'avg err':0, 'max':0}

  def updateAccuracyStats(self):
    # Update the stats
    s = self.__accuracyStats(self.measurements[self.curLoc])
    self.InvokeEvent(self.stats1Changed, str(s))

    # if sequence over, store stats
    if self.acquiNum == self.acquiNumMax and len(self.measurements[self.curLoc]) > 0:
      if self.curLoc:
        self.accuracyStats[self.curLoc] = s
      logging.info(f'¤¤¤¤¤¤ Single Point Accuracy [{self.refOriName}] ({s["num"]}): avg err = {s["avg err"]:.2f}, '
        f'max = {s["max"]:.2f} ¤¤¤¤¤¤')

  def __precisionStats(self, measurements):
    if len(measurements) > 0:
      # stdDist = RMS of deviations from mean
      return {'num':len(measurements), 'span': Span(measurements), 'rms': stdDist(measurements)}
    else:
      return {'num':0, 'span':0, 'rms':0}

  def updatePrecisionStats(self):
    # Update the stats
    s = self.__precisionStats(self.measurements[self.curLoc])
    self.InvokeEvent(self.stats2Changed, str(s))

    # if sequence over, store stats
    if self.acquiNum == self.acquiNumMax and len(self.measurements[self.curLoc]) > 0:
      if self.curLoc:
        self.precisionStats[self.curLoc] = s
      logging.info(f'¤¤¤¤¤¤ Single Point Precision [{self.refOriName}] ({s["num"]}): span = {s["span"]:.2f}, rms = {s["rms"]:.2f} ¤¤¤¤¤¤')

#
# Rotation Measurement class
#

class RotationMeasurement(vtk.vtkObject):

  def __init__(self, axis = 0):
    self.angStep = 0.25 # degrees
    self.minAngle = -180
    self.maxAngle = 180
    self.rotAxis = axis # 0: roll, 1: pitch, 2: yaw
    self.__names = ["Roll", "Pitch", "Yaw"]
    self.rotAxisName = self.__names[self.rotAxis]
    self.curLoc = None

  # Reset all measurements and stats
  def fullReset(self):
    self.curLoc = None
    # stores the measurements for each location
    self.measurements = {}
    self.stats = {}
    self.reset()

  # Reset for current location
  def reset(self):
    logging.info(f'   Reset {self.rotAxisName} Rotation measurements for location [{self.curLoc}]')
    if self.curLoc:
      self.measurements[self.curLoc] = np.empty((0,4), float)
      self.stats[self.curLoc] = None
    # base position for precision estimation, typically the averaged position
    # measured in the Single Point Measurement
    self.basePos = None

  # Calculate stats on measurements
  def __stats(self, meas):
    if len(meas) > 0 and self.basePos.any():
      # angle range (smallest and largest)
      rg = [min(meas[:,0]),max(meas[:,0])]
      # RMS of deviations from base position
      rms = rmsDist(meas[:,1:], self.basePos)
      return {"num":len(meas), "rangeMin":rg[0], "rangeMax":rg[1],
        "span":Span(meas[:,1:]), "rms":rms}
    else:
      return {"num":0, "rangeMin":0, "rangeMax":0, "span":0, "rms":0}

  # Update the current and global statistics
  def updateStats(self):
    if len(self.measurements[self.curLoc]) > 0:
      s = self.__stats(self.measurements[self.curLoc])
      if self.curLoc:
        self.stats[self.curLoc] = s

      logging.info(f'¤¤¤¤¤¤ Rotation [{self.rotAxisName}] ({s["num"]} samples): '
        f'Range <{s["rangeMin"]:.2f}°, {s["rangeMax"]:.2f}°>; Span {s["span"]:.2f}; '
        f'RMS {s["rms"]:.2f} ¤¤¤¤¤¤')

#
# Distances Measurement class
#

class DistMeasurement(vtk.vtkObject):

  def __init__(self):
    self.stats1Changed = vtk.vtkCommand.UserEvent + 1
    self.stats2Changed = vtk.vtkCommand.UserEvent + 2
    self.curLoc = None

  # Set calibrated points as ground truth
  def setGtPts(self, gtPts):
    self.gtPts = gtPts

  # Reset all stored values, including overall errors and stats
  def fullReset(self, gtPts, divotsToDo = None):
    self.curLoc = None
    self.setGtPts(gtPts)
    # stores the measurements for each location
    self.measurements = {}
    self.distStats = {}
    self.regStats = {}
    self.reset(divotsToDo)

  # Reset for current location
  def reset(self, divotsToDo = None):
    logging.info(f'   Reset Multi-point measurements for location {self.curLoc}')
    if divotsToDo:
      self.divotsToDo = divotsToDo.copy() # copy not ref
    else:
      # if no designated divots, use all of them !
      self.divotsToDo = list(self.gtPts.keys())
    if self.curLoc:
      self.measurements[self.curLoc] = {}
      self.distStats[self.curLoc] = {}
      self.regStats[self.curLoc] = {}
    self.currLbl = -1

  def onDivDone(self, pos):
    self.measurements[self.curLoc][self.currLbl] = pos
    self.divotsToDo.remove(self.currLbl)
    self.updateDistStats()
    self.updateRegStats()
    logging.info(f'   {len(self.divotsToDo)} divots left = {self.divotsToDo}')

  def __stats(self, errors):
    if len(errors) > 0:
      return {'num':len(errors), 'mean':np.mean(errors), 'min':np.min(errors), \
        'max':np.max(errors), 'rms':RMS(errors)}
    else:
      return {'num':0, 'mean':0, 'min':0, 'max':0, 'rms':0}
        
  def updateDistStats(self):
    # Compute errors
    errors = []
    for kp in itertools.combinations(self.measurements[self.curLoc], 2):
      gtDist = Dist(self.gtPts[kp[0]], self.gtPts[kp[1]])
      ptrDist = Dist(self.measurements[self.curLoc][kp[0]], self.measurements[self.curLoc][kp[1]])
      errors.append(abs(gtDist - ptrDist))
    
    # Update the stats
    s = self.__stats(errors)
    if len(errors) > 0:
      logging.info(f'¤¤¤¤¤¤ Dist Errors ({s["num"]}): mean = {s["mean"]:.2f}, min = {s["min"]:.2f}, '
        f'max = {s["max"]:.2f}, RMS = {s["rms"]:.2f} ¤¤¤¤¤¤')
    self.InvokeEvent(self.stats1Changed, str(s))

    # if sequence over, store stats
    if len(self.divotsToDo) == 0 and len(errors) > 0:
      if self.curLoc:
        self.distStats[self.curLoc] = s

  def updateRegStats(self):
    # Compute errors
    errors = []
    if len(self.measurements[self.curLoc]) > 1:
      ptsFrom = vtk.vtkPoints()
      ptsTo = vtk.vtkPoints()

      for k in self.measurements[self.curLoc]:
        ptsFrom.InsertNextPoint(self.measurements[self.curLoc][k])
        ptsTo.InsertNextPoint(self.gtPts[k])

      ldmkTransfo = vtk.vtkLandmarkTransform()
      ldmkTransfo.SetSourceLandmarks(ptsFrom)
      ldmkTransfo.SetTargetLandmarks(ptsTo)
      ldmkTransfo.SetModeToRigidBody()  # not similarity
      ldmkTransfo.Update()
      transfoMat = ldmkTransfo.GetMatrix()
      
      for k in self.measurements[self.curLoc]:
        p0 = np.append(self.measurements[self.curLoc][k], 1.0)  # adding 1.0 for homogeneous coords
        p1 = transfoMat.MultiplyDoublePoint(p0) # outputs a tuple
        errors.append(Dist(p1[0:3], self.gtPts[k]))

    # Update the stats
    s = self.__stats(errors)
    if len(errors) > 0:
      logging.info(f'¤¤¤¤¤¤ Reg Errors ({s["num"]}): mean = {s["mean"]:.2f}, min = {s["min"]:.2f}, '
        f'max = {s["max"]:.2f}, RMS = {s["rms"]:.2f} ¤¤¤¤¤¤')
    self.InvokeEvent(self.stats2Changed, str(s))

    # if sequence over, store stats
    if not len(self.divotsToDo) > 0:
      if self.curLoc:
        self.regStats[self.curLoc] = s
