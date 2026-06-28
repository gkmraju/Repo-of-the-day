Set-Location $PSScriptRoot

Write-Host "=== Repo Of The Day — Auto Push ===" -ForegroundColor Cyan

# Switch back to HTTPS (in case SSH was set)
git remote set-url origin https://github.com/gkmraju/Repo-of-the-day.git
Write-Host "[1] Remote set to HTTPS" -ForegroundColor Green

# Try flushing DNS cache
Write-Host "[2] Flushing DNS cache..." -ForegroundColor Yellow
ipconfig /flushdns | Out-Null

# Try to resolve github.com using Google DNS
Write-Host "[3] Testing connectivity to github.com..." -ForegroundColor Yellow
try {
    $ip = (Resolve-DnsName -Name "github.com" -Server "8.8.8.8" -ErrorAction Stop |
           Where-Object { $_.Type -eq "A" } |
           Select-Object -First 1).IPAddress
    Write-Host "    Resolved github.com -> $ip via 8.8.8.8" -ForegroundColor Green
} catch {
    Write-Host "    Warning: DNS resolution test failed. Trying push anyway..." -ForegroundColor Yellow
}

# Retry push up to 5 times
$success = $false
for ($i = 1; $i -le 5; $i++) {
    Write-Host "[4.$i] Pushing to GitHub (attempt $i/5)..." -ForegroundColor Yellow
    git push origin main 2>&1
    if ($LASTEXITCODE -eq 0) {
        $success = $true
        break
    }
    if ($i -lt 5) {
        Write-Host "    Retrying in 5 seconds..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }
}

if ($success) {
    Write-Host ""
    Write-Host "SUCCESS! All commits pushed to GitHub." -ForegroundColor Green
    Write-Host "https://github.com/gkmraju/Repo-of-the-day" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "Push failed after 5 attempts." -ForegroundColor Red
    Write-Host "Your 2 commits are saved locally. Try again when network is stable." -ForegroundColor Yellow
}

Write-Host ""
Read-Host "Press Enter to close"
