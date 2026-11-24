' Hidden launcher: run scripts\launch.ps1 without any console window.
Option Explicit

Dim fso, shell, root, command
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
shell.CurrentDirectory = root
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & root & "\scripts\launch.ps1"""
shell.Run command, 0, False
