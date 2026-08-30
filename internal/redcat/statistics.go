package redcat

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// PointReason identifies the source of earned channel points.
type PointReason string

const (
	PointWatch       PointReason = "WATCH"
	PointClaim       PointReason = "CLAIM"
	PointWatchStreak PointReason = "WATCH_STREAK"
	PointRaid        PointReason = "RAID"
)

// PointEvent is a single confirmed points award.
type PointEvent struct {
	Time     time.Time   `json:"time"`
	Streamer string      `json:"streamer"`
	Reason   PointReason `json:"reason"`
	Points   int         `json:"points"`
}

// Statistics contains persistent RedCat statistics.
type Statistics struct {
	TotalPoints int64                   `json:"total_points"`
	ByReason    map[PointReason]int64   `json:"by_reason"`
	ByStreamer  map[string]int64        `json:"by_streamer"`
	ByDay       map[string]int64        `json:"by_day"`
	Drops       int64                   `json:"drops"`
	Moments     int64                   `json:"moments"`
	Raids       int64                   `json:"raids"`
	Events      []PointEvent            `json:"events,omitempty"`
}

// StatsStore safely accumulates and persists statistics.
type StatsStore struct {
	mu   sync.Mutex
	path string
	data Statistics
}

func NewStatsStore(path string) (*StatsStore, error) {
	s := &StatsStore{path: path, data: Statistics{
		ByReason:   make(map[PointReason]int64),
		ByStreamer: make(map[string]int64),
		ByDay:      make(map[string]int64),
	}}
	if b, err := os.ReadFile(path); err == nil {
		if err := json.Unmarshal(b, &s.data); err != nil { return nil, err }
		if s.data.ByReason == nil { s.data.ByReason = make(map[PointReason]int64) }
		if s.data.ByStreamer == nil { s.data.ByStreamer = make(map[string]int64) }
		if s.data.ByDay == nil { s.data.ByDay = make(map[string]int64) }
	} else if !os.IsNotExist(err) {
		return nil, err
	}
	return s, nil
}

func (s *StatsStore) AddPoints(streamer string, reason PointReason, points int, at time.Time) error {
	if points <= 0 { return nil }
	s.mu.Lock()
	defer s.mu.Unlock()
	s.data.TotalPoints += int64(points)
	s.data.ByReason[reason] += int64(points)
	s.data.ByStreamer[streamer] += int64(points)
	s.data.ByDay[at.Local.Format("2006-01-02")] += int64(points)
	s.data.Events = append(s.data.Events, PointEvent{Time: at, Streamer: streamer, Reason: reason, Points: points})
	return s.saveLocked()
}

func (s *StatsStore) AddRaid() error {
	s.mu.Lock(); defer s.mu.Unlock(); s.data.Raids++; return s.saveLocked()
}

func (s *StatsStore) AddDrop() error {
	s.mu.Lock(); defer s.mu.Unlock(); s.data.Drops++; return s.saveLocked()
}

func (s *StatsStore) AddMoment() error {
	s.mu.Lock(); defer s.mu.Unlock(); s.data.Moments++; return s.saveLocked()
}

func (s *StatsStore) Snapshot() Statistics {
	s.mu.Lock(); defer s.mu.Unlock()
	out := s.data
	out.ByReason = cloneReason(s.data.ByReason)
	out.ByStreamer = cloneString(s.data.ByStreamer)
	out.ByDay = cloneString(s.data.ByDay)
	return out
}

func (s *StatsStore) saveLocked() error {
	if dir := filepath.Dir(s.path); dir != "." { if err := os.MkdirAll(dir, 0755); err != nil { return err } }
	b, err := json.MarshalIndent(s.data, "", "  "); if err != nil { return err }
	tmp := s.path + ".tmp"
	if err := os.WriteFile(tmp, b, 0644); err != nil { return err }
	return os.Rename(tmp, s.path)
}

func cloneReason(in map[PointReason]int64) map[PointReason]int64 { out := make(map[PointReason]int64, len(in)); for k,v := range in { out[k]=v }; return out }
func cloneString(in map[string]int64) map[string]int64 { out := make(map[string]int64, len(in)); for k,v := range in { out[k]=v }; return out }
