; DesktopPilot AI — NSIS installer customisation
; Automatically closes the running app before installing so the user
; never sees the "Retry" dialog caused by locked files.

!macro preInit
  ; Kill the running DesktopPilot AI process (gracefully via taskkill)
  ; before the installer tries to overwrite any files.
  nsExec::ExecToLog 'taskkill /f /im "DesktopPilot AI.exe"'
  ; Also kill the bundled agent in case it is still running
  nsExec::ExecToLog 'taskkill /f /im "desktoppilot-agent.exe"'
  ; Short pause so Windows releases the file locks
  Sleep 1500
!macroend
