#-----------------------------------------------------------------------------
set(MODULE_NAME AstmPhantomTest)

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  )

file(GLOB RESOURCES_FILES
  "Resources/gt/*.txt"
  "Resources/models/*.stl"
  "Resources/ptr/*.txt"
  "Resources/sounds/*.wav"
  "Resources/wv/*.txt"
  "Resources/*.txt"
  )
file(GLOB PYTHON_CLASSES
  "AstmPhantomTestClasses/*.py"
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
  