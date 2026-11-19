param(
    [ValidateSet("offline", "configured")]
    [string]$Mode = "offline"
)

$ErrorActionPreference = "Stop"
$apiDir = Join-Path $PSScriptRoot "services\api"
$python = Join-Path $apiDir ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    python -m venv (Join-Path $apiDir ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create Python virtual environment." }
}

& $python -m pip install -r (Join-Path $apiDir "requirements-dev.txt") "langsmith>=0.3,<1"
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

if (-not $env:LANGSMITH_API_KEY) {
    $secret = Read-Host "Enter a NEW LangSmith API key (input hidden)" -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try {
        $env:LANGSMITH_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}
if (-not $env:LANGSMITH_API_KEY) { throw "LANGSMITH_API_KEY is required." }

$env:LANGSMITH_TRACING = "true"
$env:LANGSMITH_PROJECT = "doudou-rag-eval"
Push-Location $apiDir
try {
    & $python -m eval.langsmith_rag --mode $Mode
    if ($LASTEXITCODE -ne 0) { throw "RAG evaluation failed (exit code $LASTEXITCODE)." }
}
finally {
    Pop-Location
    Remove-Item Env:LANGSMITH_API_KEY -ErrorAction SilentlyContinue
}
