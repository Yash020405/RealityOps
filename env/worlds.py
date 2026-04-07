WORLDS = {
    "db_overload": {
        "logs": [
            "connection timeout to primary-db",
            "db pool exhausted for payments-writer",
            "retry storm detected in checkout path",
        ],
        "metrics": {"cpu": 92, "latency": 380, "error_rate": 0.22},
        "fix": "increase_pool",
        "probe_hint": "Pool utilization sits above 95% during spikes.",
    },
    "cache_bug": {
        "logs": [
            "cache miss storm in recommendation service",
            "redis spike on shard-3",
            "stale cache key version mismatch",
        ],
        "metrics": {"cpu": 68, "latency": 300, "error_rate": 0.12},
        "fix": "flush_cache",
        "probe_hint": "Miss rate tracks deploys to recommendation workers.",
    },
    "auth_expiry": {
        "logs": [
            "token expired for gateway->auth service",
            "auth failure: signer key rotation drift",
            "JWT verification retries exceeded",
        ],
        "metrics": {"cpu": 48, "latency": 280, "error_rate": 0.18},
        "fix": "refresh_token",
        "probe_hint": "Auth errors cluster around key-rotation windows.",
    },
    "network_partition": {
        "logs": [
            "cross-az packet loss above threshold",
            "gateway timeout between region-a and region-b",
            "service mesh circuit-breaker opened",
        ],
        "metrics": {"cpu": 58, "latency": 420, "error_rate": 0.26},
        "fix": "reroute_traffic",
        "probe_hint": "Latency differs sharply by availability zone.",
    },
    "no_incident": {
        "logs": [
            "all critical probes healthy after retry",
            "brief p99 blip correlated with traffic burst",
            "error budget burn back to baseline",
        ],
        "metrics": {"cpu": 50, "latency": 170, "error_rate": 0.03},
        "fix": "no_fix",
        "probe_hint": "Synthetic checks stay green across every region.",
    },
    "security_breach": {
        "logs": [
            "unusual login from blocked IP range",
            "data export volume spike detected",
            "anomaly in user session patterns",
        ],
        "metrics": {"cpu": 55, "latency": 200, "error_rate": 0.08},
        "fix": "block_ip",
        "probe_hint": "Security logs show unauthorized access patterns.",
    },
    "resource_exhaustion": {
        "logs": [
            "OOM killer triggered on app servers",
            "memory pressure alerts across cluster",
            "auto-scaling limits reached",
        ],
        "metrics": {"cpu": 95, "latency": 350, "error_rate": 0.20},
        "fix": "scale_up",
        "probe_hint": "Resource usage correlates with traffic but exceeds capacity.",
    },
}