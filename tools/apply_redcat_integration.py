from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream"


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Integration anchor not found: {path}: {old[:80]!r}")
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
    '\truntime *runtimecfg.Twitch\n\n\tredcatShutdown *redcat.RaidShutdownManager\n\tredcatRunCancel context.CancelFunc\n',
)
replace(
    miner,
    '\tparentCtx := ctx\n\tg, ctx := errgroup.WithContext(ctx)\n',
    '''\tparentCtx := ctx\n\n\t// RedCat integration uses a parent cancellation context so a requested\n\t// graceful shutdown can terminate the same errgroup used by the miner.\n\trunCtx, runCancel := context.WithCancel(ctx)\n\tm.redcatRunCancel = runCancel\n\tdefer func() {\n\t\tm.redcatRunCancel = nil\n\t\trunCancel()\n\t}()\n\n\tredcatTargets := make([]string, 0, len(m.getStreamers()))\n\tfor _, s := range m.getStreamers() {\n\t\tredcatTargets = append(redcatTargets, s.Username)\n\t}\n\tm.redcatShutdown = redcat.NewRaidShutdownManager(redcatTargets, redcat.RaidShutdownConfig{\n\t\tEnabled:                         true,\n\t\tOnlyAfterRaid:                   true,\n\t\tGracePeriod:                     60 * time.Second,\n\t\tRequireAllTargetChannelsOffline: true,\n\t})\n\n\tg, ctx := errgroup.WithContext(runCtx)\n''',
)
replace(
    miner,
    '\t\t\tstreamer.Mu.RUnlock()\n\n\t\t\tmu.Lock()\n',
    '''\t\t\tstreamer.Mu.RUnlock()\n\n\t\t\tif m.redcatShutdown != nil {\n\t\t\t\tif isOnline {\n\t\t\t\t\tm.redcatShutdown.OnStreamerOnline(streamer.Username)\n\t\t\t\t} else {\n\t\t\t\t\tm.redcatShutdown.OnStreamerOffline(streamer.Username)\n\t\t\t\t}\n\t\t\t}\n\n\t\t\tmu.Lock()\n''',
)
replace(
    handler,
    '\t\t\tevent := mapReasonToEvent(reasonCode)\n\t\t\tm.log.Event(ctx, event,\n',
    '''\t\t\tevent := mapReasonToEvent(reasonCode)\n\t\t\tif event == model.EventGainForRaid && m.redcatShutdown != nil {\n\t\t\t\tm.redcatShutdown.OnRaidPointsReceived(func() {\n\t\t\t\t\tm.log.Info("🛑 RedCat raid shutdown condition satisfied")\n\t\t\t\t\tif m.redcatRunCancel != nil {\n\t\t\t\t\t\tm.redcatRunCancel()\n\t\t\t\t\t}\n\t\t\t\t})\n\t\t\t}\n\t\t\tm.log.Event(ctx, event,\n''',
)
replace(
    handler,
    '\t\t"category", category)\n\n\tm.updateChatPresence(streamer, true)\n',
    '''\t\t"category", category)\n\n\tif m.redcatShutdown != nil {\n\t\tm.redcatShutdown.OnStreamerOnline(username)\n\t}\n\n\tm.updateChatPresence(streamer, true)\n''',
)
replace(
    handler,
    '\t}\n\n\tm.updateChatPresence(streamer, false)\n',
    '''\t}\n\n\tif m.redcatShutdown != nil {\n\t\tm.redcatShutdown.OnStreamerOffline(username)\n\t}\n\n\tm.updateChatPresence(streamer, false)\n''',
)

print("RedCat integration applied successfully.")
