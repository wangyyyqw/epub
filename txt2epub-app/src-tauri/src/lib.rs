use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

#[tauri::command]
async fn convert_book(
    app: tauri::AppHandle,
    txt_path: String,
    epub_path: String,
    title: String,
    author: String,
    custom_regex: Option<String>,
    patterns: Option<String>,
    remove_empty_line: bool,
    fix_indent: bool,
) -> Result<String, String> {
    let mut cmd = app
        .shell()
        .sidecar("converter-backend")
        .map_err(|e| e.to_string())?
        .args([
            "--txt-path",
            &txt_path,
            "--epub-path",
            &epub_path,
            "--title",
            &title,
            "--author",
            &author,
        ]);

    if let Some(p) = patterns {
        cmd = cmd.args(["--patterns", &p]);
    } else if let Some(regex) = custom_regex {
        cmd = cmd.args(["--custom-regex", &regex]);
    }

    if remove_empty_line {
        cmd = cmd.args(["--remove-empty-line"]);
    }

    if fix_indent {
        cmd = cmd.args(["--fix-indent"]);
    }

    let sidecar_command = cmd;


    let (mut rx, _child) = sidecar_command.spawn().map_err(|e| e.to_string())?;

    let mut output_text = String::new();

    while let Some(event) = rx.recv().await {
        if let CommandEvent::Stdout(line) = event {
            let line_str = String::from_utf8_lossy(&line);
            output_text.push_str(&line_str);
        } else if let CommandEvent::Stderr(line) = event {
            let line_str = String::from_utf8_lossy(&line);
            output_text.push_str(&line_str);
        }
    }

    Ok(output_text)
}

#[tauri::command]
async fn run_epub_tool(
    app: tauri::AppHandle,
    operation: String,
    input_path: String,
    font_path: Option<String>,
    regex_pattern: Option<String>
) -> Result<String, String> {
    let mut cmd = app
        .shell()
        .sidecar("converter-backend")
        .map_err(|e| e.to_string())?
        .args([
            "--plugin", "epub_tool",
            "--operation", &operation,
            "--input-path", &input_path
        ]);

    if let Some(font) = font_path {
        cmd = cmd.args(["--font-path", &font]);
    }

    if let Some(regex) = regex_pattern {
        cmd = cmd.args(["--regex-pattern", &regex]);
    }

    let (mut rx, _child) = cmd.spawn().map_err(|e| e.to_string())?;
    let mut output_text = String::new();

    while let Some(event) = rx.recv().await {
         if let CommandEvent::Stdout(line) = event {
            let line_str = String::from_utf8_lossy(&line);
            output_text.push_str(&line_str);
        } else if let CommandEvent::Stderr(line) = event {
            let line_str = String::from_utf8_lossy(&line);
            output_text.push_str(&line_str);
        }
    }
    Ok(output_text)
}

#[tauri::command]
async fn scan_chapters(
    app: tauri::AppHandle,
    txt_path: String
) -> Result<String, String> {
   let sidecar_command = app.shell().sidecar("converter-backend")
        .map_err(|e| e.to_string())?
        .args([
            "--txt-path", &txt_path,
            "--epub-path", "dummy.epub", // Not used in scan mode but required by argparser
            "--title", "dummy",
            "--scan"
        ]);
        
    let output = sidecar_command
        .output()
        .await
        .map_err(|e| e.to_string())?;
        
    if output.status.success() {
        let stdout = String::from_utf8_lossy(&output.stdout);
        Ok(stdout.to_string())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        Err(stderr.to_string())
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![convert_book, scan_chapters, run_epub_tool])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
