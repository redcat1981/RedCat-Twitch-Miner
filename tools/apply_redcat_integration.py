from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream"


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Integration anchor not found: {path}: {old[:100]!r}")
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
    '\truntime *runtimecfg.Twitch\n\n\tredcatShutdown *redcat.RaidShutdownManager\n',
)
replace(
    miner,
    '\tparentCtx := ctx\n\tg, ctx := errgroup.WithContext(ctx)\n',
    '''\tparentCtx := ctx

	// RedCat owns a child of the miner context. When the raid shutdown
	// condition is satisfied it cancels this child, allowing the existing
	// errgroup-based lifecycle to stop all background workers cleanly.
	runCtx, runCancel := context.WithCancel(ctx)
	defer runCancel()

	redcatTargets := make([]string, 0, len(m.getStreamers()))
	for _, s := range m.getStreamers() {
		redcatTargets = append(redcatTargets, s.Username)
	}
	m.redcatShutdown = redcat.NewRaidShutdownManager(
		redcatTargets,
		redcat.RaidShutdownConfig{
			Enabled:                         true,
			OnlyAfterRaid:                   true,
			GracePeriod:                     60 * time.Second,
			RequireAllTargetChannelsOffline: true,
		},
		runCancel,
	)

	g, ctx := errgroup.WithContext(runCtx)
''',
)
replace(
    miner,
    '\t\t\tstreamer.Mu.RUnlock()\n\n\t\t\tmu.Lock()\n',
    '''\t\t\tstreamer.Mu.RUnlock()

			if m.redcatShutdown != nil {
				if isOnline {
					m.redcatShutdown.OnStreamerOnline(streamer.Username)
				} else {
					m.redcatShutdown.OnStreamerOffline(streamer.Username)
				}
			}

		\tmu.Lock()
''',
)
replace(
    handler,
    '\t\t\tevent := mapReasonToEvent(reasonCode)\n\t\t\tm.log.Event(ctx, event,\n',
    '''\t\t\tevent := mapReasonToEvent(reasonCode)
		if event == model.EventGainForRaid && m.redcatShutdown != nil {
			m.redcatShutdown.OnRaidPointsReceived()
		}
		m.log.Event(ctx, event,
''',
)
replace(
    handler,
    '\t\t"category", category)\n\n\tm.updateChatPresence(streamer, true)\n',
    '''\t\t"category", category)

	if m.redcatShutdown != nil {
		m.redcatShutdown.OnStreamerOnline(username)
	}

	m.updateChatPresence(streamer, true)
''',
)
replace(
    handler,
    '\t}\n\n\tm.updateChatPresence(streamer, false)\n',
    '''\t}

	if m.redcatShutdown != nil {
		m.redcatShutdown.OnStreamerOffline(username)
	}

	m.updateChatPresence(streamer, false)
''',
)

print("RedCat integration applied successfully.")
