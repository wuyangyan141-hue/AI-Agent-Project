# Copy DSAI5205 chapter PDFs into services/api/eval/corpus/dsai5205 for RAG eval.
param(
    [string]$SourceDir = "$env:USERPROFILE\Downloads\5205"
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Dest = Join-Path $Root 'services\api\eval\corpus\dsai5205'
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$map = @{
    'DSAI5205_Chapter3_2026.pdf' = 'DSAI5205_Chapter3_2026.pdf'
    'DSAI5205_Chapter4_2026 (1).pdf' = 'DSAI5205_Chapter4_2026.pdf'
    'DSAI5205_Chapter5_2026.pdf' = 'DSAI5205_Chapter5_2026.pdf'
    'DSAI5205_Chapter6.pdf' = 'DSAI5205_Chapter6.pdf'
}
foreach ($srcName in $map.Keys) {
    $src = Join-Path $SourceDir $srcName
    if (-not (Test-Path $src)) {
        Write-Warning "Missing $src - update -SourceDir or copy files manually."
        continue
    }
    Copy-Item -Force $src (Join-Path $Dest $map[$srcName])
    Write-Host "Copied $($map[$srcName])"
}
Write-Host "Eval corpus directory: $Dest"