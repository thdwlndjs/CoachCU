<#
Starts Personal Work Coach from this project directory.
Missing Python packages are installed from requirements.txt on first run.
#>
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $AppArguments
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = "py"
    $pythonPrefix = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = "python"
    $pythonPrefix = @()
} else {
    Write-Error "Python 3 was not found. Install Python 3.10 or newer, then run this script again."
    exit 1
}

& $pythonCommand @pythonPrefix -c "import PySide6, psutil" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing required Python packages..."
    & $pythonCommand @pythonPrefix -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Dependency installation failed."
        exit $LASTEXITCODE
    }
}

& $pythonCommand @pythonPrefix -m app.main @AppArguments
exit $LASTEXITCODE
