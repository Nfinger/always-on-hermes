import Foundation
import SwiftUI
import AppKit

@MainActor
final class HermesModel: ObservableObject {
    static let shared = HermesModel()

    @Published var backendOnline = false
    @Published var muted = false
    @Published var statusLine = "Starting…"
    @Published var suggestions: [String] = []
    @Published var actions: [String] = []
    @Published var sessionID: String?
    @Published var refreshSeconds: Double = 4
    @Published var backendURLString: String = UserDefaults.standard.string(forKey: "hermes.backendURL") ?? "http://127.0.0.1:8899"

    private var baseURL: URL { URL(string: backendURLString) ?? URL(string: "http://127.0.0.1:8899")! }
    private var timerTask: Task<Void, Never>?
    private var sessionTitle = "Always-on overlay"

    init() {
        Task {
            await ensureBackendRunning()
            await refreshAll()
            startPolling()
        }
    }

    func saveBackendURL() {
        UserDefaults.standard.set(backendURLString, forKey: "hermes.backendURL")
        sessionID = nil
        statusLine = "Backend URL updated"
        Task { await refreshAll() }
    }

    func openLogsFolder() {
        let logsURL = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs")
        NSWorkspace.shared.open(logsURL)
    }

    func startPolling() {
        timerTask?.cancel()
        timerTask = Task {
            while !Task.isCancelled {
                await refreshAll()
                try? await Task.sleep(for: .seconds(refreshSeconds))
            }
        }
    }

    func refreshAll() async {
        await checkHealth()
        await fetchRuntimeState()
        await ensureSession()
        await fetchSuggestions()
    }

    func ensureBackendRunning() async {
        if await healthOK() { return }

        _ = bootstrapPayloadIfNeeded()

        let ctl = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".hermes/tools/interview-copilot/scripts/hermes_shoulderctl.sh")

        guard FileManager.default.isExecutableFile(atPath: ctl.path) else {
            statusLine = "Backend control script missing"
            return
        }

        runShell([ctl.path, "install"])
        runShell([ctl.path, "menubar-install"])
        runShell([ctl.path, "overlay-install"])
        runShell([ctl.path, "start"])
        runShell([ctl.path, "overlay-start"])

        try? await Task.sleep(for: .seconds(1.2))
        backendOnline = await healthOK()
        statusLine = backendOnline ? "Backend started" : "Backend start failed"
    }

    func restartBackend() async {
        let ctl = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".hermes/tools/interview-copilot/scripts/hermes_shoulderctl.sh")
        guard FileManager.default.isExecutableFile(atPath: ctl.path) else {
            statusLine = "Backend control script missing"
            return
        }
        runShell([ctl.path, "restart"])
        try? await Task.sleep(for: .seconds(1.2))
        await refreshAll()
    }

    func toggleMute() async {
        do {
            let payload = ["muted": !muted]
            let data = try JSONSerialization.data(withJSONObject: payload)
            var req = URLRequest(url: baseURL.appendingPathComponent("runtime-state"))
            req.httpMethod = "POST"
            req.httpBody = data
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")

            let (respData, _) = try await URLSession.shared.data(for: req)
            if let dict = try JSONSerialization.jsonObject(with: respData) as? [String: Any],
               let now = dict["muted"] as? Bool {
                muted = now
                statusLine = now ? "Privacy mute ON" : "Privacy mute OFF"
                NSSound.beep()
            }
        } catch {
            statusLine = "Mute toggle failed: \(error.localizedDescription)"
        }
    }

    private func checkHealth() async {
        backendOnline = await healthOK()
        if !backendOnline {
            statusLine = "Backend offline"
        }
    }

    private func healthOK() async -> Bool {
        do {
            let (_, response) = try await URLSession.shared.data(from: baseURL.appendingPathComponent("health"))
            guard let http = response as? HTTPURLResponse else { return false }
            return (200..<300).contains(http.statusCode)
        } catch {
            return false
        }
    }

    private func fetchRuntimeState() async {
        do {
            let (data, _) = try await URLSession.shared.data(from: baseURL.appendingPathComponent("runtime-state"))
            if let dict = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let m = dict["muted"] as? Bool {
                muted = m
            }
        } catch {
            // ignore
        }
    }

    private func ensureSession() async {
        if sessionID != nil { return }
        do {
            let payload: [String: Any] = [
                "title": sessionTitle,
                "mode": "general",
                "job_description": "",
                "rubric": [],
                "context_notes": ["native overlay", "always on assistant"]
            ]
            let data = try JSONSerialization.data(withJSONObject: payload)
            var req = URLRequest(url: baseURL.appendingPathComponent("sessions"))
            req.httpMethod = "POST"
            req.httpBody = data
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            let (respData, _) = try await URLSession.shared.data(for: req)

            if let dict = try JSONSerialization.jsonObject(with: respData) as? [String: Any],
               let sid = dict["session_id"] as? String {
                sessionID = sid
            }
        } catch {
            statusLine = "Session create failed"
        }
    }

    private func fetchSuggestions() async {
        guard let sid = sessionID else { return }
        do {
            let payload = ["max_questions": 2]
            let data = try JSONSerialization.data(withJSONObject: payload)

            var req = URLRequest(url: baseURL.appendingPathComponent("sessions/\(sid)/ambient-suggestions"))
            req.httpMethod = "POST"
            req.httpBody = data
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")

            let (respData, _) = try await URLSession.shared.data(for: req)
            if let dict = try JSONSerialization.jsonObject(with: respData) as? [String: Any] {
                suggestions = dict["suggestions"] as? [String] ?? []
                actions = dict["actions"] as? [String] ?? []
                statusLine = "\(backendOnline ? "Live" : "Offline") • \(muted ? "Muted" : "Listening")"
            }
        } catch {
            statusLine = "Suggestion poll failed"
        }
    }

    private func bootstrapPayloadIfNeeded() -> Bool {
        let fm = FileManager.default
        let targetRoot = fm.homeDirectoryForCurrentUser
            .appendingPathComponent(".hermes/tools/interview-copilot", isDirectory: true)
        let targetCtl = targetRoot.appendingPathComponent("scripts/hermes_shoulderctl.sh")

        if fm.isExecutableFile(atPath: targetCtl.path) {
            return true
        }

        guard let payloadRoot = Bundle.main.resourceURL?.appendingPathComponent("payload", isDirectory: true),
              fm.fileExists(atPath: payloadRoot.path) else {
            statusLine = "Bundled payload missing"
            return false
        }

        _ = runProcess("/bin/mkdir", ["-p", targetRoot.deletingLastPathComponent().path])
        let rsyncResult = runProcess("/usr/bin/rsync", ["-a", "--delete", payloadRoot.path + "/", targetRoot.path + "/"])
        if rsyncResult != 0 {
            statusLine = "Payload sync failed"
            return false
        }

        _ = runProcess("/bin/chmod", ["+x", targetCtl.path])
        statusLine = "Installed bundled backend"
        return true
    }

    @discardableResult
    private func runProcess(_ executable: String, _ args: [String]) -> Int32 {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: executable)
        proc.arguments = args
        proc.standardOutput = Pipe()
        proc.standardError = Pipe()
        do {
            try proc.run()
            proc.waitUntilExit()
            return proc.terminationStatus
        } catch {
            return -1
        }
    }

    private func runShell(_ args: [String]) {
        guard let first = args.first else { return }
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: first)
        proc.arguments = Array(args.dropFirst())
        proc.standardOutput = Pipe()
        proc.standardError = Pipe()
        try? proc.run()
    }
}
