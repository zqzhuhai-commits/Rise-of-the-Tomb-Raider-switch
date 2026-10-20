# Upload the exact, locally downloaded research package. No token is requested by this script.
[CmdletBinding()]
param([string]$PackagePath)
$ErrorActionPreference = 'Stop'
$Repo = 'zqzhuhai-commits/Rise-of-the-Tomb-Raider-switch'
$Tag = 'v0.0.1-test'
$AssetName = 'ROTTR-Switch-test-package.zip'
$ExpectedHash = 'D701C4553912BF2EA3C17F83A4EC32AF8256A71E0D7ACA45038E87299EA0FA27'
$ExpectedSize = 32843815

function Find-Gh {
    $cmd = Get-Command gh -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidate = Join-Path $env:ProgramFiles 'GitHub CLI\gh.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return $null
}
$Gh = Find-Gh
if (-not $Gh) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'Install GitHub CLI from https://cli.github.com/ and run this script again.'
    }
    Write-Host 'Installing official GitHub CLI using winget...'
    & winget install --id GitHub.cli --exact --source winget
    if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI installation did not complete.' }
    $Gh = Find-Gh
    if (-not $Gh) { throw 'Restart PowerShell and run this script again so gh is on PATH.' }
}
if (-not $PackagePath) {
    $defaultPath = Join-Path ([Environment]::GetFolderPath('UserProfile')) "Downloads\$AssetName"
    if (Test-Path -LiteralPath $defaultPath) { $PackagePath = $defaultPath }
    else { $PackagePath = (Read-Host 'Paste the full path of ROTTR-Switch-test-package.zip').Trim().Trim('"') }
}
$PackagePath = (Resolve-Path -LiteralPath $PackagePath).Path
$LocalFile = Get-Item -LiteralPath $PackagePath
if ($LocalFile.Length -ne $ExpectedSize -or
    (Get-FileHash -LiteralPath $PackagePath -Algorithm SHA256).Hash -ne $ExpectedHash) {
    throw 'Package size or SHA256 mismatch. Select the original research test ZIP.'
}
# Stage the validated package with a fixed asset name even if the browser renamed it.
$Stage = Join-Path ([IO.Path]::GetTempPath()) ('rottr-release-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Stage | Out-Null
try {
    $AssetPath = Join-Path $Stage $AssetName
    Copy-Item -LiteralPath $PackagePath -Destination $AssetPath
    & $Gh auth status --hostname github.com
    if ($LASTEXITCODE -ne 0) {
        & $Gh auth login --hostname github.com --git-protocol https --web
        if ($LASTEXITCODE -ne 0) { throw 'GitHub authentication was not completed.' }
    }
    $PermissionText = & $Gh api "repos/$Repo" --jq '.permissions.push'
    if ($LASTEXITCODE -ne 0 -or ($PermissionText -join '').Trim() -ne 'true') {
        throw 'The active GitHub account cannot upload to the target repository.'
    }
    $ReleaseText = & $Gh release view $Tag --repo $Repo --json url,isDraft,isPrerelease,assets 2>$null
    if ($LASTEXITCODE -eq 0) {
        $Release = ($ReleaseText -join "`n") | ConvertFrom-Json
        if (-not $Release.isPrerelease) { throw 'The existing tag is not a prerelease; no changes were made.' }
        $Existing = @($Release.assets | Where-Object { $_.name -eq $AssetName })
        if ($Existing.Count -gt 0) {
            # Verify the existing bytes, rather than silently replacing a published asset.
            & $Gh release download $Tag --repo $Repo --pattern $AssetName --dir $Stage --clobber
            if ($LASTEXITCODE -ne 0) { throw 'Could not verify existing release asset.' }
            if ((Get-FileHash -LiteralPath $AssetPath -Algorithm SHA256).Hash -ne $ExpectedHash) {
                throw 'Existing release asset differs. It has not been overwritten.'
            }
        } else {
            & $Gh release upload $Tag $AssetPath --repo $Repo
            if ($LASTEXITCODE -ne 0) { throw 'Upload failed; rerun the script to resume.' }
        }
        if ($Release.isDraft) {
            & $Gh release edit $Tag --repo $Repo --draft=false
            if ($LASTEXITCODE -ne 0) { throw 'Asset uploaded, but draft publication failed.' }
        }
    } else {
        $Notes = 'Research compatibility test only. NRO and NSP were built and structurally checked; no Switch hardware testing has been performed. Gameplay, graphics, audio, saves and performance are unverified. NSP is a forwarder; copy the NRO and your own matching base-game assets to the SD card as described in README-zh.md. TU4 and DLC are not integrated. ZIP SHA256: ' + $ExpectedHash.ToLowerInvariant()
        & $Gh release create $Tag $AssetPath --repo $Repo --target main --prerelease --latest=false --title '0.0.1 - Initial compatibility test (UNTESTED)' --notes $Notes
        if ($LASTEXITCODE -ne 0) { throw 'Release upload failed. A partial draft may remain; rerun this script to resume.' }
    }
    $FinalText = & $Gh release view $Tag --repo $Repo --json url,isDraft,isPrerelease,assets
    if ($LASTEXITCODE -ne 0) { throw 'Could not verify final release state.' }
    $Final = ($FinalText -join "`n") | ConvertFrom-Json
    $Asset = @($Final.assets | Where-Object { $_.name -eq $AssetName -and $_.size -eq $ExpectedSize })
    if ($Final.isDraft -or -not $Final.isPrerelease -or $Asset.Count -ne 1) {
        throw 'Final release validation failed. Inspect the release before retrying.'
    }
    Write-Host 'Uploaded successfully:'
    Write-Host $Final.url
    Start-Process $Final.url
} finally {
    # Only the script-owned temporary staging directory is removed.
    Remove-Item -LiteralPath $Stage -Recurse -Force
}
