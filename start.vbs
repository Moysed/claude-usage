' Launch the Claude Usage widget with no console window.
' Double-click this file to run. Drop a shortcut to it in shell:startup to auto-run at login.
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.Run "pythonw """ & dir & "\claude_usage.py""", 0, False
