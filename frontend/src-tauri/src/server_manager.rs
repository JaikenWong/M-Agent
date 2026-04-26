use std::path::PathBuf;
use std::process::{Child, Command};

pub struct ServerManager {
    child: Option<Child>,
    port: u16,
    last_error: Option<String>,
}

/// 从可执行文件所在路径向上找含 `configs/default.yaml` 或 m-agent 源码根（pyproject + src/magent_tui）的目录，
/// 让 `magent-tui serve` 在正确 cwd 下工作并加载同仓库配置（避免 tauri `npm run dev` 时 cwd 在 frontend/ 下）。
fn find_magent_root() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let mut dir = exe.parent()?;
    for _ in 0..14 {
        if dir.join("configs").join("default.yaml").is_file() {
            return dir.canonicalize().ok();
        }
        if dir.join("src").join("magent_tui").is_dir() && dir.join("pyproject.toml").is_file() {
            return dir.canonicalize().ok();
        }
        dir = dir.parent()?;
    }
    None
}

/// Tauri 将 `externalBin` 安装到与主可执行文件同目录。开发模式下通常不存在该文件，则回退到 PATH 中的 `magent-tui`。
fn resolve_magent_tui_path() -> PathBuf {
    if let Some(p) = bundled_magent_tui() {
        return p;
    }
    let name = if cfg!(target_os = "windows") {
        "magent-tui.exe"
    } else {
        "magent-tui"
    };
    PathBuf::from(name)
}

fn bundled_magent_tui() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    let name = if cfg!(target_os = "windows") {
        "magent-tui.exe"
    } else {
        "magent-tui"
    };
    let path = dir.join(name);
    if path.is_file() {
        return Some(path);
    }
    None
}

impl ServerManager {
    pub fn new(port: u16) -> Self {
        Self {
            child: None,
            port,
            last_error: None,
        }
    }

    pub fn port(&self) -> u16 {
        self.port
    }

    pub fn last_error(&self) -> Option<&str> {
        self.last_error.as_deref()
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
            self.last_error = None;
            return Ok(());
        }
        self.last_error = None;

        let program = resolve_magent_tui_path();
        let mut cmd = Command::new(&program);
        cmd.args([
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            &self.port.to_string(),
        ]);

        if let Some(root) = find_magent_root() {
            let cfg = root.join("configs").join("default.yaml");
            if cfg.is_file() {
                cmd.current_dir(&root);
                cmd.arg("-c");
                cmd.arg(&cfg);
            } else {
                cmd.current_dir(&root);
            }
        }

        let child = cmd.spawn().map_err(|e| {
            let msg = format!(
                "无法启动 magent-tui ({}): {e}. \
                开发环境请先: cd 仓库根目录 && source .venv/bin/activate && pip install -e . \
                安装版请先运行 packaging 脚本把 magent-tui 与配置打进 bundle。",
                program.display()
            );
            self.last_error = Some(msg.clone());
            msg
        })?;

        eprintln!(
            "[m-agent] backend 已启动: {} (cwd+config: {:?})",
            program.display(),
            find_magent_root()
        );
        self.child = Some(child);
        self.last_error = None;
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
