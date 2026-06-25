Set objShell  = CreateObject("WScript.Shell")
Set objFSO    = CreateObject("Scripting.FileSystemObject")

' Destination on the Desktop
strDesktop = objShell.SpecialFolders("Desktop")
strShortcut = strDesktop & "\NuanceAI.lnk"

' Create the shortcut
Set objSC = objShell.CreateShortcut(strShortcut)
objSC.TargetPath       = "powershell.exe"
objSC.Arguments        = "-ExecutionPolicy Bypass -NoProfile -File """ & "D:\MBD\start.ps1" & """"
objSC.WorkingDirectory = "D:\MBD"
objSC.WindowStyle      = 1
objSC.Description      = "NuanceAI – Start Backend + Frontend"

' Use PowerShell icon
objSC.IconLocation = "powershell.exe,0"

objSC.Save

MsgBox "NuanceAI shortcut created on your Desktop!" & Chr(13) & Chr(10) & "Double-click it to launch both servers.", 64, "NuanceAI Launcher"
