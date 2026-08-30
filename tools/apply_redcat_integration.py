from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream"


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Integration anchor not found: {path}: {old[:160]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


miner = UPSTREAM / "internal" / "miner" / "miner.go"
handler = UPSTREAM / "internal" / "miner" / "handler.go"
redcat_dst = UPSTREAM / "internal" / "redcat"
redcat_src = ROOT / "internal" / "redcat"

if not miner.exists() or not handler.exists():
    raise SystemExit("Upstream source is missing. Clone twitch-miner-go first.")

redcat_dst.mkdir(parents=True, exist_ok=True)
for src in redcat_src.glob("*.go"):
    (redcat_dst / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

replace(
    miner,
    '"github.com/Guliveer/twitch-miner-go/internal/pubsub"\n',
    '"github.com/Guliveer/twitch-miner-go/internal/pubsub"\n\t"github.com/Guliveer/twitch-miner-go/internal/redcat"\n',
)
replace(
    miner,
    '\truntime *runtimecfg.Twitch\n',
    '\truntime *runtimecfg.Twitch\n\n\tredcatShutdown *redcat.RaidShutdownManager\n\tredcatStats    *redcat.StatsStore\n',
)
replace(
    miner,
    '''\tparentCtx := ctx
\tg, ctx := errgroup.WithContext(ctx)
''',
    '''\tparentCtx := ctx

\t// RedCat uses a child context so delayed raid shutdown participates in the
\t// existing errgroup lifecycle instead of terminating the process abruptly.
\trunCtx, runCancel := context.WithCancel(ctx)
\tdefer runCancel()

\tredcatTargets := make([]string, 0, len(m.getStreamers()))
\tfor _, s := range m.getStreamers() {
\t\tredcatTargets = append(redcatTargets, s.Username)
\t}
\tm.redcatShutdown = redcat.NewRaidShutdownManager(
\t\tredcatTargets,
\t\tredcat.RaidShutdownConfig{
\t\t\tEnabled:                         true,
\t\t\tOnlyAfterRaid:                   true,
\t\t\tGracePeriod:                     60 * time.Second,
\t\t\tRequireAllTargetChannelsOffline: true,
\t\t},
\t\trunCancel,
\t)

\tvar statsErr error
\tm.redcatStats, statsErr = redcat.NewStatsStore("data/redcat/statistics.json")
\tif statsErr != nil {
\t\tm.log.Warn("Failed to initialize RedCat statistics", "error", statsErr)
\t}

\tg, ctx := errgroup.WithContext(runCtx)
''',
)

replace(
    handler,
    '"github.com/Guliveer/twitch-miner-go/internal/model"\n',
    '"github.com/Guliveer/twitch-miner-go/internal/model"\n\t"github.com/Guliveer/twitch-miner-go/internal/redcat"\n',
)
replace(
    handler,
    '''\t\t\tevent := mapReasonToEvent(reasonCode)
\t\t\tm.log.Event(ctx, event,
''',
    '''\t\t\tevent := mapReasonToEvent(reasonCode)
\t\t\tif m.redcatStats != nil {
\t\t\t\tvar reason redcat.PointReason
\t\t\t\tswitch event {
\t\t\t\tcase model.EventGainForWatch:
\t\t\t\t\treason = redcat.PointWatch
\t\t\t\tcase model.EventGainForClaim:
\t\t\t\t\treason = redcat.PointClaim
\t\t\t\tcase model.EventGainForWatchStreak:
\t\t\t\t\treason = redcat.PointWatchStreak
\t\t\t\tcase model.EventGainForRaid:
\t\t\t\t\treason = redcat.PointRaid
\t\t\t\t}
\t\t\t\tif reason != "" {
\t\t\t\t\tif err := m.redcatStats.AddPoints(username, reason, earned, time.Now()); err != nil {
\t\t\t\t\t\tm.log.Warn("Failed to save RedCat point statistics", "error", err)
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t\tif event == model.EventGainForRaid && m.redcatShutdown != nil {
\t\t\t\tm.redcatShutdown.OnRaidPointsReceived()
\t\t\t}
\t\t\tm.log.Event(ctx, event,
''',
)

print("RedCat integration applied successfully.")
