param(
  [Parameter(Mandatory=$true)]
  [Alias('Platform')]
  [ValidateSet('opencode','codex','claude-code','cursor')]
  [string]$Target,
  [string]$InstallRoot
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$separator = [IO.Path]::PathSeparator
$existingPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = "$Root\runtime$separator$Root"
if ($existingPythonPath) { $env:PYTHONPATH += "$separator$existingPythonPath" }

$python = $null
$pythonArgs = @()
if (Get-Command python -ErrorAction SilentlyContinue) { $python = 'python' }
elseif (Get-Command python3 -ErrorAction SilentlyContinue) { $python = 'python3' }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $python = 'py'; $pythonArgs = @('-3') }
else { throw 'Python 3.10+ is required but python/python3/py was not found on PATH.' }

$cliArgs = @('-m','tu_runtime.cli','platform-doctor','--platform',$Target)
if ($InstallRoot) { $cliArgs += @('--target-root',$InstallRoot) }
$commandArgs = @($pythonArgs) + @($cliArgs)
& $python @commandArgs
exit $LASTEXITCODE
