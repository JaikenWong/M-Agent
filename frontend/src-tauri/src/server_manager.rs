use std::process::{Child, Command};

pub struct ServerManager {
    child: Option<Child>,
    port: u16,
}

impl ServerManager {
    pub fn new(port: u16) -> Self {
        Self { child: None, port }
    }

    pub fn port(&self) -> u16 {
        self.port
    }

    pub fn is_running(&mut self) -> bool {
        if let Some(child) = &mut self.child {
            matches!(child.try_wait(), Ok(None))
        } else {
            false
        }
    }

    pub fn start(&mut self) -> Result<(), String> {
        if self.is_running() {
            return Ok(());
        }
        let child = Command::new("magent-tui")
            .args(["serve", "--port", &self.port.to_string()])
            .spawn()
            .map_err(|e| format!("Failed to start magent-tui server: {e}"))?;
        self.child = Some(child);
        Ok(())
    }

    pub fn stop(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

impl Drop for ServerManager {
    fn drop(&mut self) {
        self.stop();
    }
}
