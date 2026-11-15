"""Local synthetic-media lab. The HTTP API controls FFmpeg; SRT carries media."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


def utc():
    return datetime.now(timezone.utc).isoformat()


class Conflict(Exception):
    pass


class WorkflowManager:
    def __init__(self, output=ROOT / "artifacts", ffmpeg=None, ffprobe=None):
        self.output = Path(output)
        self.ffmpeg = ffmpeg or os.environ.get("FFMPEG_PATH") or shutil.which("ffmpeg")
        self.ffprobe = ffprobe or os.environ.get("FFPROBE_PATH") or shutil.which("ffprobe")
        self.lock = threading.RLock()
        self.jobs = {}

    def start(self, seconds):
        if type(seconds) is not int or not 3 <= seconds <= 15:
            raise ValueError("seconds must be an integer from 3 to 15")
        if not self.ffmpeg or not self.ffprobe:
            raise ValueError("FFmpeg and FFprobe are required; see README setup")
        with self.lock:
            if any(j["status"] in ("starting", "running", "stopping") for j in self.jobs.values()):
                raise Conflict("One workflow at a time; stop or wait for the active job")
            if len(self.jobs) >= 20:
                raise Conflict("This lab allows 20 jobs per server run; restart the server to reset history")
            ident = str(uuid.uuid4())
            job = dict(id=ident, seconds=seconds, status="starting", created_at=utc(),
                       finished_at=None, error=None, probe=None, events=[],
                       stop=threading.Event(), thread=None)
            self.jobs[ident] = job
            thread = threading.Thread(target=self._run, args=(job,), daemon=True)
            job["thread"] = thread
            thread.start()
            return self.get(ident)

    def get(self, ident):
        with self.lock:
            job = self.jobs[ident]
            return {k: v for k, v in job.items() if k not in ("stop", "thread")}

    def list(self):
        with self.lock:
            return [self.get(i) for i in reversed(self.jobs)]

    def stop(self, ident):
        with self.lock:
            job = self.jobs[ident]
            if job["status"] in ("starting", "running", "stopping"):
                job["status"] = "stopping"
                job["stop"].set()
            return self.get(ident)

    def wait(self, ident, timeout=45):
        self.jobs[ident]["thread"].join(timeout)
        if self.jobs[ident]["thread"].is_alive():
            raise TimeoutError("Workflow worker did not finish")
        return self.get(ident)

    def close(self):
        with self.lock:
            ids = list(self.jobs)
            for ident in ids:
                self.stop(ident)
        for ident in ids:
            self.wait(ident)

    def _event(self, job, message):
        with self.lock:
            job["events"].append(dict(at=utc(), message=message))

    @staticmethod
    def _terminate(process):
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

    def _run(self, job):
        receiver = sender = None
        directory = self.output / job["id"]
        directory.mkdir(parents=True, exist_ok=False)
        try:
            # Reserve a candidate ephemeral UDP port. FFmpeg performs the actual bind.
            # A bind race with another local program is reported as a failed workflow.
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            recording = directory / "recording.mp4"
            common = [self.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "warning", "-y"]
            receive = common + ["-i", f"srt://127.0.0.1:{port}?mode=listener&latency=120000&timeout=10000000",
                                "-t", str(job["seconds"]), "-c", "copy", "-movflags", "+faststart", str(recording)]
            send = common + ["-re", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25",
                             "-re", "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000",
                             "-t", str(job["seconds"] + 3), "-c:v", "libx264", "-preset", "ultrafast",
                             "-tune", "zerolatency", "-pix_fmt", "yuv420p", "-g", "25", "-b:v", "800k",
                             "-c:a", "aac", "-b:a", "96k", "-f", "mpegts",
                             f"srt://127.0.0.1:{port}?mode=caller&latency=120000&pkt_size=1316"]
            self._event(job, "Starting loopback SRT receiver; latency setting is 120000 microseconds")
            with (directory / "receiver.log").open("wb") as rlog, (directory / "sender.log").open("wb") as slog:
                receiver = subprocess.Popen(receive, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=rlog)
                if job["stop"].wait(.4):
                    return
                if receiver.poll() is not None:
                    raise RuntimeError("Receiver exited before sender startup; inspect receiver.log")
                sender = subprocess.Popen(send, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=slog)
                with self.lock:
                    if not job["stop"].is_set():
                        job["status"] = "running"
                self._event(job, "Synthetic H.264 video and AAC audio sender started over MPEG-TS/SRT")
                deadline = time.monotonic() + job["seconds"] + 20
                while receiver.poll() is None:
                    if job["stop"].wait(.1):
                        return
                    if time.monotonic() > deadline:
                        raise TimeoutError("Receiver exceeded the bounded workflow deadline")
                    if sender.poll() not in (None, 0):
                        # The bounded receiver may close SRT before its exit is visible
                        # to this polling loop. Confirm receiver success before treating
                        # the sender's broken-pipe exit as an actual source failure.
                        try:
                            receiver.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            raise RuntimeError("Sender failed before receiver completion; inspect sender.log")
                        break
                if receiver.returncode != 0:
                    raise RuntimeError("Receiver failed; inspect receiver.log")
                self._terminate(sender)  # Receiver owns the planned recording duration.
                result = subprocess.run([self.ffprobe, "-v", "error", "-show_entries",
                                         "stream=codec_name,codec_type,width,height:format=duration",
                                         "-of", "json", str(recording)], capture_output=True, text=True, timeout=10, check=True)
                probe = json.loads(result.stdout)
                codecs = {s["codec_type"]: s["codec_name"] for s in probe.get("streams", [])}
                if codecs.get("video") != "h264" or codecs.get("audio") != "aac":
                    raise RuntimeError("Recording did not contain the expected H.264 and AAC streams")
                if float(probe["format"]["duration"]) < job["seconds"] - 1:
                    raise RuntimeError("Recording duration was shorter than the acceptance threshold")
                (directory / "probe.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
                with self.lock:
                    job["probe"] = probe
                    job["status"] = "completed"
                self._event(job, "Recording verified by FFprobe; controlled sender shutdown is expected")
        except Exception as error:
            with self.lock:
                job["status"] = "failed"
                job["error"] = f"{type(error).__name__}: {error}"
            self._event(job, "Workflow failed; inspect local receiver/sender logs")
        finally:
            self._terminate(sender)
            self._terminate(receiver)
            with self.lock:
                if job["stop"].is_set():
                    job["status"] = "stopped"
                job["finished_at"] = utc()
                summary = self.get(job["id"])
            (directory / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


class LabServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, manager):
        self.manager = manager
        self.token = secrets.token_urlsafe(32)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Avoid logging the dashboard token or client-supplied request content.

    def _respond(self, code, value, kind="application/json"):
        body = json.dumps(value).encode() if kind == "application/json" else value
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; object-src 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self):
        return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def do_GET(self):
        if not self._host_ok():
            return self._respond(403, {"error": "Only the local lab hostname is allowed"})
        path = urlsplit(self.path).path
        if path in ("/", "/app.js", "/style.css"):
            name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[path]
            kind = {"/": "text/html; charset=utf-8", "/app.js": "text/javascript", "/style.css": "text/css"}[path]
            content = (ROOT / "web" / name).read_bytes().replace(b"__TOKEN__", self.server.token.encode())
            return self._respond(200, content, kind)
        if path == "/api/health":
            return self._respond(200, {"status": "ok", "media_tools_configured": bool(self.server.manager.ffmpeg and self.server.manager.ffprobe)})
        if path == "/api/jobs":
            return self._respond(200, self.server.manager.list())
        parts = path.strip("/").split("/")
        try:
            if len(parts) == 3 and parts[:2] == ["api", "jobs"]:
                return self._respond(200, self.server.manager.get(parts[2]))
            if len(parts) == 3 and parts[0] == "media" and parts[2] == "recording.mp4":
                job = self.server.manager.get(parts[1])
                if job["status"] != "completed":
                    return self._respond(409, {"error": "Recording is not complete"})
                return self._respond(200, (self.server.manager.output / job["id"] / "recording.mp4").read_bytes(), "video/mp4")
        except KeyError:
            pass
        self._respond(404, {"error": "Not found"})

    def do_POST(self):
        if not self._host_ok() or not secrets.compare_digest(self.headers.get("X-Lab-Token", ""), self.server.token):
            return self._respond(403, {"error": "Local dashboard token required"})
        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("Use application/json")
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1024:
                raise ValueError("JSON request body must be 1 to 1024 bytes")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object")
            path = urlsplit(self.path).path
            if path == "/api/jobs":
                if set(body) != {"seconds"}:
                    raise ValueError("Only the seconds field is accepted")
                return self._respond(202, self.server.manager.start(body["seconds"]))
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "stop":
                return self._respond(200, self.server.manager.stop(parts[2]))
            return self._respond(404, {"error": "Not found"})
        except Conflict as error:
            self._respond(409, {"error": str(error)})
        except KeyError:
            self._respond(404, {"error": "Job not found"})
        except (ValueError, json.JSONDecodeError) as error:
            self._respond(400, {"error": str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5190)
    args = parser.parse_args()
    manager = WorkflowManager()
    server = LabServer(("127.0.0.1", args.port), manager)
    print(f"Media Workflow Lab: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        manager.close()


if __name__ == "__main__":
    main()
