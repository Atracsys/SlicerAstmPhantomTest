import numpy as np
import vtk, json
import itertools  # for combinations

#
# Position queue class
#

class PosQueue():
  def __init__(self, size):
    self.maxsz = size
    self.reset()

  def size(self):
    return len(self.queue)

  def reset(self):
    self.queue = []
    self.sum = np.array([0,0,0], dtype='float64')

  def push(self, pos):
    self.queue.insert(0, pos)
    self.sum += pos
    if len(self.queue) > self.maxsz:
      self.sum -= self.queue.pop()

  def strideMed(self, w1, w2):
    if len(self.queue) < self.maxsz:
      return float('inf')
    if (w1 <= 0 or w2 <=0 or w1+w2 > self.maxsz):
      w1 = 1
      w2 = 1
    firstPos = np.median(self.queue[:w1], axis=0)
    lastPos = np.median(self.queue[-w2:], axis=0)
    return np.linalg.norm(firstPos - lastPos) # distance between first and last positions in queue

  def strideMean(self, w1, w2):
    if len(self.queue) < self.maxsz:
      return float('inf')
    if (w1 <= 0 or w2 <=0 or w1+w2 > self.maxsz):
      w1 = 1
      w2 = 1
    firstPos = np.mean(self.queue[:w1], axis=0)
    lastPos = np.mean(self.queue[-w2:], axis=0)
    return np.linalg.norm(firstPos - lastPos) # distance between first and last positions in queue

  def stride(self):
    if len(self.queue) < self.maxsz:
      return float('inf')
    else:
      return np.linalg.norm(self.queue[0] - self.queue[-1]) # distance between first and last positions in queue
  
  def avg(self):
    return self.sum/len(self.queue)

#
# Reimplementation of vtkRenderer::ResetCameraScreenSpace
# (because it's not available in Slicer yet)

def ResetCameraScreenSpace(renderer):
  # Classic camera reset to ensure all props are visible
  bds = renderer.ComputeVisiblePropBounds()
  renderer.ResetCamera(bds)

  # Expand bounds (as in vtkRenderer::ExpandBounds, also not in Slicer yet)
  pt = [[bds[0],bds[2],bds[5],1.0], [bds[1],bds[2],bds[5],1.0], \
        [bds[1],bds[2],bds[4],1.0], [bds[0],bds[2],bds[4],1.0], \
        [bds[0],bds[3],bds[5],1.0], [bds[1],bds[3],bds[5],1.0], \
        [bds[1],bds[3],bds[4],1.0], [bds[0],bds[3],bds[4],1.0]]
  cam = renderer.GetActiveCamera()
  camMat = cam.GetModelTransformMatrix()
  for i in range(0,8):
    pt[i] = camMat.MultiplyPoint(pt[i])
  bmin = list(pt[0]).copy()
  bmax = list(pt[0]).copy()
  for i in range(0,8):
    for j in range(0,3):
      bmin[j] = min(bmin[j], pt[i][j])
      bmax[j] = max(bmax[j], pt[i][j])
  bds = [bmin[0], bmax[0], bmin[1], bmax[1], bmin[2], bmax[2]]

  # Compute the screen space bounding box
  xmin = vtk.VTK_DOUBLE_MAX
  ymin = vtk.VTK_DOUBLE_MAX
  xmax = vtk.VTK_DOUBLE_MIN
  ymax = vtk.VTK_DOUBLE_MIN
  for i in range(0,2):
    for j in range(0,2):
      for k in range(0,2):
        currentPoint = [bds[i], bds[j+2], bds[k+4], 1.0]
        renderer.SetWorldPoint(currentPoint)
        renderer.WorldToDisplay()
        currentPointDisplay = renderer.GetDisplayPoint()
        xmin = min(currentPointDisplay[0], xmin)
        xmax = max(currentPointDisplay[0], xmax)
        ymin = min(currentPointDisplay[1], ymin)
        ymax = max(currentPointDisplay[1], ymax)

  # Project the focal point in screen space
  fp = list(cam.GetFocalPoint())
  fp.append(1.0)
  renderer.SetWorldPoint(fp)
  renderer.WorldToDisplay()
  fpDisplay = renderer.GetDisplayPoint()

  # The focal point must be at the center of the box
  # So construct a box with fpDisplay at the center
  xCenterFocalPoint = int(fpDisplay[0])
  yCenterFocalPoint = int(fpDisplay[1])
  xCenterBox = int((xmin+xmax)/2)
  yCenterBox = int((ymin+ymax)/2)
  xDiff = 2 * (xCenterFocalPoint - xCenterBox)
  yDiff = 2 * (yCenterFocalPoint - yCenterBox)
  xMaxOffset = max(xDiff, 0)
  xMinOffset = min(xDiff, 0)
  yMaxOffset = max(yDiff, 0)
  yMinOffset = min(yDiff, 0)
  xmin += xMinOffset
  xmax += xMaxOffset
  ymin += yMinOffset
  ymax += yMaxOffset
  # Now the focal point is at the center of the box
  box = vtk.vtkRecti(int(xmin), int(ymin), int(xmax - xmin), int(ymax - ymin))
  # We let a 5% offset around the zoomed data
  size = renderer.GetSize()
  zf1 = size[0] / float(box.GetWidth())
  zf2 = size[1] / float(box.GetHeight())
  zoomFactor = min(zf1, zf2)
  # OffsetRatio will let a free space between the zoomed data
  # And the edges of the window
  cam.Zoom(zoomFactor*0.95)

#
# Class NumpyEncoder:
# which makes it possible to serialize a nd-array in nested dictionaries

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


#
# Distance calculation
#

def Dist(a,b):
  return np.linalg.norm(np.array(a) - np.array(b))

#
# RMS calculation
#

def RMS(samples):
  S = np.array(samples)
  return np.sqrt(np.mean(np.array(S)**2))

#
# Standard deviation of 3D coordinates
# based on distance
#

def stdDist(coords):
  S = np.array(coords)
  if S.ndim > 1:
    avg = np.mean(S, axis=0)
  else:
    avg = np.mean(S)
  devs = [Dist(s, avg) for s in S]
  return np.sqrt(np.mean(np.array(devs)**2))

#
# Span calculation
#

def Span(samples):
  # Compute largest distance between two samples
  span = 0.0
  for pair in itertools.combinations(np.array(samples),2):
    span = max(Dist(pair[0], pair[1]), span)
  return span
