# Epub Tool (Go + Vue + Python)

This is a refactored version of the Epub Tool using Wails (Go + Vue) and Python.

## Tech Stack

- **Frontend**: Vue 3 + Tailwind CSS
- **Backend (Host)**: Go (Wails)
- **Core Logic**: Python (Existing scripts)

## Project Structure

- `frontend/`: Vue 3 application.
- `app.go`: Main Go application logic.
- `backend-py/`: Python source scripts.
- `backend-bin/`: Compiled Python binaries.

## How to Run

1. **Install Prerequisites**:
   - Go 1.18+
   - Node.js 14+
   - Python 3.9+ (for backend logic)
   - Wails CLI: `go install github.com/wailsapp/wails/v2/cmd/wails@latest`

2. **Development**:
   ```bash
   wails dev
   ```

3. **Build**:
   ```bash
   wails build
   ```
   The application will be built in `build/bin/`.

## UI

The UI has been updated to a Dashboard style matching the requirements.
- Sidebar navigation.
- Dashboard with network stats and traffic monitoring (Visual only for now, can be connected to real data).

## Backend Integration

The Go application calls the Python backend executable located in `backend-bin/`.
Ensure `converter-backend` exists in `backend-bin/` or `backend-py/main.py` is available for fallback.
