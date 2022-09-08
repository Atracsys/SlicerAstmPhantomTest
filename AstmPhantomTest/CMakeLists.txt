#-----------------------------------------------------------------------------
set(MODULE_NAME AstmPhantomTest)

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  )

set(RESOURCES_FILES
  Resources/gt/SN0001a.txt
  Resources/gt/SN0001b.txt
  Resources/gt/SN0001c.txt
  Resources/models/ftk250_RAS.stl
  Resources/models/ftk500_RAS.stl
  Resources/models/phantom2018_RAS.stl
  Resources/models/phantom2022_RAS.stl
  Resources/models/pointer_RAS.stl
  Resources/models/simpPhantom_RAS.stl
  Resources/models/stk180_RAS.stl
  Resources/models/stk300_RAS.stl
  Resources/models/vega_RAS.stl
  Resources/ptr/hip7.txt
  Resources/ptr/navex.txt
  Resources/sounds/danger.wav
  Resources/sounds/done.wav
  Resources/sounds/error.wav
  Resources/sounds/plop.wav
  Resources/sounds/touchdown.wav
  Resources/wv/FusionTrack250.txt
  Resources/wv/FusionTrack500.txt
  Resources/wv/PolarisVega.txt
  Resources/wv/PolarisVegaExtend.txt
  Resources/wv/SpryTrack180.txt
  Resources/wv/SpryTrack300.txt
  )
  
set(PYTHON_CLASSES
  AstmPhantomTestClasses/__init__.py
  AstmPhantomTestClasses/Measurements.py
  AstmPhantomTestClasses/Phantom.py
  AstmPhantomTestClasses/Pointer.py
  AstmPhantomTestClasses/Targets.py
  AstmPhantomTestClasses/Utils.py
  AstmPhantomTestClasses/WorkingVolume.py
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  Resources/UI/${MODULE_NAME}.ui
  ${RESOURCES_FILES}
  ${PYTHON_CLASSES}
  )

#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  )
  