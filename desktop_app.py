"""
ARGUS TECHNOLOGIES - Desktop Application Launcher
Runs the Flask Attendance & Operations Management Web Application inside a native,
dedicated desktop window (powered by Microsoft Edge WebView2 via PyWebView):
- Runs in its own desktop window: NO browser address bar, NO tabs, NO bookmarks.
- Automatic free port discovery & multi-threaded Waitress WSGI background server.
- Full WebRTC camera & microphone hardware access for Face AI and Voice Recording.
- Seamless, clean process shutdown when the desktop window is closed.
"""

import os
import sys
import time
import socket
import threading
import urllib.request
import webview
from waitress import serve


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


def main():
    # Mark execution as running inside the desktop application wrapper
    os.environ['ARGUS_DESKTOP'] = '1'

    # Lazy import Flask app to ensure all paths are initialized
    from app import app

    host = '127.0.0.1'
    port = find_available_port(5000)
    server_url = f"http://{host}:{port}/"

    print("================================================================")
    print("ARGUS TECHNOLOGIES - AI ATTENDANCE DESKTOP APPLICATION")
    print(f"Embedded Server URL: {server_url}")
    print("Initializing Native Application Window (WebView2)...")
    print("================================================================")

    # 1. Start Waitress WSGI server in background daemon thread
    server_thread = threading.Thread(
        target=start_wsgi_server,
        args=(app, host, port),
        daemon=True
    )
    server_thread.start()

    # 2. Wait until server is healthy and responding
    if not wait_for_server_ready(server_url):
        print("Notice: Proceeding with window launch...")

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
        title='ARGUS TECHNOLOGIES - AI Attendance & Operations Management',
        url=server_url,
        width=1366,
        height=860,
        min_size=(1024, 680),
        resizable=True,
        fullscreen=False,
        text_select=True,
        confirm_close=False
    )

    # 6. Launch PyWebView with Windows Edge Chromium (WebView2)
    # private_mode=False ensures cookie persistence across app launches
    webview.start(gui='edgechromium', debug=False, private_mode=False)

    print("Desktop application window closed. Cleaning up and exiting.")
    sys.exit(0)


if __name__ == '__main__':
    main()
