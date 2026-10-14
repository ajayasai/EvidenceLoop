param(
    [string]$ModelPath,
    [string]$ModelId = 'qwen2.5-1.5b-onnx-int4-pilot',
    [int]$Port = 8091,
    [ValidateRange(1,8)][int]$Threads = 4,
    [switch]$FastForward
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.tools\local-inference\Scripts\python.exe'
if (-not $ModelPath) {
    $ModelPath = Join-Path $taskRoot '.runtime\qwen15-export\qwen-1.5b-onnx'
}
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Local ONNX environment is not installed. Read docs/FREE_INFERENCE.md.' }
if (-not (Test-Path -LiteralPath (Join-Path $ModelPath 'genai_config.json'))) { throw 'A verified ONNX model directory is required.' }
# Fixed loopback binding is enforced by the Python service. No downloads occur here.
$taskArguments = @((Join-Path $PSScriptRoot 'local_inference_server.py'), '--model-path', $ModelPath, '--model-id', $ModelId, '--port', $Port, '--threads', $Threads)
if ($FastForward) { $taskArguments += '--fast-forward' }
& $taskPython @taskArguments
exit $LASTEXITCODE
