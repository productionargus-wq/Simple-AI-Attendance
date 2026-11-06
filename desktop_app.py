"""
ARGUS CNC™ - Desktop Application Launcher (Cloud-Connected with Offline Fallback)
Runs the Argus Attendance Intelligence Application inside a native, dedicated desktop window
(powered by Microsoft Edge WebView2 via PyWebView):
- Primary Mode: Connects directly to the live production cloud server:
    https://argusattendanceintelligence.argussoftwares.com/
  This guarantees all clients instantly receive every feature, fix, and update in real-time
  without ever needing to reinstall the desktop .exe!
- Offline Fallback Mode: If the laptop is disconnected from the internet or the cloud server
  is temporarily unreachable, it automatically starts the embedded Waitress WSGI local server
  (http://127.0.0.1:<port>/) so local attendance operations continue without interruption.
"""

import os
import sys
import time
import socket
import threading
import urllib.request
import urllib.error
import webview
from waitress import serve

# Configure stdout and stderr for UTF-8 and safe character replacement on Windows
if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr is not None:
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

CLOUD_URL = "https://argusattendanceintelligence.argussoftwares.com/"
CLOUD_HEALTH_URL = "https://argusattendanceintelligence.argussoftwares.com/health"


def get_base_dir():
    """Returns the base directory for resources in development or bundled executable."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def find_available_port(default_port=5000):
    """Checks if default_port is free, otherwise finds any open ephemeral port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', default_port))
            return default_port
    except OSError:
        pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def start_wsgi_server(app, host, port):
    """Starts Waitress production WSGI server in background."""
    try:
        serve(app, host=host, port=port, threads=8, _quiet=True)
    except Exception as e:
        print(f"[Waitress] Server error: {e}")


def wait_for_server_ready(url, timeout=12):
    """Polls the local server until it responds to HTTP requests."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(f"{url}health", timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


def check_cloud_online(timeout=3.0):
    """Checks if the production cloud server is reachable within timeout."""
    try:
        req = urllib.request.Request(
            CLOUD_HEALTH_URL,
            headers={'User-Agent': 'ArgusDesktop/2.0 (Windows)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 301, 302, 307, 308)
    except Exception as e:
        print(f"[CloudCheck] Cloud server unreachable ({e}).")
        return False


def main():
    # Mark execution as running inside the desktop application wrapper
    os.environ['ARGUS_DESKTOP'] = '1'

    # Lazy import Flask app for local server fallback
    from app import app

    host = '127.0.0.1'
    local_port = find_available_port(5000)
    local_server_url = f"http://{host}:{local_port}/"

    print("================================================================")
    print("ARGUS CNC - ARGUS ATTENDANCE INTELLIGENCE V2.0.0")
    print("Checking Cloud Server Connectivity...")
    print(f"Cloud URL: {CLOUD_URL}")
    print("================================================================")

    # 1. Start local WSGI server as a background standby daemon thread
    server_thread = threading.Thread(
        target=start_wsgi_server,
        args=(app, host, local_port),
        daemon=True
    )
    server_thread.start()

    # 2. Check if the production cloud is reachable
    cloud_is_online = check_cloud_online(timeout=3.0)

    if cloud_is_online:
        target_url = CLOUD_URL
        window_title = 'Argus Attendance Intelligence (Cloud Connected)'
        print("[OK] Production Cloud Server is ONLINE. Connecting to live cloud...")
        print("  All latest web changes and features will reflect in real-time.")
    else:
        target_url = local_server_url
        window_title = 'Argus Attendance Intelligence (Offline Mode - Local Fallback)'
        print("[WARN] Notice: Cloud server is unreachable or device is offline.")
        print(f"[OK] Falling back to local offline server at: {local_server_url}")
        # Wait until local server responds before displaying window
        wait_for_server_ready(local_server_url)

    # 3. Configure PyWebView settings
    webview.settings['ALLOW_DOWNLOADS'] = True
    webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = False

    # 4. Resolve application window icon
    base_dir = get_base_dir()
    icon_candidates = [
        os.path.join(base_dir, 'static', 'favicon.ico'),
        os.path.join(base_dir, 'static', 'app_icon.ico'),
        os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else base_dir, 'static', 'favicon.ico')
    ]
    icon_path = next((p for p in icon_candidates if os.path.exists(p)), None)

    # 5. Create native desktop window
    window = webview.create_window(
        title=window_title,
        url=target_url,
        width=1366,
        height=860,
        min_size=(1024, 680),
        resizable=True,
        fullscreen=False,
        text_select=True,
        confirm_close=False
    )

    # 6. Background connectivity monitor:
    # If starting in offline mode, background thread detects when internet returns
    def monitor_connectivity():
        time.sleep(10)
        while True:
            try:
                current_url = window.get_current_url()
                if current_url and '127.0.0.1' in current_url:
                    if check_cloud_online(timeout=2.0):
                        print("[Network] Internet connection restored! Cloud server is available.")
            except Exception:
                pass
            time.sleep(20)

    monitor_thread = threading.Thread(target=monitor_connectivity, daemon=True)
    monitor_thread.start()

    # 7. Launch PyWebView with Windows Edge Chromium (WebView2)
    # private_mode=False ensures cookie persistence across app launches
    webview.start(gui='edgechromium', debug=False, private_mode=False)

    print("Desktop application window closed. Cleaning up and exiting.")
    sys.exit(0)


if __name__ == '__main__':
    main()
