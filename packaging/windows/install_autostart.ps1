# Cree un raccourci vers Zelploie.exe dans le dossier Demarrage de Windows,
# pour que l'app se lance automatiquement a l'ouverture de session (§7.6,
# confirme avec Zeli : app permanente + demarrage auto).
#
# Usage (apres `flet build windows`) :
#   .\install_autostart.ps1 -ExePath "C:\chemin\vers\build\windows\zelploie.exe"
#
# Pour desinstaller : supprimer le raccourci
#   %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Zelploie.lnk

param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath
)

if (-not (Test-Path $ExePath)) {
    Write-Error "Executable introuvable : $ExePath"
    exit 1
}

$startupFolder = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startupFolder "Zelploie.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = (Resolve-Path $ExePath).Path
$shortcut.WorkingDirectory = Split-Path (Resolve-Path $ExePath).Path
$shortcut.Description = "Zelploie - suivi strict de l'emploi du temps"
$shortcut.Save()

Write-Host "Raccourci de demarrage automatique cree : $shortcutPath"
Write-Host "Zelploie se lancera desormais a chaque ouverture de session Windows."
