pub mod resolver;

pub use resolver::WarpResolver;

pub async fn reset_warp_external() -> Result<String, String> {
    let resolver = WarpResolver::new(1, 3000);
    resolver.reset_warp().await?;
    Ok("WARP tunnel reset complete. New IP assigned.".to_string())
}

pub async fn restore_ip_external() -> Result<String, String> {
    let resolver = WarpResolver::new(1, 3000);
    resolver.restore_original_ip().await
}
