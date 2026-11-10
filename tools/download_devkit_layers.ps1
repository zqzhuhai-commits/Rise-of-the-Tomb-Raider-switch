param([Parameter(Mandatory=$true)][string]$CacheRoot)
$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Force -Path $CacheRoot | Out-Null
$tokenResponse=Invoke-RestMethod 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:devkitpro/devkita64:pull'
$manifest=Invoke-RestMethod 'https://registry-1.docker.io/v2/devkitpro/devkita64/manifests/sha256:82575ea78651b530b2e232bb3799cfd1fe331514e053d5f724bb4b28191fb79d' -Headers @{Authorization=('Bearer '+$tokenResponse.token);Accept='application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'}
$manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $CacheRoot 'manifest.json') -Encoding utf8
foreach ($layer in $manifest.layers) {
    $layerPath=Join-Path $cacheRoot ($layer.digest.Replace(':','-')+'.tgz')
    if (-not (Test-Path -LiteralPath $layerPath) -or (Get-Item -LiteralPath $layerPath).Length -ne $layer.size) {
        Write-Output ('Downloading layer '+$layer.digest+' bytes '+$layer.size)
        Invoke-WebRequest ('https://registry-1.docker.io/v2/devkitpro/devkita64/blobs/'+$layer.digest) -Headers @{Authorization=('Bearer '+$tokenResponse.token)} -OutFile $layerPath -TimeoutSec 120
    }
    $digest=(Get-FileHash -LiteralPath $layerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ('sha256:'+$digest -ne $layer.digest) { throw 'Layer checksum mismatch' }
    Write-Output ('Verified '+$layer.digest)
}

