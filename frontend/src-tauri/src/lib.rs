mod server_manager;

use server_manager::ServerManager;
use std::sync::Mutex;
use tauri::Manager;

pub struct AppState {
    pub server: Mutex<ServerManager>,
}

#[tauri::command]
fn get_server_status(state: tauri::State<AppState>) -> serde_json::Value {
    let server = state.server.lock().unwrap();
    serde_json::json!({
        "running": server.is_running(),
        "port": server.port(),
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
        .setup(|app| {
            let state = app.state::<AppState>();
            let mut server = state.server.lock().unwrap();
            // Auto-start server on launch; ignore error (server may already be running)
            let _ = server.start();
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
