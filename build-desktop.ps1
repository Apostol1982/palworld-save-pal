# Build and Run Script for PALWorld Save Pal
Set-Location -Path $PSScriptRoot

$version = (Get-Content -Path ".\palworld_save_pal\__version__.py" | Select-String -Pattern "__version__").Line.Split('"')[1]
Write-Host "Building PALWorld Save Pal Desktop App version $version"


$distDir = ".\dist\psp-windows-$version"
if (Test-Path -Path $distDir) {
    Remove-Item -Path $distDir -Recurse -Force
}
New-Item -Path $distDir -ItemType Directory | Out-Null
Write-Host "Created $distDir"

# Build Front end

if (Test-Path -Path ".\build\") {
    Remove-Item -Path ".\build\" -Recurse -Force
}

if (Test-Path -Path ".\ui_build\") {
    Remove-Item -Path ".\ui_build\" -Recurse -Force
}


@"
PUBLIC_WS_URL=127.0.0.1:5174/ws
PUBLIC_DESKTOP_MODE=true
"@ | Set-Content -Path ".\ui\.env"

Set-Location -Path ".\ui"

# Function to check if a command exists
function Test-Command($command) {
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'stop'
    try {
        if (Get-Command $command) { return $true }
    }
    catch { return $false }
    finally { $ErrorActionPreference = $oldPreference }
}

# Determine which package manager to use
$packageManager = if (Test-Command 'bun') {
    'bun'
}
elseif (Test-Command 'npm') {
    'npm'
}
elseif (Test-Command 'yarn') {
    'yarn'
}
else {
    Write-Error "No suitable package manager found. Please install Bun, npm, or Yarn."
    exit 1
}

Write-Host "Using $packageManager as the package manager."

# Install dependencies
Write-Host "Installing dependencies..."
& $packageManager install

if ($LASTEXITCODE -ne 0) {
    Write-Error "$packageManager install failed. Exiting."
    exit 1
}

# Build the frontend
Write-Host "Building the frontend..."
& $packageManager run build

if ($LASTEXITCODE -ne 0) {
    Write-Error "$packageManager run build failed. Exiting."
    exit 1
}

Set-Location -Path ".."

Write-Host "Building exe..."

python setup.py build

if ($LASTEXITCODE -ne 0) {
    Write-Error "cx_Freeze build failed. Exiting."
    exit 1
}

Copy-Item -Path ".\build\exe.win-amd64-*\*" -Destination $distDir -Recurse -Force

Write-Host "Cleaning up..."
Remove-Item -Path ".\ui_build\" -Recurse -Force

Write-Host "Done building the desktop app."