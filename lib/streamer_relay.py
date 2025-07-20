#!/usr/bin/env python3
import os
import threading
import http.server
import socketserver

PORT = 8080
FRAME_LOCK = threading.Lock()
LATEST_FRAME = None
stop_event = threading.Event()

def set_latest_frame(frame):
    global LATEST_FRAME
    with FRAME_LOCK:
        LATEST_FRAME = frame

def get_latest_frame():
    with FRAME_LOCK:
        return LATEST_FRAME

def read_stdin_loop():
    buffer = bytearray()
    while not stop_event.is_set():
        try:
            chunk = os.read(0, 4096)
            if not chunk:
                break
            buffer.extend(chunk)
            while True:
                start = buffer.find(b'\xff\xd8')  # JPEG start
                end = buffer.find(b'\xff\xd9')    # JPEG end
                if start != -1 and end != -1 and end > start:
                    frame = buffer[start:end + 2]
                    set_latest_frame(frame)
                    buffer = buffer[end + 2:]
                else:
                    break
        except Exception as e:
            print(f"[ERROR] Read error: {e}")
            break

class MJPEGHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/':
            self.send_error(404)
            return

        print(f"[INFO] Client connected: {self.client_address}")
        self.send_response(200)
        self.send_header("Content-type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        try:
            while not stop_event.is_set():
                frame = get_latest_frame()
                if frame:
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            print(f"[WARN] Client disconnected: {self.client_address}")
        except Exception as e:
            print(f"[ERROR] Stream error: {e}")

def run_http_server():
    with socketserver.ThreadingTCPServer(("", PORT), MJPEGHandler) as httpd:
        print(f"[INFO] MJPEG relay server running at http://0.0.0.0:{PORT}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[INFO] Caught Ctrl+C — shutting down cleanly.")
            stop_event.set()
        finally:
            httpd.shutdown()

if __name__ == "__main__":
    read_thread = threading.Thread(target=read_stdin_loop)
    read_thread.start()
    run_http_server()
    read_thread.join()
