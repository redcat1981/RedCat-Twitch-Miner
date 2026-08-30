package redcat

import (
	"sync/atomic"
	"testing"
	"time"
)

func TestRaidShutdownWhenBothTargetsStayOffline(t *testing.T) {
	var shutdowns atomic.Int32
	manager := NewRaidShutdownManager(
		[]string{"v_craken_v", "fenriscreations"},
		RaidShutdownConfig{Enabled: true, OnlyAfterRaid: true, GracePeriod: 20 * time.Millisecond, RequireAllTargetChannelsOffline: true},
		func() { shutdowns.Add(1) },
	)

	manager.OnRaidPointsReceived()
	time.Sleep(50 * time.Millisecond)

	if got := shutdowns.Load(); got != 1 {
		t.Fatalf("expected one shutdown, got %d", got)
	}
}

func TestRaidShutdownCancelledWhenTargetReturnsOnline(t *testing.T) {
	var shutdowns atomic.Int32
	manager := NewRaidShutdownManager(
		[]string{"v_craken_v", "fenriscreations"},
		RaidShutdownConfig{Enabled: true, OnlyAfterRaid: true, GracePeriod: 50 * time.Millisecond, RequireAllTargetChannelsOffline: true},
		func() { shutdowns.Add(1) },
	)

	manager.OnStreamerOffline("v_craken_v")
	manager.OnStreamerOffline("fenriscreations")
	manager.OnRaidPointsReceived()

	time.Sleep(10 * time.Millisecond)
	manager.OnStreamerOnline("fenriscreations")
	time.Sleep(70 * time.Millisecond)

	if got := shutdowns.Load(); got != 0 {
		t.Fatalf("expected shutdown to be cancelled, got %d", got)
	}
}

func TestOfflineAloneDoesNotShutdown(t *testing.T) {
	var shutdowns atomic.Int32
	manager := NewRaidShutdownManager(
		[]string{"v_craken_v", "fenriscreations"},
		RaidShutdownConfig{Enabled: true, OnlyAfterRaid: true, GracePeriod: 20 * time.Millisecond, RequireAllTargetChannelsOffline: true},
		func() { shutdowns.Add(1) },
	)

	manager.OnStreamerOffline("v_craken_v")
	time.Sleep(40 * time.Millisecond)

	if got := shutdowns.Load(); got != 0 {
		t.Fatalf("unexpected shutdown without raid: %d", got)
	}
}
