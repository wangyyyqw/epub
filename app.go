package main

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"time"

	wailsRuntime "github.com/wailsapp/wails/v2/pkg/runtime"
)

// debugMode controls whether debug logs are printed
var debugMode = os.Getenv("EPUB_TOOL_DEBUG") == "1"

func debugLog(format string, args ...interface{}) {
	if debugMode {
		fmt.Fprintf(os.Stderr, "DEBUG: "+format+"\n", args...)
	}
}

// App struct
type App struct {
	ctx context.Context
}

// BackendResult holds the output from a backend command
type BackendResult struct {
	Stdout string `json:"stdout"`
	Stderr string `json:"stderr"`
}

// NewApp creates a new App application struct
func NewApp() *App {
	return &App{}
}

// startup is called when the app starts
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
}

// Greet returns a greeting for the given name
func (a *App) Greet(name string) string {
	return fmt.Sprintf("Hello %s, It's show time!", name)
}

// projectRoot returns the project root directory.
// In dev mode, runtime.Caller gives the source file path.
// In production, it falls back to executable directory.
func projectRoot() string {
	_, sourceFile, _, ok := runtime.Caller(0)
	if ok && sourceFile != "" {
		dir := filepath.Dir(sourceFile)
		// Verify it looks like our project root
		if _, err := os.Stat(filepath.Join(dir, "backend-py", "main.py")); err == nil {
			return dir
		}
	}
	ex, err := os.Executable()
	if err == nil {
		return filepath.Dir(ex)
	}
	return "."
}

// findBackendBinary locates the converter-backend binary
func (a *App) findBackendBinary() string {
	binaryName := "converter-backend"
	if runtime.GOOS == "windows" {
		binaryName += ".exe"
	}

	ex, err := os.Executable()
	if err != nil {
		return ""
	}
	exPath := filepath.Dir(ex)
	root := projectRoot()

	searchPaths := []string{
		filepath.Join("backend-bin", binaryName),
		filepath.Join(exPath, "backend-bin", binaryName),
		filepath.Join(exPath, binaryName),
		filepath.Join(root, "backend-bin", binaryName),
	}

	// macOS .app bundle: Contents/MacOS/../Resources/backend-bin/
	if runtime.GOOS == "darwin" {
		searchPaths = append(searchPaths,
			filepath.Join(exPath, "..", "Resources", "backend-bin", binaryName),
		)
	}

	for _, p := range searchPaths {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}

// GetLogFilePath 返回日志文件的完整路径
// 搜索路径与 findBackendBinary() 一致，在 Python 后端可执行文件所在目录下查找 log.txt
func (a *App) GetLogFilePath() (string, error) {
	binaryName := "converter-backend"
	if runtime.GOOS == "windows" {
		binaryName += ".exe"
	}

	ex, err := os.Executable()
	if err != nil {
		return "", fmt.Errorf("无法获取可执行文件路径: %s", err)
	}
	exPath := filepath.Dir(ex)
	root := projectRoot()

	searchPaths := []string{
		filepath.Join("backend-bin", binaryName),
		filepath.Join(exPath, "backend-bin", binaryName),
		filepath.Join(exPath, binaryName),
		filepath.Join(root, "backend-bin", binaryName),
	}

	if runtime.GOOS == "darwin" {
		searchPaths = append(searchPaths,
			filepath.Join(exPath, "..", "Resources", "backend-bin", binaryName),
		)
	}

	for _, p := range searchPaths {
		if _, err := os.Stat(p); err == nil {
			logPath := filepath.Join(filepath.Dir(p), "log.txt")
			if _, err := os.Stat(logPath); err == nil {
				return logPath, nil
			}
		}
	}

	return "", fmt.Errorf("日志文件未找到")
}

// OpenLogFile 使用系统默认程序打开日志文件
func (a *App) OpenLogFile() error {
	logPath, err := a.GetLogFilePath()
	if err != nil {
		return err
	}

	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "darwin":
		cmd = exec.Command("open", logPath)
	case "windows":
		cmd = exec.Command("cmd", "/c", "start", "", logPath)
	default:
		cmd = exec.Command("xdg-open", logPath)
	}

	return cmd.Start()
}



// RunBackend executes the backend with arguments.
// Returns BackendResult with separate stdout/stderr so frontend can handle them independently.
func (a *App) RunBackend(args []string) (*BackendResult, error) {
	var cmd *exec.Cmd

	binaryPath := a.findBackendBinary()

	cwd, _ := os.Getwd()
	debugLog("Current working directory: %s", cwd)
	debugLog("Binary path found: %s", binaryPath)

	if binaryPath != "" {
		cmd = exec.Command(binaryPath, args...)
	} else {
		ex, _ := os.Executable()
		exPath := filepath.Dir(ex)
		root := projectRoot()

		searchPaths := []string{
			filepath.Join("backend-py", "main.py"),
			filepath.Join(exPath, "backend-py", "main.py"),
			filepath.Join(root, "backend-py", "main.py"),
		}

		pythonScript := ""
		for _, p := range searchPaths {
			if _, err := os.Stat(p); err == nil {
				pythonScript = p
				break
			}
		}

		if pythonScript == "" {
			return nil, fmt.Errorf("后端程序未找到: 既没有编译的二进制文件，也没有 Python 脚本\n搜索路径: %v", searchPaths)
		}

		debugLog("Using Python script: %s", pythonScript)
		cmdArgs := append([]string{pythonScript}, args...)
		pythonCmd := "python3"
		if runtime.GOOS == "windows" {
			pythonCmd = "python"
		}
		cmd = exec.Command(pythonCmd, cmdArgs...)
	}

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	// 启动进程
	if err := cmd.Start(); err != nil {
		return &BackendResult{}, fmt.Errorf("启动后端失败: %s", err)
	}

	// 带超时等待，默认 5 分钟
	done := make(chan error, 1)
	go func() {
		done <- cmd.Wait()
	}()

	timeout := 5 * time.Minute
	var err error
	select {
	case <-time.After(timeout):
		if cmd.Process != nil {
			cmd.Process.Kill()
		}
		err = fmt.Errorf("执行超时（5分钟）")
	case err = <-done:
	}

	result := &BackendResult{
		Stdout: stdout.String(),
		Stderr: stderr.String(),
	}

	if err != nil {
		return result, fmt.Errorf("执行失败: %s\nSTDERR: %s", err, result.Stderr)
	}

	return result, nil
}

// SelectFile opens a file dialog for selecting a file
func (a *App) SelectFile() (string, error) {
	return wailsRuntime.OpenFileDialog(a.ctx, wailsRuntime.OpenDialogOptions{
		Title: "选择文件",
	})
}
// SelectFiles opens a file dialog for selecting multiple files
func (a *App) SelectFiles() ([]string, error) {
	return wailsRuntime.OpenMultipleFilesDialog(a.ctx, wailsRuntime.OpenDialogOptions{
		Title: "选择文件（可多选）",
		Filters: []wailsRuntime.FileFilter{
			{DisplayName: "EPUB 文件", Pattern: "*.epub"},
		},
	})
}


// SelectDirectory opens a directory dialog
func (a *App) SelectDirectory() (string, error) {
	return wailsRuntime.OpenDirectoryDialog(a.ctx, wailsRuntime.OpenDialogOptions{
		Title: "选择目录",
	})
}

// SaveFile opens a save file dialog
func (a *App) SaveFile(defaultFilename string) (string, error) {
	return wailsRuntime.SaveFileDialog(a.ctx, wailsRuntime.SaveDialogOptions{
		Title:           "保存文件",
		DefaultFilename: defaultFilename,
	})
}

