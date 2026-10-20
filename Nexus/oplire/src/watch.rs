use std::time::Duration;
use tokio::time::interval;
use tracing::{error, info, warn};

use crate::sessions::SessionGuard;
use crate::warp::WarpResolver;

pub async fn start_watch_mode(
    upstream: &str,
    max_retries: u32,
    warp_delay_ms: u64,
) -> anyhow::Result<()> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
        .build()?;

    let resolver = WarpResolver::new(max_retries, warp_delay_ms);
    let session_guard = SessionGuard::new();
    session_guard.init().await;

    let models_url = format!("{}/v1/models", upstream.trim_end_matches('/'));

    let mut check_interval = interval(Duration::from_secs(20));
    let mut consecutive_429 = 0u32;
    let mut total_requests = 0u32;
    let mut successful_requests = 0u32;
    let mut last_rate_limit_time: Option<u64> = None;
    let mut last_health_check = 0u64;
    let health_check_interval = 300;

    info!("Watch mode active with predictive rate limit detection");
    info!("Monitoring: {}", models_url);
    info!("Health checks every {}s", health_check_interval);

    loop {
        check_interval.tick().await;

        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);

        if now - last_health_check >= health_check_interval {
            info!("Running periodic health check...");
            match session_guard.fix_corrupted_sessions().await {
                Ok(fixed) if fixed > 0 => {
                    info!("Fixed {} corrupted sessions", fixed);
                }
                _ => {}
            }
            match session_guard.cleanup_old_sessions(24).await {
                Ok(archived) if archived > 0 => {
                    info!("Archived {} old sessions", archived);
                }
                _ => {}
            }
            last_health_check = now;
        }

        total_requests += 1;

        match client.get(&models_url).send().await {
            Ok(resp) => {
                let status = resp.status();

                if status.is_success() {
                    successful_requests += 1;

                    if consecutive_429 > 0 {
                        info!(
                            "Rate limit recovered (was {} consecutive 429s)",
                            consecutive_429
                        );
                        consecutive_429 = 0;
                    }

                    let success_rate = if total_requests > 0 {
                        (successful_requests as f64 / total_requests as f64 * 100.0) as u32
                    } else {
                        100
                    };

                    if total_requests % 10 == 0 {
                        info!(
                            "Health: OK (success rate: {}%, total checks: {})",
                            success_rate, total_requests
                        );
                    }

                    if let Some(last_rl) = last_rate_limit_time {
                        let time_since_rl = now.saturating_sub(last_rl);
                        if time_since_rl > 300 {
                            info!(
                                "Rate limit window cleared ({}s since last 429)",
                                time_since_rl
                            );
                            last_rate_limit_time = None;
                        }
                    }
                } else if status.as_u16() == 429 {
                    consecutive_429 += 1;
                    last_rate_limit_time = Some(now);

                    warn!(
                        "Rate limit detected (count: {}, total checks: {})",
                        consecutive_429, total_requests
                    );

                    let estimated_wait = estimate_rate_limit_wait(consecutive_429);
                    info!("Estimated wait time: {}s", estimated_wait);

                    if consecutive_429 >= 2 {
                        info!("Multiple 429s detected, performing full WARP rotation...");
                        if let Err(e) = resolver.full_cleanup().await {
                            warn!("Full cleanup failed: {}", e);
                        }
                        tokio::time::sleep(Duration::from_secs(3)).await;
                    }

                    if resolver.handle_429(consecutive_429 - 1).await {
                        info!("WARP reset triggered. Waiting for recovery...");
                        tokio::time::sleep(Duration::from_secs(5)).await;

                        match client.get(&models_url).send().await {
                            Ok(retry_resp)
                                if retry_resp.status().is_success() =>
                            {
                                info!("Recovery confirmed. OpenCode Zen is accessible.");
                                consecutive_429 = 0;
                            }
                            _ => {
                                warn!(
                                    "Recovery check failed. Will retry on next cycle."
                                );
                            }
                        }
                    } else {
                        error!("WARP reset failed. Rate limit persists.");

                        if consecutive_429 >= 3 {
                            error!(
                                "Persistent rate limit after {} attempts. Consider manual intervention.",
                                consecutive_429
                            );
                        }
                    }
                } else {
                    warn!(
                        "OpenCode Zen returned unexpected status: {}",
                        status
                    );
                }
            }
            Err(e) => {
                error!("Failed to reach OpenCode Zen: {}", e);

                if e.is_timeout() {
                    warn!("Connection timeout - upstream may be overloaded");
                } else if e.is_connect() {
                    error!("Connection failed - is OpenCode Zen running?");
                }
            }
        }
    }
}

fn estimate_rate_limit_wait(consecutive_429: u32) -> u64 {
    match consecutive_429 {
        1 => 30,
        2 => 60,
        3 => 120,
        4 => 300,
        _ => 600,
    }
}
