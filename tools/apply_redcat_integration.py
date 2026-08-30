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

# --- miner.go: import, fields, lifecycle/context, initial status ---
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

	// RedCat uses a child context so delayed raid shutdown participates in the
	// existing errgroup lifecycle instead of terminating the process abruptly.
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

	var statsErr error
	m.redcatStats, statsErr = redcat.NewStatsStore("data/redcat/statistics.json")
	if statsErr != nil {
		m.log.Warn("Failed to initialize RedCat statistics", "error", statsErr)
	}

	g, ctx := errgroup.WithContext(runCtx)
''',
)
replace(
    miner,
    '''\t\t\tstreamer.Mu.RUnlock()

\t\t\tmu.Lock()
''',
    '''\t\t\tstreamer.Mu.RUnlock()

			if m.redcatShutdown != nil {
				if isOnline {
					m.redcatShutdown.OnStreamerOnline(streamer.Username)
				} else {
					m.redcatShutdown.OnStreamerOffline(streamer.Username)
				}
			}

			mu.Lock()
''',
)

# --- handler.go: import and event hooks ---
replace(
    handler,
    '"github.com/Guliveer/twitch-miner-go/internal/model"\n',
    '"github.com/Guliveer/twitch-miner-go/internal/model"\n\t"github.com/Guliveer/twitch-miner-go/internal/redcat"\n',
)
replace(
    handler,
    '''\t\tevent := mapReasonToEvent(reasonCode)
\t\tm.log.Event(ctx, event,
''',
    '''\t\tevent := mapReasonToEvent(reasonCode)
		if m.redcatStats != nil {
			var reason redcat.PointReason
			switch event {
			case model.EventGainForWatch:
				reason = redcat.PointWatch
			case model.EventGainForClaim:
				reason = redcat.PointClaim
			case model.EventGainForWatchStreak:
				reason = redcat.PointWatchStreak
			case model.EventGainForRaid:
				reason = redcat.PointRaid
			}
			if err := m.redcatStats.AddPoints(streamer.Username, reason, earned, time.Now()); err != nil {
				m.log.Warn("Failed to save RedCat point statistics", "error", err)
			}
		}
		if event == model.EventGainForRaid && m.redcatShutdown != nil {
			m.redcatShutdown.OnRaidPointsReceived()
		}
		m.log.Event(ctx, event,
''',
)
replace(
    handler,
    '''\tif err := m.twitch.JoinRaid(ctx, raidID); err != nil {
\t\tm.log.Warn("Failed to join raid",
\t\t\t"streamer", username, "raid_id", raidID, "error", err)
\t}
''',
    '''\tif err := m.twitch.JoinRaid(ctx, raidID); err != nil {
\t\tm.log.Warn("Failed to join raid",
\t\t\t"streamer", username, "raid_id", raidID, "error", err)
\t} else if m.redcatStats != nil {
\t\tif err := m.redcatStats.AddRaid(); err != nil {
\t\t\tm.log.Warn("Failed to save RedCat raid statistics", "error", err)
\t\t}
\t}
''',
)
replace(
    handler,
    '''\tif err := m.twitch.ClaimMoment(ctx, momentID); err != nil {
\t\tm.log.Warn("Failed to claim moment",
\t\t\t"streamer", username, "moment_id", momentID, "error", err)
\t}
''',
    '''\tif err := m.twitch.ClaimMoment(ctx, momentID); err != nil {
\t\tm.log.Warn("Failed to claim moment",
\t\t\t"streamer", username, "moment_id", momentID, "error", err)
\t} else if m.redcatStats != nil {
\t\tif err := m.redcatStats.AddMoment(); err != nil {
\t\t\tm.log.Warn("Failed to save RedCat moment statistics", "error", err)
\t\t}
\t}
''',
)
replace(
    handler,
    '''\tm.log.Event(ctx, model.EventStreamerOnline,
\t\t"Stream online",
\t\t"streamer", username,
\t\t"category", category)

\tm.updateChatPresence(streamer, true)
''',
    '''\tm.log.Event(ctx, model.EventStreamerOnline,
\t\t"Stream online",
\t\t"streamer", username,
\t\t"category", category)

	if m.redcatShutdown != nil {
		m.redcatShutdown.OnStreamerOnline(username)
	}

	m.updateChatPresence(streamer, true)
''',
)
replace(
    handler,
    '''\tm.updateChatPresence(streamer, false)
}

func (m *Miner) handleViewCount''',
    '''\tif m.redcatShutdown != nil {
		m.redcatShutdown.OnStreamerOffline(username)
	}

	m.updateChatPresence(streamer, false)
}

func (m *Miner) handleViewCount''',
)

print("RedCat integration applied successfully.")
