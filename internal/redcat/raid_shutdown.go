package redcat

import (
	"context"
	"sync"
	"time"
)

// RaidShutdownConfig controls the optional shutdown-after-raid behavior.
type RaidShutdownConfig struct {
	Enabled                         bool
	OnlyAfterRaid                   bool
	GracePeriod                     time.Duration
	RequireAllTargetChannelsOffline bool
}

// RaidShutdownManager tracks target channel state and arms a delayed,
// graceful shutdown only after Twitch confirms that raid points were awarded.
// The shutdown callback is supplied once by the miner lifecycle, avoiding any
// direct dependency on the upstream Miner type.
type RaidShutdownManager struct {
	mu sync.Mutex

	targets map[string]bool
	cfg     RaidShutdownConfig

	raidPending bool
	generation  uint64

	shutdown func()
	cancel   context.CancelFunc
}

// NewRaidShutdownManager creates a manager for the supplied target channels.
func NewRaidShutdownManager(targets []string, cfg RaidShutdownConfig, shutdown func()) *RaidShutdownManager {
	if cfg.GracePeriod <= 0 {
		cfg.GracePeriod = 60 * time.Second
	}

	states := make(map[string]bool, len(targets))
	for _, target := range targets {
		states[target] = false
	}

	return &RaidShutdownManager{
		targets:  states,
		cfg:      cfg,
		shutdown: shutdown,
	}
}

// OnStreamerOnline marks a target channel online and cancels any pending
// shutdown. A channel coming back during the grace period is enough to keep
// the miner alive.
func (m *RaidShutdownManager) OnStreamerOnline(username string) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if _, ok := m.targets[username]; !ok {
		return
	}

	m.targets[username] = true
	m.cancelLocked()
}

// OnStreamerOffline marks a target channel offline. It does not initiate a
// shutdown by itself; shutdown is only armed after raid points are confirmed.
func (m *RaidShutdownManager) OnStreamerOffline(username string) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if _, ok := m.targets[username]; !ok {
		return
	}

	m.targets[username] = false
}

// OnRaidPointsReceived confirms that Twitch actually awarded raid points.
func (m *RaidShutdownManager) OnRaidPointsReceived() {
	m.mu.Lock()
	defer m.mu.Unlock()

	if !m.cfg.Enabled || !m.cfg.OnlyAfterRaid || len(m.targets) == 0 {
		return
	}

	m.raidPending = true
	m.generation++
	generation := m.generation
	m.cancelLocked()
	m.raidPending = true

	ctx, cancel := context.WithCancel(context.Background())
	m.cancel = cancel

	go m.waitForShutdown(ctx, generation)
}

func (m *RaidShutdownManager) waitForShutdown(ctx context.Context, generation uint64) {
	timer := time.NewTimer(m.cfg.GracePeriod)
	defer timer.Stop()

	select {
	case <-ctx.Done():
		return
	case <-timer.C:
	}

	m.mu.Lock()
	if generation != m.generation || !m.raidPending || !m.allTargetsOfflineLocked() {
		m.mu.Unlock()
		return
	}

	m.raidPending = false
	m.cancel = nil
	shutdown := m.shutdown
	m.mu.Unlock()

	if shutdown != nil {
		shutdown()
	}
}

func (m *RaidShutdownManager) allTargetsOfflineLocked() bool {
	if len(m.targets) == 0 {
		return false
	}

	for _, online := range m.targets {
		if online {
			return false
		}
	}
	return true
}

func (m *RaidShutdownManager) cancelLocked() {
	if m.cancel != nil {
		m.cancel()
		m.cancel = nil
	}
	m.raidPending = false
}

// AllTargetsOffline reports the current state of all configured targets.
func (m *RaidShutdownManager) AllTargetsOffline() bool {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.allTargetsOfflineLocked()
}

// RaidPending reports whether a confirmed raid is currently waiting for the
// grace period to expire.
func (m *RaidShutdownManager) RaidPending() bool {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.raidPending
}
