<#
.SYNOPSIS
  Empaqueta las conversaciones de Claude Code del coordinador y de las 4 áreas para llevarlas a otro portátil.

.DESCRIPTION
  Claude Code guarda cada conversación en <config>\projects\<ruta-de-la-carpeta-codificada>\.
  Este script mete en un zip las carpetas de D:\MAIKI\Malackathon y de sus subcarpetas (equipo, area-*).
  En el portátil nuevo, con la MISMA ruta raíz, se importan con importar-conversaciones.ps1 y se retoman con "claude --resume".

  AVISO: las conversaciones pueden contener lo que se haya escrito en el chat. El zip va por USB o por un canal
  privado, NUNCA a git. Ejecútalo cuando las 4 áreas hayan dicho "listo para migrar", para no cortar una sesión a medias.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\exportar-conversaciones.ps1 -Destino D:\traspaso-conversaciones.zip
#>
[CmdletBinding()]
param(
    [string]$Raiz = "D:\MAIKI\Malackathon",
    [string]$Destino = "D:\traspaso-conversaciones.zip"
)
$ErrorActionPreference = "Stop"

$config = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $env:USERPROFILE ".claude" }
$projects = Join-Path $config "projects"
# Claude Code codifica la ruta cambiando ":", "\" y "/" por "-": D:\MAIKI\Malackathon -> D--MAIKI-Malackathon
$prefijo = ($Raiz -replace '[:\\/]', '-')
$carpetas = Get-ChildItem $projects -Directory | Where-Object { $_.Name -eq $prefijo -or $_.Name -like "$prefijo-*" }
if (-not $carpetas) { throw "No hay conversaciones para $Raiz en $projects" }

$temp = Join-Path $env:TEMP ("traspaso-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $temp | Out-Null
foreach ($c in $carpetas) {
    Copy-Item $c.FullName (Join-Path $temp $c.Name) -Recurse
    Write-Host "  + $($c.Name)"
}
if (Test-Path $Destino) { Remove-Item $Destino -Force }
Compress-Archive -Path (Join-Path $temp "*") -DestinationPath $Destino
Remove-Item $temp -Recurse -Force
Write-Host "Listo: $Destino. Llévalo por USB o canal privado y ejecuta importar-conversaciones.ps1 en el portátil nuevo." -ForegroundColor Green
