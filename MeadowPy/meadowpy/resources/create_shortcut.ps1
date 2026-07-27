[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $ShortcutPath,

    [Parameter(Mandatory = $true)]
    [string] $AppDirectory
)

$ErrorActionPreference = "Stop"

$pythonwPath = Join-Path $AppDirectory ".venv\Scripts\pythonw.exe"
$launcherPath = Join-Path $AppDirectory "meadowpy\resources\launch.vbs"
$iconPath = Join-Path $AppDirectory "meadowpy\resources\icons\meadowpy.ico"

if (Test-Path -LiteralPath $pythonwPath -PathType Leaf) {
    $targetPath = $pythonwPath
    $arguments = "-m meadowpy"
}
else {
    $targetPath = $launcherPath
    $arguments = ""
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $AppDirectory
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Description = "Launch MeadowPy IDE"
$shortcut.Save()
