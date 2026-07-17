$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Python = Join-Path $ProjectRoot "terrain-model\.venv\Scripts\python.exe"
$NotebookScript = Join-Path $PSScriptRoot "tb_cough_xai_notebook.py"
$OutputDirectory = Join-Path $ProjectRoot "data\coda-tb\training-output"
$LogPath = Join-Path $OutputDirectory "training.log"
$ErrorLogPath = Join-Path $OutputDirectory "training.err.log"

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$cudaAvailable = & $Python -c "import torch; print(torch.cuda.is_available())"
if ($cudaAvailable.Trim() -ne "True") {
    throw "CUDA is not available in the terrain-model virtual environment."
}

$RunnerPath = Join-Path $OutputDirectory "training_runner.py"
$RunnerScript = @"
from pathlib import Path

notebook_path = Path(r"$NotebookScript")
source = notebook_path.read_text(encoding="utf-8")
source = "\n".join(
    "pass" if line.lstrip().startswith(("!", "%")) else line
    for line in source.splitlines()
)
exec(compile(source, str(notebook_path), "exec"), {"__name__": "__main__"})
"@
[IO.File]::WriteAllText(
    $RunnerPath,
    $RunnerScript,
    [Text.UTF8Encoding]::new($false)
)

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$Process = Start-Process `
    -FilePath $Python `
    -ArgumentList "`"$RunnerPath`"" `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $LogPath `
    -RedirectStandardError $ErrorLogPath `
    -PassThru

Write-Output "TRAINING_PID=$($Process.Id)"
Write-Output "TRAINING_LOG=$LogPath"
Write-Output "TRAINING_ERROR_LOG=$ErrorLogPath"
