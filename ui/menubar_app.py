#!/usr/bin/env python3
import json
import os
import subprocess
import threading
import urllib.request
import webbrowser
from pathlib import Path

import rumps
from pynput import keyboard

BASE_URL = "http://127.0.0.1:8899"
BASE_DIR = str(Path(__file__).resolve().parent.parent)


def _api(method: str, path: str, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


class HermesMenubar(rumps.App):
    def __init__(self):
        super().__init__("🧠", title="🧠", quit_button=None)
        self.menu = [
            "Open Native Overlay",
            "Open Web Panel",
            "Toggle Privacy Mute",
            "Mute: unknown",
            None,
            "Quit Hermes Companion",
        ]
        self.default_session_id = None
        self._hotkey_pressed = set()
        self._listener = None
        self._start_hotkey_listener()
        self._refresh_mute_label()
        self._auto_start_default_session()
        self._timer = rumps.Timer(self._poll_refresh, 5)
        self._timer.start()

    def _start_hotkey_listener(self):
        def on_press(key):
            self._hotkey_pressed.add(key)
            combos = [
                {keyboard.Key.cmd, keyboard.Key.alt},
                {keyboard.Key.cmd_l, keyboard.Key.alt_l},
                {keyboard.Key.cmd_r, keyboard.Key.alt_r},
            ]
            cmd_alt_active = any(all(k in self._hotkey_pressed for k in combo) for combo in combos)
            if not cmd_alt_active:
                return
            if key in {keyboard.KeyCode.from_char("m"), keyboard.KeyCode.from_char("M")}:
                threading.Thread(target=lambda: self.toggle_privacy_mute(None), daemon=True).start()

        def on_release(key):
            self._hotkey_pressed.discard(key)

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()

    def _refresh_mute_label(self):
        try:
            out = _api("GET", "/runtime-state")
            muted = bool(out.get("muted"))
            self.menu["Mute: unknown"].title = f"Mute: {'ON' if muted else 'OFF'}"
            self.title = "🔇" if muted else "🧠"
        except Exception:
            self.menu["Mute: unknown"].title = "Mute: backend offline"
            self.title = "⚠️"

    def _poll_refresh(self, _):
        self._refresh_mute_label()

    def _beep(self, times: int = 1):
        try:
            subprocess.Popen(["osascript", "-e", f"beep {max(1, min(times, 3))}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _auto_start_default_session(self):
        enabled = os.getenv("AUTO_START_DEFAULT_SESSION", "1").strip().lower() in {"1", "true", "yes", "on"}
        if not enabled:
            return
        try:
            title = os.getenv("AUTO_START_SESSION_TITLE", "Always-on session")
            notes = os.getenv("AUTO_START_SESSION_NOTES", "always on assistant, Nate")
            out = _api(
                "POST",
                "/sessions",
                {
                    "title": title,
                    "mode": "general",
                    "job_description": "",
                    "rubric": [],
                    "context_notes": [x.strip() for x in notes.split(",") if x.strip()],
                },
            )
            self.default_session_id = out.get("session_id")
            if self.default_session_id:
                rumps.notification("Always-On Hermes", "Default session started", self.default_session_id)
        except Exception:
            # Non-fatal: backend may be starting.
            pass

    @rumps.clicked("Open Native Overlay")
    def open_overlay(self, _):
        try:
            subprocess.Popen([f"{BASE_DIR}/scripts/hermes_shoulderctl.sh", "overlay-install"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.Popen([f"{BASE_DIR}/scripts/hermes_shoulderctl.sh", "overlay-start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            rumps.notification("Always-On Hermes", "Overlay start failed", str(e))

    @rumps.clicked("Open Web Panel")
    def open_panel(self, _):
        webbrowser.open(f"{BASE_URL}/panel")

    @rumps.clicked("Toggle Privacy Mute")
    def toggle_privacy_mute(self, _):
        try:
            current = _api("GET", "/runtime-state")
            muted = bool(current.get("muted"))
            out = _api("POST", "/runtime-state", {"muted": not muted})
            now = bool(out.get("muted"))
            self._refresh_mute_label()
            self._beep(2 if now else 1)
            rumps.notification(
                "Always-On Hermes",
                "Privacy Mute",
                "ON (mic blocked)" if now else "OFF (mic live)",
            )
        except Exception as e:
            rumps.notification("Always-On Hermes", "Toggle failed", str(e))

    @rumps.clicked("Mute: unknown")
    def refresh_label(self, _):
        self._refresh_mute_label()

    @rumps.clicked("Quit Hermes Companion")
    def quit_app(self, _):
        if self._listener:
            self._listener.stop()
        rumps.quit_application()


if __name__ == "__main__":
    app = HermesMenubar()
    app.run()
