<#
.SYNOPSIS
  Prepara el portátil para la Malachathon dejando todo en el disco D:.

.DESCRIPTION
  - Crea D:\Malackaton (repo), D:\DevCache (cachés), D:\DevTools (programas) y D:\ClaudeCode (config de Claude Code).
  - Guarda variables de entorno de usuario para que pip, npm, Playwright, Ollama, Hugging Face y Claude Code usen D:.
  - Instala lo que falte (Git, Python 3.12, Node.js LTS) con winget, intentando hacerlo en D:\DevTools.
  - Instala Claude Code con npm en D:\DevTools\npm-global.
  - Clona o actualiza el repo, crea el entorno virtual de Python e instala las dependencias y Chromium para Playwright.

  Se puede ejecutar varias veces: lo que ya está hecho se salta.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File D:\Malackaton\setup-portatil.ps1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File D:\Malackaton\setup-portatil.ps1 -ConOllama
#>
[CmdletBinding()]
param(
    [string]$Drive = "D:",
    [string]$RepoUrl = "https://github.com/gitmobau/Malackaton.git",
    [switch]$ConOllama,
    [switch]$SinClaudeCode
)

$ErrorActionPreference = "Stop"

$Drive     = $Drive.TrimEnd("\")
$Root      = "$Drive\Malackaton"
$Cache     = "$Drive\DevCache"
$Tools     = "$Drive\DevTools"
$ClaudeCfg = "$Drive\ClaudeCode"
$NpmGlobal = "$Tools\npm-global"

$script:Avisos = New-Object System.Collections.Generic.List[string]

function Write-Paso([string]$Texto) {
    Write-Host ""
    Write-Host "==> $Texto" -ForegroundColor Cyan
}

function Write-Ok([string]$Texto)    { Write-Host "    OK  $Texto" -ForegroundColor Green }
function Write-Info([string]$Texto)  { Write-Host "    ..  $Texto" }
function Add-Aviso([string]$Texto) {
    $script:Avisos.Add($Texto)
    Write-Host "    !!  $Texto" -ForegroundColor Yellow
}

function Update-PathDeSesion {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user    = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ";"
}

function Set-VariableUsuario([string]$Nombre, [string]$Valor) {
    $actual = [Environment]::GetEnvironmentVariable($Nombre, "User")
    if ($actual -ne $Valor) {
        [Environment]::SetEnvironmentVariable($Nombre, $Valor, "User")
        Write-Ok "$Nombre = $Valor"
    } else {
        Write-Info "$Nombre ya apuntaba a $Valor"
    }
    Set-Item -Path "Env:$Nombre" -Value $Valor
}

function Add-PathUsuario([string]$Carpeta) {
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $partes = @()
    if ($user) { $partes = $user.Split(";") | Where-Object { $_ } }
    if ($partes -notcontains $Carpeta) {
        [Environment]::SetEnvironmentVariable("Path", ((@($Carpeta) + $partes) -join ";"), "User")
        Write-Ok "Añadido al PATH de usuario: $Carpeta"
    }
    Update-PathDeSesion
}

function Test-Comando([string]$Nombre) {
    return [bool](Get-Command $Nombre -ErrorAction SilentlyContinue)
}

function Invoke-Externo([string]$Exe, [string[]]$Argumentos, [string]$Que) {
    & $Exe @Argumentos
    if ($LASTEXITCODE -ne 0) { throw "Falló: $Que (código $LASTEXITCODE)" }
}

function Install-ConWinget([string]$Id, [string]$Nombre, [string]$Carpeta) {
    if (-not (Test-Comando "winget")) {
        Add-Aviso "No encuentro winget. Instala $Nombre a mano y vuelve a ejecutar este script."
        return $false
    }
    Write-Info "Instalando $Nombre con winget en $Carpeta ..."
    & winget install --id $Id -e --silent --accept-package-agreements --accept-source-agreements --location $Carpeta
    if ($LASTEXITCODE -ne 0) {
        Write-Info "El instalador de $Nombre no aceptó la carpeta en D:. Lo instalo en su ubicación por defecto."
        & winget install --id $Id -e --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            Add-Aviso "No se pudo instalar $Nombre con winget (código $LASTEXITCODE). Instálalo a mano."
            return $false
        }
        Add-Aviso "$Nombre se instaló en su carpeta por defecto (normalmente C:), no en D:."
    }
    Update-PathDeSesion
    return $true
}

function Get-Python {
    # Devuelve el ejecutable de un Python 3.10+ real (evita el acceso directo de Microsoft Store).
    $candidatos = @()
    if (Test-Comando "py") { $candidatos += ,@("py", "-3") }
    if (Test-Comando "python") { $candidatos += ,@("python") }
    foreach ($c in $candidatos) {
        try {
            $exeArgs = @()
            if ($c.Count -gt 1) { $exeArgs = $c[1..($c.Count - 1)] }
            $salida = & $c[0] @exeArgs -c "import sys; print(sys.executable); print(sys.version_info >= (3, 10))" 2>$null
            if ($LASTEXITCODE -eq 0 -and $salida -and $salida[-1] -eq "True") { return $salida[0] }
        } catch { }
    }
    return $null
}

# ---------------------------------------------------------------------------
Write-Paso "Comprobando el disco $Drive"
if (-not (Test-Path "$Drive\")) {
    throw "No existe la unidad $Drive. Conecta el disco o ejecuta con -Drive X: (por ejemplo -Drive E:)."
}
foreach ($d in @($Cache, $Tools, $ClaudeCfg, $NpmGlobal)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}
Write-Ok "Carpetas base listas en $Drive"

# ---------------------------------------------------------------------------
Write-Paso "Variables de entorno para que todo use $Drive"
Set-VariableUsuario "CLAUDE_CONFIG_DIR"        $ClaudeCfg
Set-VariableUsuario "PIP_CACHE_DIR"            (Join-Path $Cache "pip")
Set-VariableUsuario "npm_config_cache"         (Join-Path $Cache "npm")
Set-VariableUsuario "PLAYWRIGHT_BROWSERS_PATH" (Join-Path $Cache "ms-playwright")
Set-VariableUsuario "HF_HOME"                  (Join-Path $Cache "huggingface")
Set-VariableUsuario "OLLAMA_MODELS"            (Join-Path $Cache "ollama-models")

# ---------------------------------------------------------------------------
Write-Paso "Git"
Update-PathDeSesion
if (-not (Test-Comando "git")) {
    [void](Install-ConWinget "Git.Git" "Git" (Join-Path $Tools "Git"))
}
if (Test-Comando "git") {
    Write-Ok (& git --version)
    $gitExe = (Get-Command git).Source
    $bash = Join-Path (Split-Path (Split-Path $gitExe -Parent) -Parent) "bin\bash.exe"
    if (Test-Path $bash) {
        Set-VariableUsuario "CLAUDE_CODE_GIT_BASH_PATH" $bash
    }
} else {
    throw "Git es imprescindible. Instálalo y vuelve a ejecutar el script."
}

# ---------------------------------------------------------------------------
Write-Paso "Python 3"
$python = Get-Python
if (-not $python) {
    [void](Install-ConWinget "Python.Python.3.12" "Python 3.12" (Join-Path $Tools "Python312"))
    $python = Get-Python
}
if ($python) {
    Write-Ok "Python: $python"
} else {
    throw "No encuentro Python 3.10 o superior. Instálalo (marca 'Add to PATH') y vuelve a ejecutar."
}

# ---------------------------------------------------------------------------
if (-not $SinClaudeCode) {
    Write-Paso "Node.js (para instalar Claude Code en $Drive)"
    if (-not (Test-Comando "npm")) {
        [void](Install-ConWinget "OpenJS.NodeJS.LTS" "Node.js LTS" (Join-Path $Tools "nodejs"))
    }
    if (Test-Comando "npm") {
        Write-Ok ("Node " + (& node --version))

        Write-Paso "Claude Code"
        Invoke-Externo "npm" @("config", "set", "prefix", $NpmGlobal) "configurar la carpeta global de npm"
        Add-PathUsuario $NpmGlobal
        $claudeEnD = Join-Path $NpmGlobal "claude.cmd"
        if (Test-Path $claudeEnD) {
            Write-Info "Claude Code ya está en $NpmGlobal; compruebo si hay versión nueva."
        }
        Invoke-Externo "npm" @("install", "-g", "@anthropic-ai/claude-code@latest") "instalar Claude Code"
        $donde = (Get-Command claude -ErrorAction SilentlyContinue)
        if ($donde) {
            Write-Ok ("claude: " + $donde.Source)
            if (-not $donde.Source.StartsWith($NpmGlobal, [StringComparison]::OrdinalIgnoreCase)) {
                Add-Aviso "Hay otra instalación de Claude Code antes en el PATH ($($donde.Source)). Se usará esa."
            }
        } else {
            Add-Aviso "Claude Code se instaló, pero 'claude' aún no está en el PATH. Abre una terminal nueva."
        }
    } else {
        Add-Aviso "Sin Node.js no puedo instalar Claude Code en $Drive. Instala Node.js LTS y vuelve a ejecutar."
    }
}

# ---------------------------------------------------------------------------
Write-Paso "Repositorio en $Root"
if (Test-Path (Join-Path $Root ".git")) {
    Write-Info "Ya existe; traigo los últimos cambios."
    & git -C $Root pull --ff-only
    if ($LASTEXITCODE -ne 0) { Add-Aviso "No pude actualizar el repo (¿cambios locales sin subir?). Sigo con lo que hay." }
} elseif ((Test-Path $Root) -and (Get-ChildItem $Root -Force | Select-Object -First 1)) {
    throw "$Root existe y no es un repositorio git. Muévelo o bórralo y vuelve a ejecutar."
} else {
    Invoke-Externo "git" @("clone", $RepoUrl, $Root) "clonar el repositorio"
}
Write-Ok "Repo listo"

# ---------------------------------------------------------------------------
Write-Paso "Entorno virtual de Python y dependencias"
$venv   = Join-Path $Root ".venv"
$venvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Invoke-Externo $python @("-m", "venv", $venv) "crear el entorno virtual"
}
Invoke-Externo $venvPy @("-m", "pip", "install", "--upgrade", "pip") "actualizar pip"
Invoke-Externo $venvPy @("-m", "pip", "install", "-r", (Join-Path $Root "requirements.txt")) "instalar requirements.txt"
Write-Ok "Dependencias instaladas en $venv"

Write-Paso "Chromium para Playwright (en $Cache\ms-playwright)"
Invoke-Externo $venvPy @("-m", "playwright", "install", "chromium") "instalar Chromium de Playwright"
Write-Ok "Chromium listo"

# ---------------------------------------------------------------------------
if ($ConOllama) {
    Write-Paso "Ollama (modelos en $Cache\ollama-models)"
    if (-not (Test-Comando "ollama")) {
        [void](Install-ConWinget "Ollama.Ollama" "Ollama" (Join-Path $Tools "Ollama"))
    }
    if (Test-Comando "ollama") { Write-Ok "Ollama instalado. Los modelos se guardarán en $env:OLLAMA_MODELS" }
}

# ---------------------------------------------------------------------------
Write-Paso "Resumen"
Write-Host "    Repo:              $Root"
Write-Host "    Python (venv):     $venvPy"
Write-Host "    Config de Claude:  $ClaudeCfg"
Write-Host "    Cachés:            $Cache"
if ($script:Avisos.Count -gt 0) {
    Write-Host ""
    Write-Host "Avisos:" -ForegroundColor Yellow
    foreach ($a in $script:Avisos) { Write-Host "  - $a" -ForegroundColor Yellow }
}
Write-Host ""
Write-Host "Listo. Abre una terminal NUEVA (para cargar las variables) y ejecuta:" -ForegroundColor Green
Write-Host "    cd $Root"
Write-Host "    .venv\Scripts\Activate.ps1"
Write-Host "    claude"
Write-Host "La primera vez, Claude Code te pedirá iniciar sesión con tu cuenta de Claude."
