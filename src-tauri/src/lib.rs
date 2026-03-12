use std::sync::Mutex;
use std::time::Duration;

use tauri::Manager;
use tauri_plugin_shell::ShellExt;

const SIDECAR_PORT: u16 = 3000;
const HEALTH_POLL_INTERVAL: Duration = Duration::from_millis(500);
const HEALTH_POLL_TIMEOUT: Duration = Duration::from_secs(30);
const SHUTDOWN_GRACE: Duration = Duration::from_secs(3);

struct SidecarState {
    pid: Option<u32>,
}

impl SidecarState {
    /// Lock the mutex, recovering from poison if needed.
    /// Safe here because SidecarState is just an Option<u32>.
    fn lock_or_recover(state: &Mutex<SidecarState>) -> std::sync::MutexGuard<'_, SidecarState> {
        state.lock().unwrap_or_else(|e| e.into_inner())
    }
}

fn env_file_path() -> String {
    let home = std::env::var("HOME").unwrap_or_default();
    format!(
        "{}/Library/Application Support/com.vault-agent.app/.env",
        home
    )
}

async fn wait_for_health(port: u16, timeout: Duration) -> Result<(), String> {
    let url = format!("http://127.0.0.1:{}/health", port);
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let start = std::time::Instant::now();
    loop {
        if start.elapsed() > timeout {
            return Err(format!(
                "Sidecar health check timed out after {}s",
                timeout.as_secs()
            ));
        }
        match client.get(&url).send().await {
            Ok(resp) if resp.status().is_success() => return Ok(()),
            _ => tokio::time::sleep(HEALTH_POLL_INTERVAL).await,
        }
    }
}

/// Send SIGTERM to a process, wait for grace period, then SIGKILL if still alive.
fn graceful_kill(pid: u32) {
    #[cfg(unix)]
    {
        use std::thread;
        unsafe {
            libc::kill(pid as i32, libc::SIGTERM);
        }
        thread::sleep(SHUTDOWN_GRACE);
        unsafe {
            if libc::kill(pid as i32, 0) == 0 {
                libc::kill(pid as i32, libc::SIGKILL);
            }
        }
    }
}

fn sidecar_url() -> url::Url {
    format!("http://localhost:{}", SIDECAR_PORT)
        .parse()
        .expect("hardcoded localhost URL must parse")
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Mutex::new(SidecarState { pid: None }))
        .setup(|app| {
            let shell = app.shell();
            let env_file = env_file_path();

            let (mut rx, child) = shell
                .sidecar("vault-agent-sidecar")
                .map_err(|e| format!("Failed to create sidecar command: {}", e))?
                .args(["--port", &SIDECAR_PORT.to_string(), "--env-file", &env_file])
                .spawn()
                .map_err(|e| format!("Failed to spawn sidecar: {}", e))?;

            let pid = child.pid();
            let state = app.state::<Mutex<SidecarState>>();
            SidecarState::lock_or_recover(&state).pid = Some(pid);
            log::info!("Sidecar spawned with PID {}", pid);

            // Log sidecar stdout/stderr in background
            tauri::async_runtime::spawn(async move {
                use tauri_plugin_shell::process::CommandEvent;
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            log::info!("[sidecar] {}", String::from_utf8_lossy(&line))
                        }
                        CommandEvent::Stderr(line) => {
                            log::warn!("[sidecar] {}", String::from_utf8_lossy(&line))
                        }
                        CommandEvent::Terminated(payload) => {
                            log::info!("[sidecar] terminated: {:?}", payload);
                            break;
                        }
                        CommandEvent::Error(err) => {
                            log::error!("[sidecar] error: {}", err);
                            break;
                        }
                        _ => {}
                    }
                }
            });

            // Health-poll then open window
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                match wait_for_health(SIDECAR_PORT, HEALTH_POLL_TIMEOUT).await {
                    Ok(()) => {
                        log::info!("Sidecar healthy, opening window");
                        let url = tauri::WebviewUrl::External(sidecar_url());
                        match tauri::WebviewWindowBuilder::new(&app_handle, "main", url)
                            .title("Vault Agent")
                            .inner_size(1200.0, 800.0)
                            .min_inner_size(800.0, 600.0)
                            .build()
                        {
                            Ok(_) => {}
                            Err(e) => {
                                log::error!("Failed to create window: {}", e);
                                // Kill sidecar before exiting since window failed
                                let state = app_handle.state::<Mutex<SidecarState>>();
                                if let Some(pid) = SidecarState::lock_or_recover(&state).pid.take()
                                {
                                    graceful_kill(pid);
                                }
                                std::process::exit(1);
                            }
                        }
                    }
                    Err(e) => {
                        log::error!("Sidecar failed to start: {}", e);
                        eprintln!("Fatal: {}", e);
                        std::process::exit(1);
                    }
                }
            });

            Ok(())
        })
        .on_event(|app, event| {
            if let tauri::RunEvent::Exit = event {
                let state = app.state::<Mutex<SidecarState>>();
                if let Some(pid) = SidecarState::lock_or_recover(&state).pid.take() {
                    log::info!("Shutting down sidecar (PID {})", pid);
                    graceful_kill(pid);
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error running tauri application");
}
