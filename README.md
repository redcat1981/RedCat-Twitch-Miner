# RedCat Twitch Miner 2.0

A small integration layer around `Guliveer/twitch-miner-go` for one Twitch account (`small_redcat`).

## Target channels

- `v_craken_v`
- `fenriscreations`

## Enabled behavior

- Channel Points
- Channel Point bonuses
- Watch Streaks
- Twitch Drops
- Community Moments
- Raids

Disabled:

- Predictions
- Betting strategies
- Community Goals
- Followers mode

## RedCat raid shutdown

After Twitch actually awards raid points (`GAIN_FOR_RAID`), RedCat starts a 60-second grace period. The miner shuts down gracefully only if both target channels remain offline when the grace period expires.

If either target comes back online during the grace period, the pending shutdown is cancelled.

The integration uses the upstream miner's existing event flow and `context.Context` cancellation rather than `os.Exit`, so the normal miner cleanup path is preserved.

## Build

The repository intentionally does not copy the entire upstream project. The build scripts pin upstream to commit `6a5696a8e9954523588ed0aa9d3d34e8b3853da3`, copy the RedCat module into the upstream tree, apply the integration changes, run tests, and build the Windows x64 executable.

Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\tools\build_windows.ps1
```

The executable is written to `dist\RedCatTwitchMiner.exe`.

GitHub Actions performs the same reproducible build and uploads a Windows x64 artifact.

## Current stage

The raid-shutdown lifecycle integration is implemented. Point statistics are the next module: we will consume the upstream point-reason events (`WATCH`, `CLAIM`, `WATCH_STREAK`, `RAID`) and persist RedCat session/daily/channel totals without duplicating Twitch protocol handling.
