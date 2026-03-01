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

// backendSearchPaths returns the common search paths for locating backend-related files.
func backendSearchPaths() ([]string, string) {
	ex, err := os.Executable()
	if err != nil {
		return nil, ""
	}
	exPath := filepath.Dir(ex)
	root := projectRoot()

	paths := []string{
		"backend-bin",
		filepath.Join(exPath, "backend-bin"),
		exPath,
		filepath.Join(root, "backend-bin"),
	}

	// macOS .app bundle: Contents/MacOS/../Resources/backend-bin/
	if runtime.GOOS == "darwin" {
		paths = append(paths, filepath.Join(exPath, "..", "Resources", "backend-bin"))
	}

	return paths, exPath
}

// findFileInSearchPaths locates a file by name across backend search paths.
// Returns the full path if found, empty string otherwise.
func findFileInSearchPaths(filename string) string {
	dirs, _ := backendSearchPaths()
	for _, dir := range dirs {
		p := filepath.Join(dir, filename)
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}

// findBackendBinary locates the converter-backend binary
func (a *App) findBackendBinary() string {
	binaryName := "converter-backend"
	if runtime.GOOS == "windows" {
		binaryName += ".exe"
	}
	return findFileInSearchPaths(binaryName)
}

// GetLogFilePath 返回日志文件的完整路径
func (a *App) GetLogFilePath() (string, error) {
	binaryName := "converter-backend"
	if runtime.GOOS == "windows" {
		binaryName += ".exe"
	}

	// 找到后端二进制文件，然后在同目录下查找 log.txt
	binaryPath := findFileInSearchPaths(binaryName)
	if binaryPath != "" {
		logPath := filepath.Join(filepath.Dir(binaryPath), "log.txt")
		if _, err := os.Stat(logPath); err == nil {
			return logPath, nil
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

	// On Windows, write --patterns value to a temp file to avoid CLI encoding issues with Chinese characters.
	// Replace --patterns <value> with --patterns-file <tempfile> in the args.
	var tempPatternsFile string
	if runtime.GOOS == "windows" {
		for i := 0; i < len(args)-1; i++ {
			if args[i] == "--patterns" {
				patternsValue := args[i+1]
				tmpFile, err := os.CreateTemp("", "epub-patterns-*.txt")
				if err == nil {
					_, writeErr := tmpFile.WriteString(patternsValue)
					tmpFile.Close()
					if writeErr == nil {
						tempPatternsFile = tmpFile.Name()
						args[i] = "--patterns-file"
						args[i+1] = tempPatternsFile
					} else {
						os.Remove(tmpFile.Name())
					}
				}
				break
			}
		}
	}
	// Clean up temp file when done
	if tempPatternsFile != "" {
		defer os.Remove(tempPatternsFile)
	}

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

	// Ensure UTF-8 encoding for subprocess (critical for Chinese characters in regex patterns on Windows)
	cmd.Env = append(os.Environ(), "PYTHONIOENCODING=utf-8", "PYTHONUTF8=1")

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

// OpenURL opens a URL in the default browser
func (a *App) OpenURL(url string) error {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "darwin":
		cmd = exec.Command("open", url)
	case "windows":
		cmd = exec.Command("cmd", "/c", "start", "", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	return cmd.Start()
}

// SearchDoubanCover searches Douban for book covers by title.
// Returns JSON string with search results.
func (a *App) SearchDoubanCover(title string) (string, error) {
	args := []string{"--plugin", "txt2epub", "--txt-path", "/dev/null", "--epub-path", "/dev/null", "--title", "search", "--search-cover", title}
	result, err := a.RunBackend(args)
	if err != nil {
		return "", fmt.Errorf("搜索封面失败: %s", err)
	}
	return result.Stdout, nil
}

// DownloadDoubanCover downloads a cover image from URL and returns the local path.
func (a *App) DownloadDoubanCover(coverURL string) (string, error) {
	args := []string{"--plugin", "txt2epub", "--txt-path", "/dev/null", "--epub-path", "/dev/null", "--title", "download", "--download-cover", coverURL}
	result, err := a.RunBackend(args)
	if err != nil {
		return "", fmt.Errorf("下载封面失败: %s", err)
	}
	return result.Stdout, nil
}

