package redcat

import (
    "bufio"
    "context"
    "fmt"
    "os"
    "strings"
    "sync"
    "time"
)

type Balance struct {
    Name   string
    Points int
}

type ConsoleDashboardConfig struct {
    Stats    *StatsStore
    Balances func() []Balance
    Cancel   context.CancelFunc
    Interval time.Duration
}

func StartConsoleDashboard(ctx context.Context, cfg ConsoleDashboardConfig) {
    if cfg.Stats == nil || cfg.Cancel == nil {
        return
    }
    if cfg.Interval <= 0 {
        cfg.Interval = 30 * time.Second
    }

    go func() {
        started := time.Now()
        base := cfg.Stats.Snapshot().TotalPoints
        var mu sync.Mutex
        _ = mu

        printShort := func() {
            snap := cfg.Stats.Snapshot()
            today := snap.ByDay[time.Now().Local().Format("2006-01-02")]
            session := snap.TotalPoints - base
            if session < 0 {
                session = 0
            }
            fmt.Printf("\n📊 Session: +%d | Today: +%d | All-time: %d\n", session, today, snap.TotalPoints)
        }

        printDetailed := func() {
            snap := cfg.Stats.Snapshot()
            session := snap.TotalPoints - base
            if session < 0 {
                session = 0
            }
            today := snap.ByDay[time.Now().Local().Format("2006-01-02")]
            counts := map[PointReason]int{}
            for _, e := range snap.Events {
                if !e.Time.Before(started) {
                    counts[e.Reason]++
                }
            }

            fmt.Print("\033[2J\033[H")
            fmt.Println("╔══════════════════════════════════════╗")
            fmt.Println("║       🐱 REDCAT STATISTICS           ║")
            fmt.Println("╠══════════════════════════════════════╣")
            fmt.Printf("║ Session:                       %s ║\n", formatDuration(time.Since(started)))
            fmt.Println("║                                      ║")
            fmt.Printf("║ 👀 WATCH                     %5d  ║\n", counts[PointWatch])
            fmt.Printf("║ 🎁 CLAIM                     %5d  ║\n", counts[PointClaim])
            fmt.Printf("║ 🔥 STREAK                    %5d  ║\n", counts[PointWatchStreak])
            fmt.Printf("║ 🚀 RAID                      %5d  ║\n", counts[PointRaid])
            fmt.Println("║                                      ║")
            fmt.Printf("║ 💰 SESSION TOTAL            %5d  ║\n", session)
            fmt.Printf("║ 📅 TODAY                     %5d  ║\n", today)
            fmt.Printf("║ 🏆 ALL TIME                %7d  ║\n", snap.TotalPoints)
            fmt.Println("╠══════════════════════════════════════╣")
            fmt.Println("║ 💰 BALANCES                         ║")
            balances := cfg.Balances()
            if len(balances) == 0 {
                fmt.Println("║ (waiting for Twitch balances...)     ║")
            } else {
                for _, b := range balances {
                    name := b.Name
                    if len(name) > 18 {
                        name = name[:18]
                    }
                    fmt.Printf("║ %-18s %12d  ║\n", name, b.Points)
                }
            }
            fmt.Println("╠══════════════════════════════════════╣")
            fmt.Println("║ [S] Statistics  [R] Refresh  [Q] Quit║")
            fmt.Println("╚══════════════════════════════════════╝")
        }

        printShort()

        input := make(chan string, 4)
        go func() {
            scanner := bufio.NewScanner(os.Stdin)
            for scanner.Scan() {
                input <- strings.TrimSpace(strings.ToLower(scanner.Text()))
            }
        }()

        ticker := time.NewTicker(cfg.Interval)
        defer ticker.Stop()

        for {
            select {
            case <-ctx.Done():
                return
            case cmd := <-input:
                switch cmd {
                case "s", "stats", "statistics":
                    printDetailed()
                case "r", "refresh":
                    printShort()
                case "q", "quit":
                    fmt.Println("\n🐱 RedCat: graceful shutdown requested.")
                    cfg.Cancel()
                    return
                }
            case <-ticker.C:
                printShort()
            }
        }
    }()
}

func formatDuration(d time.Duration) string {
    if d < 0 {
        d = 0
    }
    h := int(d / time.Hour)
    m := int((d % time.Hour) / time.Minute)
    s := int((d % time.Minute) / time.Second)
    return fmt.Sprintf("%02d:%02d:%02d", h, m, s)
}
