<#
.SYNOPSIS
  Importa en este portátil las conversaciones exportadas con exportar-conversaciones.ps1.

.DESCRIPTION
  Descomprime el zip en <config>\projects\ (sin borrar nada de lo que ya hubiera). Después, en cada carpeta
  (misma ruta que en el portátil original), "claude --resume" muestra la conversación para retomarla.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\importar-conversaciones.ps1 -Zip E:\traspaso-conversaciones.zip
#>
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Zip)
$ErrorActionPreference = "Stop"

$config = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE ".claude" }
$projects = Join-Path $config "projects"
if (-not (Test-Path $projects)) { New-Item -ItemType Directory -Path $projects | Out-Null }

$temp = Join-Path $env:TEMP ("importar-" + [guid]::NewGuid())
Expand-Archive -Path $Zip -DestinationPath $temp
foreach ($c in Get-ChildItem $temp -Directory) {
    $dest = Join-Path $projects $c.Name
    if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest | Out-Null }
    Copy-Item (Join-Path $c.FullName "*") $dest -Recurse -Force
    Write-Host "  + $($c.Name)"
}
Remove-Item $temp -Recurse -Force
Write-Host "Listo. En cada carpeta: claude --resume (elige la conversación) y después /remote-control." -ForegroundColor Green
