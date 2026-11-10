param(
    [Parameter(Mandatory=$true)][string]$Sdk,
    [Parameter(Mandatory=$true)][string]$DepsInclude,
    [string]$DevkitPro = 'C:/devkitPro',
    [string]$CMake = 'cmake',
    [string]$Ninja = 'ninja',
    [string]$Python = 'python',
    [string]$BuildDir = '',
    [ValidateSet('Debug','Release','RelWithDebInfo')][string]$BuildType = 'Release',
    [int]$Jobs = 4
)
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $BuildDir) { $BuildDir = Join-Path $projectDir 'build/guest-windows' }
$Sdk = (Resolve-Path -LiteralPath $Sdk).Path.Replace('\','/')
$DepsInclude = (Resolve-Path -LiteralPath $DepsInclude).Path.Replace('\','/')
$DevkitPro = (Resolve-Path -LiteralPath $DevkitPro).Path.Replace('\','/')
$env:DEVKITPRO = $DevkitPro
$env:PYTHONUTF8 = '1'
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
# Use native Windows CMake/Ninja; the MSYS builds rewrite Windows paths.
if (-not (Test-Path -LiteralPath (Join-Path $projectDir 'generated/default/sources.cmake'))) {
    throw 'Run ReXGlue v0.10.0 codegen rottr_manifest.toml before compiling.'
}
Invoke-Checked $Python @((Join-Path $projectDir 'tools/verify_codegen.py'))
Invoke-Checked $Python @((Join-Path $projectDir 'tools/prepare_codegen.py'))
Invoke-Checked $Python @((Join-Path $projectDir 'tools/direct_calls.py'), '--sdk', $Sdk)
Invoke-Checked $CMake @('-S', $projectDir, '-B', $BuildDir, '-G', 'Ninja', "-DCMAKE_MAKE_PROGRAM=$Ninja", "-DCMAKE_BUILD_TYPE=$BuildType", "-DCMAKE_TOOLCHAIN_FILE=$projectDir/cmake/switch-devkitA64.cmake", "-DDEVKITPRO=$DevkitPro", "-DREXSDK_DIR=$Sdk", "-DREX_DEPS_INCLUDE=$DepsInclude")
Invoke-Checked $CMake @('--build', $BuildDir, '--target', 'rottr_guest', '-j', "$Jobs")
Invoke-Checked $Python @((Join-Path $projectDir 'tools/verify_guest.py'), '--objects', (Join-Path $BuildDir 'CMakeFiles/rottr_guest.dir/generated/default'), '--report', (Join-Path $BuildDir 'guest-build-result.json'))
