$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Upstream = Join-Path $Root 'upstream'
$UpstreamCommit = '6a5696a8e9954523588ed0aa9d3d34e8b3853da3'

Write-Host '=== RedCat Twitch Miner 2.0 build ===' -ForegroundColor Cyan
Write-Host "Upstream: Guliveer/twitch-miner-go @ $UpstreamCommit"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required.' }
if (-not (Get-Command go -ErrorAction SilentlyContinue)) { throw 'Go 1.25+ is required.' }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python 3 is required.' }

if (Test-Path $Upstream) {
    Remove-Item $Upstream -Recurse -Force
}

git clone https://github.com/Guliveer/twitch-miner-go.git $Upstream
git -C $Upstream checkout --detach $UpstreamCommit

python (Join-Path $Root 'tools/apply_redcat_integration.py')

gofmt -w (Join-Path $Upstream 'internal/redcat/*.go') (Join-Path $Upstream 'internal/miner/miner.go') (Join-Path $Upstream 'internal/miner/handler.go')

go -C $Upstream test ./internal/redcat

$Output = Join-Path $Root 'dist/RedCatTwitchMiner.exe'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Output) | Out-Null
$env:GOOS = 'windows'
$env:GOARCH = 'amd64'
$env:CGO_ENABLED = '0'
go -C $Upstream build -trimpath -ldflags '-s -w' -o $Output ./cmd/twitch-miner-go

Copy-Item (Join-Path $Root 'configs/small_redcat.yaml') (Join-Path $Root 'dist/small_redcat.yaml') -Force

Write-Host ''
Write-Host "BUILD OK: $Output" -ForegroundColor Green
