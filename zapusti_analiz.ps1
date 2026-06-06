$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python .\scripts\run_agentic_pipeline.py --auto-install --start-status --use-wsl @args
