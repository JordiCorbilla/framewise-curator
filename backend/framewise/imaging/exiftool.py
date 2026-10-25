"""Bounded, per-thread ExifTool stay-open sessions with binary-safe output and deadlines."""

import queue
import subprocess
import threading
import time
import uuid

_local = threading.local()
_sessions = set()
_lock = threading.Lock()


class ExifToolSession:
    def __init__(self, executable):
        self.closed = False
        self.executable = executable
        self.output = queue.Queue(maxsize=32)
        self.process = subprocess.Popen(
            [executable, "-stay_open", "True", "-@", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._read, daemon=True, name="exiftool-output").start()

    def _read(self):
        while not self.closed:
            chunk = self.process.stdout.read1(65536)
            while not self.closed:
                try:
                    self.output.put(chunk, timeout=0.25)
                    break
                except queue.Full:
                    continue
            if not chunk:
                return

    def execute(self, arguments, timeout):
        token = str(uuid.uuid4().int)
        marker = f"{{ready{token}}}".encode()
        if any("\n" in str(value) or "\r" in str(value) for value in arguments):
            raise ValueError("Unsupported newline in ExifTool argument")
        command = "\n".join(["-charset", "filename=UTF8", *map(str, arguments), f"-execute{token}"]) + "\n"
        self.process.stdin.write(command.encode("utf-8"))
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        data = bytearray()
        while True:
            try:
                chunk = self.output.get(timeout=max(0.001, deadline - time.monotonic()))
            except queue.Empty as exc:
                self.close()
                raise TimeoutError("ExifTool processing timed out") from exc
            if not chunk:
                self.close()
                raise RuntimeError("ExifTool exited unexpectedly")
            data.extend(chunk)
            start = data.find(marker)
            if start >= 0 and b"\n" in data[start + len(marker) :]:
                return bytes(data[:start])
            if len(data) > 128 * 1024 * 1024:
                self.close()
                raise ValueError("Embedded preview exceeds the 128 MB safety limit")
            if time.monotonic() >= deadline:
                self.close()
                raise TimeoutError("ExifTool processing timed out")

    def close(self):
        if not self.closed:
            self.closed = True
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process.stdin.close()
            self.process.stdout.close()


def execute(executable, arguments, timeout=60):
    session = getattr(_local, "session", None)
    if session is None or session.closed or session.executable != executable:
        session = ExifToolSession(executable)
        _local.session = session
        with _lock:
            _sessions.add(session)
    return session.execute(arguments, timeout)


def close_all():
    with _lock:
        sessions = list(_sessions)
        _sessions.clear()
    for session in sessions:
        session.close()
