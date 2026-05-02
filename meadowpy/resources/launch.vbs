Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
rootDir = fso.GetParentFolderName(fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName)))
pythonwPath = rootDir & "\.venv\Scripts\pythonw.exe"

WshShell.CurrentDirectory = rootDir
If fso.FileExists(pythonwPath) Then
    WshShell.Run Chr(34) & pythonwPath & Chr(34) & " -m meadowpy", 0, False
Else
    WshShell.Run Chr(34) & rootDir & "\Run MeadowPy.bat" & Chr(34), 0, False
End If
