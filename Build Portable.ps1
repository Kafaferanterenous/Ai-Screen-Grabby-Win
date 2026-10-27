$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$builder = (Get-Command pyinstaller.exe -ErrorAction Stop).Source
$buildRoot = Join-Path $project 'build_portable'
$dist = Join-Path $buildRoot 'dist'
$work = Join-Path $buildRoot 'work'
$spec = Join-Path $buildRoot 'spec'
$package = Join-Path $project 'portable_app'
$screenshots = Join-Path $package 'Screenshots'
$licenses = Join-Path $package 'licenses'
$pythonRoot = Split-Path -Parent (Split-Path -Parent $builder)
$pyInstallerInfo = Get-ChildItem -LiteralPath (Join-Path $pythonRoot 'lib\site-packages') -Directory -Filter 'pyinstaller-*.dist-info' | Sort-Object Name -Descending | Select-Object -First 1
if (-not $pyInstallerInfo) { throw 'PyInstaller license directory was not found' }

New-Item -ItemType Directory -Path $dist,$work,$spec,$package,$screenshots,$licenses -Force | Out-Null

& $builder --noconfirm --onefile --name Grabby --distpath $dist --workpath $work --specpath $spec (Join-Path $project 'grabby.py')
if ($LASTEXITCODE -ne 0) { throw 'Grabby CLI build failed' }

& $builder --noconfirm --onefile --windowed --name GrabbyGUI --distpath $dist --workpath $work --specpath $spec (Join-Path $project 'grabby_gui_launcher.py')
if ($LASTEXITCODE -ne 0) { throw 'Grabby GUI build failed' }

Copy-Item -LiteralPath (Join-Path $dist 'Grabby.exe') -Destination (Join-Path $package 'Grabby.exe') -Force
Copy-Item -LiteralPath (Join-Path $dist 'GrabbyGUI.exe') -Destination (Join-Path $package 'GrabbyGUI.exe') -Force
Copy-Item -LiteralPath (Join-Path $project 'PORTABLE_README.md') -Destination (Join-Path $package 'README.md') -Force
Copy-Item -LiteralPath (Join-Path $project 'LICENSE') -Destination (Join-Path $package 'LICENSE') -Force
Copy-Item -LiteralPath (Join-Path $project 'THIRD_PARTY_NOTICES.txt') -Destination (Join-Path $package 'THIRD_PARTY_NOTICES.txt') -Force
Copy-Item -LiteralPath (Join-Path $project 'assets\grabby-capture-navy.png') -Destination (Join-Path $screenshots 'Grabby-Navy.png') -Force
Copy-Item -LiteralPath (Join-Path $pythonRoot 'LICENSE.txt') -Destination (Join-Path $licenses 'Python-LICENSE.txt') -Force
Copy-Item -LiteralPath (Join-Path $pythonRoot 'tcl\tk8.6\license.terms') -Destination (Join-Path $licenses 'Tk-license.terms') -Force
Copy-Item -LiteralPath (Join-Path $pyInstallerInfo.FullName 'licenses\COPYING.txt') -Destination (Join-Path $licenses 'PyInstaller-COPYING.txt') -Force
Compress-Archive -Path (Join-Path $package '*') -DestinationPath (Join-Path $project 'Ai-Screen-Grabby-v0.5.0-portable.zip') -Force
Write-Output "Portable candidate: $package"
