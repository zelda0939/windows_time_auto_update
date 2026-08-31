param(
    [Parameter(Mandatory=$true)]
    [string]$Commit1,

    [Parameter(Mandatory=$true)]
    [string]$Commit2
)

$ErrorActionPreference = "Stop"

try {
    # Get log with stats
    # Format: Hash | Author | Date | Subject | Body
    # Followed by stat
    $logOutput = git log --pretty=format:"%h|%an|%ad|%s|%b" --date=short --stat $Commit1..$Commit2
    
    # Also get a simple file list for easier parsing
    $fileList = git diff --name-status $Commit1 $Commit2

    Write-Host "=== GIT CHANGE SUMMARY ==="
    Write-Host "From: $Commit1"
    Write-Host "To:   $Commit2"
    Write-Host ""
    Write-Host "--- DETAILED LOG ---"
    Write-Host $logOutput
    Write-Host ""
    Write-Host "--- FILE CHANGES ---"
    Write-Host $fileList
    
} catch {
    Write-Error "Failed to retrieve git log: $_"
    exit 1
}
