#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.request
from datetime import datetime

import AppKit
import objc
from Foundation import NSObject, NSTimer
from PyObjCTools import AppHelper

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8899")
REFRESH_SECS = float(os.getenv("OVERLAY_REFRESH_SECS", "4"))


def api(method: str, path: str, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


class OverlayController(NSObject):
    def init(self):
        self = objc.super(OverlayController, self).init()
        if self is None:
            return None
        self.session_id = None
        self.muted = False
        self.window = None
        self.status_label = None
        self.text_view = None
        self.mute_button = None
        return self

    def applicationDidFinishLaunching_(self, _notification):
        self._build_window()
        self._ensure_session()
        self._refresh_runtime_state()
        self._fetch_and_render()

        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            REFRESH_SECS,
            self,
            "tick:",
            None,
            True,
        )

    def _build_window(self):
        frame = AppKit.NSMakeRect(0.0, 0.0, 460.0, 320.0)
        style = AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskClosable
        self.window = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            style,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("Hermes Overlay")
        self.window.setFloatingPanel_(True)
        self.window.setHidesOnDeactivate_(False)
        self.window.setLevel_(AppKit.NSFloatingWindowLevel)
        self.window.setReleasedWhenClosed_(False)

        screen = AppKit.NSScreen.mainScreen().visibleFrame()
        x = screen.origin.x + screen.size.width - 460 - 20
        y = screen.origin.y + screen.size.height - 320 - 70
        self.window.setFrameOrigin_((x, y))

        content = self.window.contentView()

        self.status_label = AppKit.NSTextField.alloc().initWithFrame_(AppKit.NSMakeRect(12, 286, 430, 20))
        self.status_label.setBezeled_(False)
        self.status_label.setDrawsBackground_(False)
        self.status_label.setEditable_(False)
        self.status_label.setSelectable_(False)
        self.status_label.setStringValue_("Booting…")
        content.addSubview_(self.status_label)

        self.mute_button = AppKit.NSButton.alloc().initWithFrame_(AppKit.NSMakeRect(350, 8, 96, 28))
        self.mute_button.setTitle_("Mute: OFF")
        self.mute_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
        self.mute_button.setTarget_(self)
        self.mute_button.setAction_("toggleMute:")
        content.addSubview_(self.mute_button)

        scroll = AppKit.NSScrollView.alloc().initWithFrame_(AppKit.NSMakeRect(12, 44, 436, 236))
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(AppKit.NSBezelBorder)

        self.text_view = AppKit.NSTextView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, 436, 236))
        self.text_view.setEditable_(False)
        self.text_view.setString_("Live suggestions will appear here.\n")
        scroll.setDocumentView_(self.text_view)
        content.addSubview_(scroll)

        self.window.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    def _set_status(self, text: str):
        if self.status_label is not None:
            self.status_label.setStringValue_(text)

    def _paint_mute(self):
        self.mute_button.setTitle_(f"Mute: {'ON' if self.muted else 'OFF'}")

    def _ensure_session(self):
        if self.session_id:
            return
        try:
            out = api(
                "POST",
                "/sessions",
                {
                    "title": "Always-on overlay",
                    "mode": "general",
                    "job_description": "",
                    "rubric": [],
                    "context_notes": ["overlay", "always on assistant"],
                },
            )
            self.session_id = out.get("session_id")
            if self.session_id:
                self._set_status(f"session: {self.session_id[:8]}…")
        except Exception as e:
            self._set_status(f"backend offline: {e}")

    def _refresh_runtime_state(self):
        try:
            out = api("GET", "/runtime-state")
            self.muted = bool(out.get("muted"))
            self._paint_mute()
        except Exception:
            pass

    def _fetch_and_render(self):
        if not self.session_id:
            self._ensure_session()
            if not self.session_id:
                return

        try:
            out = api("POST", f"/sessions/{self.session_id}/ambient-suggestions", {"max_questions": 2})
        except urllib.error.HTTPError as e:
            self._set_status(f"http {e.code}")
            return
        except Exception as e:
            self._set_status(f"poll error: {e}")
            return

        suggestions = out.get("suggestions", [])
        actions = out.get("actions", [])

        lines = [f"Updated {datetime.now().strftime('%H:%M:%S')}", ""]
        if suggestions:
            lines.append("Suggestions:")
            for i, s in enumerate(suggestions, 1):
                lines.append(f"{i}. {s}")
        else:
            lines.append("No suggestions yet.")

        if actions:
            lines.append("")
            lines.append("Actions:")
            for a in actions[:3]:
                lines.append(f"- {a}")

        self.text_view.setString_("\n".join(lines))
        self._set_status(f"session: {self.session_id[:8]}… | {'MUTED' if self.muted else 'live'}")

    def toggleMute_(self, _sender):
        try:
            out = api("POST", "/runtime-state", {"muted": not self.muted})
            self.muted = bool(out.get("muted"))
            self._paint_mute()
            self._set_status(f"privacy mute {'ON' if self.muted else 'OFF'}")
        except Exception as e:
            self._set_status(f"mute error: {e}")

    def tick_(self, _timer):
        self._refresh_runtime_state()
        self._fetch_and_render()


if __name__ == "__main__":
    app = AppKit.NSApplication.sharedApplication()
    delegate = OverlayController.alloc().init()
    app.setDelegate_(delegate)
    AppHelper.runEventLoop()
