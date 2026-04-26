mod server_manager;

use server_manager::ServerManager;
use std::sync::Mutex;
use tauri::Manager;

pub struct AppState {
    pub server: Mutex<ServerManager>,
}

#[tauri::command]
fn get_server_status(state: tauri::State<AppState>) -> serde_json::Value {
    let mut server = state.server.lock().unwrap();
    let running = server.is_running();
    let err = server.last_error().map(|s| s.to_string());
    serde_json::json!({
        "running": running,
        "port": server.port(),
        "last_error": err,
    })
}

#[tauri::command]
fn start_server(state: tauri::State<AppState>) -> Result<(), String> {
    let mut server = state.server.lock().unwrap();
    server.start()
}

#[tauri::command]
fn stop_server(state: tauri::State<AppState>) -> Result<(), String> {
    let mut server = state.server.lock().unwrap();
    server.stop();
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let server = ServerManager::new(8765);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState {
            server: Mutex::new(server),
        })
        .setup(|_app| {
            let state = _app.state::<AppState>();
            let mut server = state.server.lock().unwrap();
            if let Err(e) = server.start() {
                eprintln!("[m-agent] 后端未启动: {e}");
            }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let state = window.state::<AppState>();
                let mut server = state.server.lock().unwrap();
                server.stop();
            }
        })
        .invoke_handler(tauri::generate_handler![
            get_server_status,
            start_server,
            stop_server,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
