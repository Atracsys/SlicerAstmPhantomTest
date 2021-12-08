import vtk
import logging
import numpy as np
import math
import random
import slicer  # for error popup
import itertools  # for combinations of divots
import json

#
# Single Point Measurement class
#

class SinglePointMeasurement(vtk.vtkObject):

  def __init__(self):
    self.acquiNumMax = 20 # some default value, but probably overwritten
    self.acquiNumChanged = vtk.vtkCommand.UserEvent + 1
    self.stats1Changed = vtk.vtkCommand.UserEvent + 2
    self.stats2Changed = vtk.vtkCommand.UserEvent + 3

  # Reset all stored values, including overall errors and stats
  def fullReset(self, gtPts, divot = None):
    self.gtPts = gtPts
    if divot:
      self.divot = divot
    else:
      self.divot = 1
    # stores the measurements for each location
    self.measurements = {}
    # stack of all performed measurements, not categorized by location
    self.allMeasurements = np.empty((0,3), float)
    self.precisionStats = {} # stores the precision stats for each location
    self.accuracyStats = {} # stores the accuracy stats for each location
    self.reset()

  # Reset for next sequence
  def reset(self):
    # reset current location
    self.curLoc = None
    # acquisition number
    self.acquiNum = 0

  def onDivDone(self, pos):
    self.acquiNum = self.acquiNum + 1
    self.measurements[self.curLoc] = np.append(self.measurements[self.curLoc],
      pos.reshape(1,-1), axis=0)
    self.InvokeEvent(self.acquiNumChanged, self.acquiNum)
    if self.acquiNum < self.acquiNumMax:
      logging.info(f"   {self.acquiNumMax - self.acquiNum} acquisition(s) left"
        f"for central divot #{self.divot}")
    else:
      self.allMeasurements = np.append(self.allMeasurements, self.measurements[self.curLoc], axis=0)
    self.updatePrecisionStats()
    self.updateAccuracyStats()

  def __accuracyStats(self, measurements):
    if len(measurements) > 0:
      avg = np.linalg.norm(np.mean(measurements, axis = 0) - self.gtPts[self.divot])
      maxerr = 0
      for m in measurements:
        maxerr = max(maxerr, np.linalg.norm(m-self.gtPts[self.divot]))
      return {'num':len(measurements), 'avg err':avg, 'max':maxerr}
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
      logging.info(f'¤¤¤¤¤¤ Accuracy ({s["num"]}): avg err = {s["avg err"]:.2f}, '
        f'max = {s["max"]:.2f} ¤¤¤¤¤¤')
      # and update global stats
      self.accuracyStats["ALL"] = self.__accuracyStats(self.allMeasurements)

  def __precisionStats(self, measurements):
    if len(measurements) > 0:
      # Compute largest distance between two measurements (span)
      span = 0.0
      for pair in itertools.combinations(measurements,2):
        span = max(np.linalg.norm(pair[0] - pair[1]), span)
      # Compute rms of all distances from mean
      avg = np.mean(measurements, axis=0)
      dists = [np.linalg.norm(m - avg) for m in measurements]
      rms = np.sqrt(np.mean(np.array(dists)**2))
      return {'num':len(measurements), 'span': span, 'rms': rms}
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
      logging.info(f'¤¤¤¤¤¤ Precision ({s["num"]}): span = {s["span"]:.2f}, rms = {s["rms"]:.2f} ¤¤¤¤¤¤')
      # and update global stats
      self.precisionStats["ALL"] = self.__precisionStats(self.allMeasurements)

#
# Rotation Measurement class
#

class RotationMeasurement(vtk.vtkObject):

  def __init__(self, axis = 0):
    self.angStep = 2.0 # degrees
    self.minAngle = -180
    self.maxAngle = 180
    self.rotAxis = axis # 0: roll, 1: pitch, 2: yaw
    self.__names = ["Roll", "Pitch", "Yaw"]
    self.rotAxisName = self.__names[self.rotAxis]
    self.fullReset()

  # Reset all measurements and stats
  def fullReset(self):
    # stores the measurements for each location
    self.measurements = {}
    # stack of all performed measurements, not categorized by location
    self.allMeasurements = np.empty((0,4), float)
    self.stats = {}
    self.reset()

  # Reset current sequence
  def reset(self):
    self.curLoc = None

  # Calculate stats on measurements
  def __stats(self, meas):
    if len(meas) > 0:
      def dist(a,b):
        return np.linalg.norm(a - b)
      # angle range (smallest and largest)
      rg = [min(meas[:,0]),max(meas[:,0])]
      # max distance between two samples (span)
      span = 0
      for pair in itertools.combinations(meas[:,1:], 2):
        span = max(dist(pair[0], pair[1]), span)
      # standard deviation and RMS of deviations
      avg = np.mean(meas[:,1:], axis=0)
      devs = [dist(m, avg) for m in meas[:,1:]]
      rms = np.sqrt(np.mean(np.array(devs)**2)) # should be same as std
      return {"num":len(meas), "rangeMin":rg[0], "rangeMax":rg[1],
        "span":span, "rms":rms}
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
      
      # and update global stats
      self.allMeasurements = np.append(self.allMeasurements, self.measurements[self.curLoc], axis = 0)
      self.stats["ALL"] = self.__stats(self.allMeasurements)

#
# Distances Measurement class
#

class DistMeasurement(vtk.vtkObject):

  def __init__(self):
    self.acquiNumChanged = vtk.vtkCommand.UserEvent + 1
    self.stats1Changed = vtk.vtkCommand.UserEvent + 2
    self.stats2Changed = vtk.vtkCommand.UserEvent + 3

  # Reset all stored values, including overall errors and stats
  def fullReset(self, gtPts, divotsToDo = None):
    self.gtPts = gtPts
    # stores the measurements for each location
    self.measurements = {}
    self.allDistErrors = [] # stores all the distance errors, without sorting by location
    self.distStats = {}
    self.allRegErrors = [] # stores all the registration errors, without sorting by location
    self.regStats = {}
    self.reset(divotsToDo)

  # Reset only for current sequence
  def reset(self, divotsToDo = None):
    if divotsToDo:
      self.divotsToDo = divotsToDo.copy() # copy not ref
    else:
      self.divotsToDo = list(self.gtPts.keys())
    self.curLoc = None
    self.currLbl = -1

  def onDivDone(self, pos):
    self.measurements[self.curLoc][self.currLbl] = pos
    self.divotsToDo.remove(self.currLbl)
    self.InvokeEvent(self.acquiNumChanged, len(self.measurements[self.curLoc]))
    self.updateDistStats()
    self.updateRegStats()
    logging.info(f'   {len(self.divotsToDo)} divots left = {self.divotsToDo}')

  def __stats(self, errors):
    if len(errors) > 0:
      return {'num':len(errors), 'mean':np.mean(errors), 'min':np.min(errors), \
        'max':np.max(errors), 'std':np.std(errors), 'rms':np.sqrt(np.mean(np.array(errors)**2))}
    else:
      return {'num':0, 'mean':0, 'min':0, 'max':0, 'std':0, 'rms':0}
        
  def updateDistStats(self):
    # Compute errors
    errors = []
    for kp in itertools.combinations(self.measurements[self.curLoc], 2):
      gtDist = np.linalg.norm(self.gtPts[kp[0]] - self.gtPts[kp[1]])
      ptrDist = np.linalg.norm(self.measurements[self.curLoc][kp[0]] -
        self.measurements[self.curLoc][kp[1]])
      errors.append(abs(gtDist - ptrDist))
    
    # Update the stats
    s = self.__stats(errors)
    if len(errors) > 0:
      logging.info(f'¤¤¤¤¤¤ Dist Errors ({s["num"]}): mean = {s["mean"]:.2f}, min = {s["min"]:.2f}, '
        f'max = {s["max"]:.2f}, std = {s["std"]:.2f}, RMS = {s["rms"]:.2f} ¤¤¤¤¤¤')
    self.InvokeEvent(self.stats1Changed, str(s))

    # if sequence over, store stats
    if len(self.divotsToDo) == 0 and len(errors) > 0:
      if self.curLoc:
        self.distStats[self.curLoc] = s
      # and update overall stats
      self.allDistErrors = self.allDistErrors + errors
      self.distStats["ALL"] = self.__stats(self.allDistErrors)

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
        errors.append(abs(np.linalg.norm(np.array(p1[0:3]) - self.gtPts[k])))

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
      # and update overall stats
      self.allRegErrors = self.allRegErrors + errors
      self.regStats["ALL"] = self.__stats(self.allRegErrors)
