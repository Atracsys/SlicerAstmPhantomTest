#-----------------------------------------------------------------------------
set(MODULE_NAME AstmPhantomTest)

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  )

file(GLOB_RECURSE RESOURCES_FILES "Resources/*")
file(GLOB_RECURSE PYTHON_CLASSES "AstmPhantomTestClasses/*")

set(MODULE_PYTHON_RESOURCES
  ${RESOURCES_FILES}
  ${PYTHON_CLASSES}
  )

#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  )
  