from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream"


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Integration anchor not found: {path}: {old[:120]!r}")
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
\n\t// RedCat uses a child context so delayed raid shutdown participates in the\n\t// existing errgroup lifecycle instead of terminating the process abruptly.\n\trunCtx, runCancel := context.WithCancel(ctx)\n\tdefer runCancel()\n\n\tredcatTargets := make([]string, 0, len(m.getStreamers()))\n\tfor _, s := range m.getStreamers() {\n\t\tredcatTargets = append(redcatTargets, s.Username)\n\t}\n\tm.redcatShutdown = redcat.NewRaidShutdownManager(\n\t\tredcatTargets,\n\t\tredcat.RaidShutdownConfig{\n\t\t\tEnabled:                         true,\n\t\t\tOnlyAfterRaid:                   true,\n\t\t\tGracePeriod:                     60 * time.Second,\n\t\t\tRequireAllTargetChannelsOffline: true,\n\t\t},\n\t\trunCancel,\n\t)\n\n\tvar statsErr error\n\tm.redcatStats, statsErr = redcat.NewStatsStore("data/redcat/statistics.json")\n\tif statsErr != nil {\n\t\tm.log.Warn("Failed to initialize RedCat statistics", "error", statsErr)\n\t}\n\n\tg, ctx := errgroup.WithContext(runCtx)\n''',
)

replace(
    handler,
    '"github.com/Guliveer/twitch-miner-go/internal/model"\n',
    '"github.com/Guliveer/twitch-miner-go/internal/model"\n\t"github.com/Guliveer/twitch-miner-go/internal/redcat"\n',
)
replace(
    handler,
    '''\t\tevent := mapReasonToEvent(reasonCode)\n\t\tm.log.Event(ctx, event,\n''',
    '''\t\tevent := mapReasonToEvent(reasonCode)\n\t\tif m.redcatStats != nil {\n\t\t\tvar reason redcat.PointReason\n\t\t\tswitch event {\n\t\t\tcase model.EventGainForWatch:\n\t\t\t\treason = redcat.PointWatch\n\t\t\tcase model.EventGainForClaim:\n\t\t\t\treason = redcat.PointClaim\n\t\t\tcase model.EventGainForWatchStreak:\n\t\t\t\treason = redcat.PointWatchStreak\n\t\t\tcase model.EventGainForRaid:\n\t\t\t\treason = redcat.PointRaid\n\t\t\t}\n\t\t\tif reason != "" {\n\t\t\t\tif err := m.redcatStats.AddPoints(streamer.Username, reason, earned, time.Now()); err != nil {\n\t\t\t\t\tm.log.Warn("Failed to save RedCat point statistics", "error", err)\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t\tif event == model.EventGainForRaid && m.redcatShutdown != nil {\n\t\t\tm.redcatShutdown.OnRaidPointsReceived()\n\t\t}\n\t\tm.log.Event(ctx, event,\n''',
)

print("RedCat integration applied successfully.")
