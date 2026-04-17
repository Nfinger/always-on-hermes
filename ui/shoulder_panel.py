#!/usr/bin/env python3
import json
import queue
import threading
import time
import urllib.error
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox

BASE_URL = "http://127.0.0.1:8899"
POLL_SECONDS = 6


class HermesPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Always-On Hermes — Shoulder Panel")
        self.geometry("520x760")
        self.attributes("-topmost", True)

        self.session_id = None
        self.polling = False
        self.ui_queue = queue.Queue()

        self._build_ui()
        self.after(300, self._drain_ui_queue)

    def _build_ui(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        status_row = ttk.Frame(root)
        status_row.pack(fill="x", pady=(0, 8))
        self.status_var = tk.StringVar(value="Backend: checking...")
        ttk.Label(status_row, textvariable=self.status_var).pack(side="left")
        ttk.Button(status_row, text="Refresh", command=self.refresh_health).pack(side="right")

        session_box = ttk.LabelFrame(root, text="Session", padding=8)
        session_box.pack(fill="x", pady=(0, 8))

        self.title_var = tk.StringVar(value="Always-on session")
        self.mode_var = tk.StringVar(value="general")
        self.speaker_var = tk.StringVar(value="user")
        self.parent_var = tk.StringVar(value="342ca918aa048096bb08fccef2a94c49")

        ttk.Label(session_box, text="Title").grid(row=0, column=0, sticky="w")
        ttk.Entry(session_box, textvariable=self.title_var).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Label(session_box, text="Mode").grid(row=1, column=0, sticky="w")
        ttk.Combobox(session_box, textvariable=self.mode_var, values=["general", "meeting", "interview"], state="readonly", width=12).grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(4, 0))

        ttk.Label(session_box, text="Context notes (comma-separated)").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.context_entry = ttk.Entry(session_box)
        self.context_entry.insert(0, "always on assistant, Nate")
        self.context_entry.grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))

        row = ttk.Frame(session_box)
        row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(row, text="Start Session", command=self.start_session).pack(side="left")
        ttk.Button(row, text="Stop Poll", command=self.stop_poll).pack(side="left", padx=(6, 0))
        ttk.Button(row, text="Sync Notion", command=self.sync_notion).pack(side="right")

        session_box.columnconfigure(1, weight=1)

        transcript_box = ttk.LabelFrame(root, text="Transcript Input", padding=8)
        transcript_box.pack(fill="both", expand=False, pady=(0, 8))

        top = ttk.Frame(transcript_box)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Speaker").pack(side="left")
        ttk.Combobox(top, textvariable=self.speaker_var, values=["user", "other", "assistant"], state="readonly", width=10).pack(side="left", padx=(6, 8))
        ttk.Label(top, text="Notion Parent ID").pack(side="left")
        ttk.Entry(top, textvariable=self.parent_var, width=30).pack(side="left", padx=(6, 0), fill="x", expand=True)

        self.chunk_text = tk.Text(transcript_box, height=5, wrap="word")
        self.chunk_text.pack(fill="x")

        actions = ttk.Frame(transcript_box)
        actions.pack(fill="x", pady=(6, 0))
        ttk.Button(actions, text="Send Chunk", command=self.send_chunk).pack(side="left")
        ttk.Button(actions, text="Quick: mark important", command=lambda: self.quick_chunk("Important point flagged."))
        ttk.Button(actions, text="Quick: ask deeper", command=lambda: self.quick_chunk("Need a deeper follow-up here."))
        for w in actions.winfo_children()[1:]:
            w.pack(side="left", padx=(6, 0))

        suggestion_box = ttk.LabelFrame(root, text="Live Shoulder Output", padding=8)
        suggestion_box.pack(fill="both", expand=True)

        self.output = tk.Text(suggestion_box, height=18, wrap="word")
        self.output.pack(fill="both", expand=True)
        self.output.insert("end", "Suggestions will appear here once a session is active.\n")

        self.refresh_health()

    def _request(self, method, path, payload=None):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["content-type"] = "application/json"
        req = urllib.request.Request(f"{BASE_URL}{path}", data=data, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def refresh_health(self):
        try:
            out = self._request("GET", "/health")
            self.status_var.set(f"Backend: {'OK' if out.get('ok') else 'error'}")
        except Exception as e:
            self.status_var.set(f"Backend: offline ({e})")

    def start_session(self):
        title = self.title_var.get().strip() or "Always-on session"
        notes = [x.strip() for x in self.context_entry.get().split(",") if x.strip()]
        payload = {
            "title": title,
            "mode": self.mode_var.get(),
            "job_description": "",
            "rubric": [],
            "context_notes": notes,
        }
        try:
            out = self._request("POST", "/sessions", payload)
            self.session_id = out["session_id"]
            self._append(f"\n[session started] {self.session_id}\n")
            self._append(f"mode={out.get('mode','general')} title={out.get('title')}\n")
            self.start_poll()
        except Exception as e:
            messagebox.showerror("Session error", str(e))

    def send_chunk(self):
        if not self.session_id:
            messagebox.showwarning("No session", "Start a session first.")
            return
        text = self.chunk_text.get("1.0", "end").strip()
        if not text:
            return
        payload = {"speaker": self.speaker_var.get(), "text": text}
        try:
            self._request("POST", f"/sessions/{self.session_id}/chunks", payload)
            self._append(f"\n[{self.speaker_var.get()}] {text}\n")
            self.chunk_text.delete("1.0", "end")
            self.fetch_once()
        except Exception as e:
            messagebox.showerror("Chunk error", str(e))

    def quick_chunk(self, text):
        self.chunk_text.delete("1.0", "end")
        self.chunk_text.insert("1.0", text)
        self.send_chunk()

    def sync_notion(self):
        if not self.session_id:
            messagebox.showwarning("No session", "Start a session first.")
            return
        parent = self.parent_var.get().strip()
        if not parent:
            messagebox.showwarning("Missing parent", "Enter Notion parent page id.")
            return
        try:
            out = self._request("POST", f"/sessions/{self.session_id}/notion-sync", {"parent_page_id": parent})
            self._append(f"\n[notion synced] {out.get('page_url','(no url)')}\n")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            messagebox.showerror("Notion sync failed", body)
        except Exception as e:
            messagebox.showerror("Notion sync failed", str(e))

    def start_poll(self):
        if self.polling:
            return
        self.polling = True

        def loop():
            while self.polling:
                if self.session_id:
                    try:
                        out = self._request("POST", f"/sessions/{self.session_id}/ambient-suggestions", {"max_questions": 3})
                        self.ui_queue.put(out)
                    except Exception as e:
                        self.ui_queue.put({"error": str(e)})
                time.sleep(POLL_SECONDS)

        threading.Thread(target=loop, daemon=True).start()

    def stop_poll(self):
        self.polling = False
        self._append("\n[polling stopped]\n")

    def fetch_once(self):
        if not self.session_id:
            return
        try:
            out = self._request("POST", f"/sessions/{self.session_id}/ambient-suggestions", {"max_questions": 3})
            self._render_suggestions(out)
        except Exception as e:
            self._append(f"\n[error] {e}\n")

    def _drain_ui_queue(self):
        while True:
            try:
                out = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            self._render_suggestions(out)
        self.after(300, self._drain_ui_queue)

    def _render_suggestions(self, out):
        if "error" in out:
            self._append(f"\n[poll error] {out['error']}\n")
            return

        suggestions = out.get("suggestions", [])
        actions = out.get("actions", [])
        risks = out.get("risks", [])

        self._append("\n=== Live Suggestions ===\n")
        for i, s in enumerate(suggestions, start=1):
            self._append(f"{i}. {s}\n")
        if actions:
            self._append("Actions:\n")
            for a in actions:
                self._append(f"- {a}\n")
        if risks:
            self._append("Risks:\n")
            for r in risks:
                self._append(f"- {r}\n")

    def _append(self, text):
        self.output.insert("end", text)
        self.output.see("end")


if __name__ == "__main__":
    app = HermesPanel()
    app.mainloop()
