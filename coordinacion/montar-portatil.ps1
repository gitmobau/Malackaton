<#
.SYNOPSIS
  Recrea en otro portátil la estructura del equipo: coordinador + 4 worktrees + .venv + ECC.

.DESCRIPTION
  Deja exactamente la misma distribución que en el portátil de Maiki:
    <Raiz>\CLAUDE.md          (instrucciones del coordinador y de cada sesión, copiado de coordinacion\CLAUDE.md)
    <Raiz>\equipo\            (clon principal, rama main)
    <Raiz>\area-A-maiki\      (worktree, rama feat/A-betsson-web)
    <Raiz>\area-B-alejandro\  (worktree, rama feat/B-vision)
    <Raiz>\area-C-migue\      (worktree, rama feat/C-core)
    <Raiz>\area-D-guilli\     (worktree, rama feat/D-infra)
    <Raiz>\.venv\             (Python compartido con requirements.txt y Chromium de Playwright)
  Además instala el plugin ECC a nivel de usuario con los hooks en modo "standard".

  Usa la MISMA ruta raíz que en el portátil de Maiki (D:\MAIKI\Malackathon), para que:
    - funcionen las rutas de los documentos y del workflow de CI (VENV_PY);
    - se puedan retomar las conversaciones copiadas con coordinacion\importar-conversaciones.ps1.

  Se puede ejecutar varias veces: lo que ya existe se salta.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\montar-portatil.ps1
#>
[CmdletBinding()]
param(
    [string]$Raiz = "D:\MAIKI\Malackathon",
    [string]$RepoUrl = "https://github.com/gitmobau/Malackaton.git",
    [string]$Python = "",
    [switch]$SinEcc
)

$ErrorActionPreference = "Stop"
$Areas = @(
    @{ Carpeta = "area-A-maiki";     Rama = "feat/A-betsson-web" },
    @{ Carpeta = "area-B-alejandro"; Rama = "feat/B-vision" },
    @{ Carpeta = "area-C-migue";     Rama = "feat/C-core" },
    @{ Carpeta = "area-D-guilli";    Rama = "feat/D-infra" }
)
$script:Avisos = New-Object System.Collections.Generic.List[string]

function Write-Paso([string]$Texto) { Write-Host ""; Write-Host "==> $Texto" -ForegroundColor Cyan }
function Write-Ok([string]$Texto)   { Write-Host "    OK  $Texto" -ForegroundColor Green }
function Add-Aviso([string]$Texto)  { $script:Avisos.Add($Texto); Write-Host "    !!  $Texto" -ForegroundColor Yellow }
function Test-Comando([string]$Nombre) { return [bool](Get-Command $Nombre -ErrorAction SilentlyContinue) }
function Invoke-Git([string[]]$Argumentos) {
    & git @Argumentos
    if ($LASTEXITCODE -ne 0) { throw "Falló: git $($Argumentos -join ' ')" }
}

# ---------------------------------------------------------------------------
Write-Paso "Comprobando herramientas"
foreach ($c in @("git", "claude", "node")) {
    if (-not (Test-Comando $c)) { throw "No encuentro '$c'. Ejecuta antes setup-portatil.ps1 del repo (o instálalo) y abre una terminal nueva." }
    Write-Ok "$c disponible"
}
if (-not (Test-Comando "gh")) { Add-Aviso "No encuentro 'gh' (GitHub CLI). Instálalo con: winget install --id GitHub.cli -e" }

# ---------------------------------------------------------------------------
Write-Paso "Clon principal en $Raiz\equipo"
if (-not (Test-Path $Raiz)) { New-Item -ItemType Directory -Path $Raiz | Out-Null }
$Equipo = Join-Path $Raiz "equipo"
if (Test-Path (Join-Path $Equipo ".git")) {
    Invoke-Git @("-C", $Equipo, "fetch", "--all", "--prune")
    Write-Ok "Ya existía; ramas actualizadas"
} else {
    Invoke-Git @("clone", $RepoUrl, $Equipo)
    Write-Ok "Clonado"
}

# ---------------------------------------------------------------------------
Write-Paso "Worktrees por área"
foreach ($a in $Areas) {
    $ruta = Join-Path $Raiz $a.Carpeta
    $rama = $a.Rama
    if (Test-Path (Join-Path $ruta ".git")) {
        Write-Ok "$($a.Carpeta) ya existe"
        continue
    }
    & git -C $Equipo show-ref --verify --quiet "refs/heads/$rama"
    $local = ($LASTEXITCODE -eq 0)
    & git -C $Equipo show-ref --verify --quiet "refs/remotes/origin/$rama"
    $remota = ($LASTEXITCODE -eq 0)
    if ($local) {
        Invoke-Git @("-C", $Equipo, "worktree", "add", $ruta, $rama)
    } elseif ($remota) {
        Invoke-Git @("-C", $Equipo, "worktree", "add", "--track", "-b", $rama, $ruta, "origin/$rama")
    } else {
        Invoke-Git @("-C", $Equipo, "worktree", "add", "-b", $rama, $ruta, "origin/main")
        Add-Aviso "La rama $rama no estaba en GitHub: se creó desde main. ¿Subió el área su trabajo?"
    }
    Write-Ok "$($a.Carpeta) en $rama"
}

# ---------------------------------------------------------------------------
Write-Paso "CLAUDE.md de la raíz (coordinador y papel de cada sesión)"
$origenClaude = Join-Path $Equipo "coordinacion\CLAUDE.md"
if (Test-Path $origenClaude) {
    Copy-Item $origenClaude (Join-Path $Raiz "CLAUDE.md") -Force
    Write-Ok "Copiado a $Raiz\CLAUDE.md"
} else {
    Add-Aviso "No encuentro coordinacion\CLAUDE.md en main. Copia a mano el CLAUDE.md de la raíz del portátil de Maiki."
}

# ---------------------------------------------------------------------------
Write-Paso "Python compartido en $Raiz\.venv"
if (-not $env:PLAYWRIGHT_BROWSERS_PATH -and (Test-Path "D:\")) {
    $env:PLAYWRIGHT_BROWSERS_PATH = "D:\DevCache\ms-playwright"
    [Environment]::SetEnvironmentVariable("PLAYWRIGHT_BROWSERS_PATH", $env:PLAYWRIGHT_BROWSERS_PATH, "User")
}
$venvPy = Join-Path $Raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    if (-not $Python) {
        # Mismo Python que el .venv original (3.14); si no está, 3.12. Ver handoff/D-guilli.md.
        foreach ($v in @("-3.14", "-3.12")) {
            if (Test-Comando "py") {
                & py $v -c "import sys" 2>$null
                if ($LASTEXITCODE -eq 0) { $Python = "py $v"; break }
            }
        }
        if (-not $Python) { $Python = "python" }
    }
    Write-Host "    ..  Creando el venv con: $Python"
    $partes = $Python.Split(" ")
    $exeArgs = @()
    if ($partes.Count -gt 1) { $exeArgs = $partes[1..($partes.Count - 1)] }
    & $partes[0] @exeArgs -m venv (Join-Path $Raiz ".venv")
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el venv con '$Python'. Pasa -Python 'ruta\python.exe'." }
}
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r (Join-Path $Equipo "requirements.txt")
if ($LASTEXITCODE -ne 0) { Add-Aviso "pip install falló. Mira handoff/D-guilli.md (versión de Python y si hizo falta uv)." }
& $venvPy -m playwright install chromium
if ($LASTEXITCODE -ne 0) { Add-Aviso "No se pudo instalar Chromium de Playwright." }
Write-Ok "venv listo: $venvPy"

# ---------------------------------------------------------------------------
if (-not $SinEcc) {
    Write-Paso "Plugin ECC a nivel de usuario (hooks standard)"
    & claude plugin marketplace add https://github.com/affaan-m/ECC.git 2>$null
    & claude plugin install ecc@ecc --scope user
    if ($LASTEXITCODE -ne 0) { Add-Aviso "No se pudo instalar ecc@ecc. Dentro de Claude: /plugin, marketplace 'ecc', instalar 'ecc'." }
    $lista = (& claude plugin list --json) | Out-String | ConvertFrom-Json
    $ecc = @($lista | ForEach-Object { $_ }) | Where-Object { $_.id -eq "ecc@ecc" } | Select-Object -First 1
    if ($ecc -and $ecc.installPath) {
        $setup = Join-Path $ecc.installPath "scripts\setup.js"
        $env:CLAUDE_PLUGIN_ROOT = $ecc.installPath
        & node $setup --mode claude-plugin --scope user --hooks standard --yes --json
        if ($LASTEXITCODE -eq 0) { Write-Ok "ECC $($ecc.version) con hooks standard" }
        else { Add-Aviso "El asistente de ECC falló. Dentro de Claude ejecuta /ecc:configure-ecc (user, standard)." }
    } else {
        Add-Aviso "No veo ecc@ecc en 'claude plugin list'. Instálalo desde /plugin y después ejecuta /ecc:configure-ecc."
    }
}

# ---------------------------------------------------------------------------
Write-Paso "Resumen"
Write-Host "    Raíz:        $Raiz"
Write-Host "    Coordinador: $Raiz  (o $Equipo)"
foreach ($a in $Areas) { Write-Host ("    {0,-17} {1}" -f $a.Carpeta, $a.Rama) }
if ($script:Avisos.Count -gt 0) {
    Write-Host ""; Write-Host "Avisos:" -ForegroundColor Yellow
    foreach ($x in $script:Avisos) { Write-Host "  - $x" -ForegroundColor Yellow }
}
Write-Host ""
Write-Host "Siguiente:" -ForegroundColor Green
Write-Host "  1. Copia el .env (por USB o chat privado, NUNCA por git) en la carpeta de cada área que lo use."
Write-Host "  2. (Opcional) Retomar las conversaciones: coordinacion\importar-conversaciones.ps1 -Zip <ruta del zip>."
Write-Host "  3. Abre una terminal por sesión: cd <carpeta>; claude --resume (o claude) y /remote-control."
