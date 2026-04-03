Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
rootDir = fso.GetParentFolderName(fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName)))
WshShell.Run Chr(34) & rootDir & "\Run MeadowPy.bat" & Chr(34), 0, False
