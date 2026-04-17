import Foundation
import SwiftUI
import AppKit

struct ProcessResult {
    let code: Int32
    let stdout: String
    let stderr: String
}

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
    @Published var startupDetails = ""
    @Published var launchAtLogin = false

    private var baseURL: URL { URL(string: backendURLString) ?? URL(string: "http://127.0.0.1:8899")! }
    private var timerTask: Task<Void, Never>?
    private var sessionTitle = "Always-on overlay"
    private var isEnsuringBackend = false

    private var logsDirectoryURL: URL {
        let dir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/AlwaysOnHermes", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    private var appLogURL: URL {
        logsDirectoryURL.appendingPathComponent("app.log")
    }

    private var diagnosticsURL: URL {
        logsDirectoryURL.appendingPathComponent("diagnostics.txt")
    }

    private var loginItemPlistURL: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/LaunchAgents/com.nate.alwaysonhermes.native-app.plist")
    }

    init() {
        appendLog("app launch")
        launchAtLogin = FileManager.default.fileExists(atPath: loginItemPlistURL.path)
        cleanupLegacyAgents()
        Task {
            await ensureBackendRunning(reason: "initial")
            await refreshAll()
            startPolling()
        }
    }

    func saveBackendURL() {
        UserDefaults.standard.set(backendURLString, forKey: "hermes.backendURL")
        sessionID = nil
        statusLine = "Backend URL updated"
        appendLog("backend URL set to \(backendURLString)")
        Task { await refreshAll() }
    }

    func openLogsFolder() {
        NSWorkspace.shared.open(logsDirectoryURL)
    }

    func openDiagnosticsReport() {
        Task {
            await generateDiagnosticsReport()
            NSWorkspace.shared.open(diagnosticsURL)
        }
    }

    func setLaunchAtLogin(_ enabled: Bool) {
        if enabled {
            let script = """
<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
  <key>Label</key>
  <string>com.nate.alwaysonhermes.native-app</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/open</string>
    <string>-a</string>
    <string>Always-on Hermes</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
</dict>
</plist>
"""
            do {
                let launchAgentsDir = loginItemPlistURL.deletingLastPathComponent()
                try FileManager.default.createDirectory(at: launchAgentsDir, withIntermediateDirectories: true)
                try script.write(to: loginItemPlistURL, atomically: true, encoding: .utf8)
                _ = runProcess("/bin/launchctl", ["unload", loginItemPlistURL.path])
                _ = runProcess("/bin/launchctl", ["load", loginItemPlistURL.path])
                launchAtLogin = true
                statusLine = "Launch at login enabled"
                appendLog("launch at login enabled")
            } catch {
                launchAtLogin = false
                statusLine = "Failed to enable launch at login"
                appendLog(statusLine + ": \(error.localizedDescription)")
            }
        } else {
            _ = runProcess("/bin/launchctl", ["unload", loginItemPlistURL.path])
            try? FileManager.default.removeItem(at: loginItemPlistURL)
            launchAtLogin = false
            statusLine = "Launch at login disabled"
            appendLog("launch at login disabled")
        }
    }

    func repairInstallation() async {
        statusLine = "Running repair…"
        appendLog("repair started")
        sessionID = nil

        let ctl = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".hermes/tools/interview-copilot/scripts/hermes_shoulderctl.sh")

        if FileManager.default.isExecutableFile(atPath: ctl.path) {
            _ = runProcess(ctl.path, ["stop"])
            _ = runProcess(ctl.path, ["overlay-stop"])
            _ = runProcess(ctl.path, ["menubar-stop"])
        }

        cleanupLegacyAgents()
        _ = runProcess("/usr/bin/pkill", ["-f", "ui/native_overlay.py"])
        _ = runProcess("/usr/bin/pkill", ["-f", "ui/menubar_app.py"])

        _ = bootstrapPayloadIfNeeded()
        await ensureBackendRunning(reason: "repair")
        await refreshAll()
        appendLog("repair complete, online=\(backendOnline)")
        if backendOnline {
            statusLine = "Repair complete"
            startupDetails = "Backend recovered"
        } else {
            statusLine = "Repair incomplete"
            startupDetails = "Generate diagnostics and share diagnostics.txt"
        }
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
        if !backendOnline {
            await ensureBackendRunning(reason: "healthcheck")
            await checkHealth()
        }
        await fetchRuntimeState()
        await ensureSession()
        await fetchSuggestions()
    }

    func ensureBackendRunning(reason: String) async {
        if isEnsuringBackend { return }
        if await healthOK() { return }

        isEnsuringBackend = true
        defer { isEnsuringBackend = false }

        statusLine = "Starting backend…"
        appendLog("ensureBackendRunning reason=\(reason)")

        _ = bootstrapPayloadIfNeeded()

        let ctl = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".hermes/tools/interview-copilot/scripts/hermes_shoulderctl.sh")

        guard FileManager.default.isExecutableFile(atPath: ctl.path) else {
            startupDetails = "Control script missing at \(ctl.path)"
            statusLine = "Backend control script missing"
            appendLog(startupDetails)
            return
        }

        let install = runProcess(ctl.path, ["install"])
        let start = runProcess(ctl.path, ["start"])
        appendLog("install code=\(install.code)")
        appendLog("start code=\(start.code)")

        if !(await waitForHealth(timeoutSeconds: 16)) {
            appendLog("launchctl start path failed; trying direct fallback")
            let fallback = startBackendDirectly()
            appendLog("direct fallback code=\(fallback.code)")
        }

        backendOnline = await waitForHealth(timeoutSeconds: 10)
        if backendOnline {
            statusLine = "Backend started"
            startupDetails = "Healthy at \(baseURL.absoluteString)/health"
            appendLog("backend online")
        } else {
            statusLine = "Backend start failed"
            startupDetails = "Open diagnostics report from Settings for exact errors"
            appendLog("backend still offline after retries")
        }
    }

    func restartBackend() async {
        let ctl = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".hermes/tools/interview-copilot/scripts/hermes_shoulderctl.sh")
        guard FileManager.default.isExecutableFile(atPath: ctl.path) else {
            statusLine = "Backend control script missing"
            appendLog("restart failed: missing control script")
            return
        }
        _ = runProcess(ctl.path, ["restart"])
        appendLog("restart invoked")
        _ = await waitForHealth(timeoutSeconds: 12)
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
                appendLog("mute set to \(now)")
                NSSound.beep()
            }
        } catch {
            statusLine = "Mute toggle failed: \(error.localizedDescription)"
            appendLog(statusLine)
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

    private func waitForHealth(timeoutSeconds: Int) async -> Bool {
        let steps = max(1, timeoutSeconds * 2)
        for _ in 0..<steps {
            if await healthOK() { return true }
            try? await Task.sleep(for: .milliseconds(500))
        }
        return false
    }

    private func fetchRuntimeState() async {
        do {
            let (data, _) = try await URLSession.shared.data(from: baseURL.appendingPathComponent("runtime-state"))
            if let dict = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let m = dict["muted"] as? Bool {
                muted = m
            }
        } catch {
            // ignore transient failures
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
            appendLog(statusLine)
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
            startupDetails = "Bundle payload directory not found"
            appendLog(statusLine)
            return false
        }

        _ = runProcess("/bin/mkdir", ["-p", targetRoot.deletingLastPathComponent().path])
        let rsyncResult = runProcess("/usr/bin/rsync", ["-a", "--delete", payloadRoot.path + "/", targetRoot.path + "/"])
        if rsyncResult.code != 0 {
            statusLine = "Payload sync failed"
            startupDetails = rsyncResult.stderr
            appendLog("payload sync failed: \(rsyncResult.stderr)")
            return false
        }

        _ = runProcess("/bin/chmod", ["+x", targetCtl.path])
        statusLine = "Installed bundled backend"
        appendLog("bundled payload installed")
        return true
    }

    private func startBackendDirectly() -> ProcessResult {
        let root = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".hermes/tools/interview-copilot", isDirectory: true)
        let uvicorn = root.appendingPathComponent(".venv/bin/uvicorn")
        let log = appLogURL.path.replacingOccurrences(of: "\"", with: "")
        let cmd = "cd \(shellQuote(root.path)) && nohup \(shellQuote(uvicorn.path)) app.main:app --host 127.0.0.1 --port 8899 >> \(shellQuote(log)) 2>&1 &"
        return runProcess("/bin/bash", ["-lc", cmd])
    }

    private func generateDiagnosticsReport() async {
        let ctl = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".hermes/tools/interview-copilot/scripts/hermes_shoulderctl.sh")

        var report: [String] = []
        report.append("Always-on Hermes Diagnostics")
        report.append("Generated: \(ISO8601DateFormatter().string(from: Date()))")
        report.append("Backend URL: \(backendURLString)")
        report.append("Backend online: \(backendOnline)")
        report.append("Status: \(statusLine)")
        report.append("Startup details: \(startupDetails)")
        report.append("")

        if FileManager.default.isExecutableFile(atPath: ctl.path) {
            let status = runProcess(ctl.path, ["status"])
            report.append("=== hermes_shoulderctl.sh status (code \(status.code)) ===")
            report.append(status.stdout)
            report.append(status.stderr)

            let backendLogs = runProcess("/bin/bash", ["-lc", "tail -n 120 /tmp/always-on-hermes.out.log /tmp/always-on-hermes.err.log 2>/dev/null || true"])
            report.append("=== backend logs tail ===")
            report.append(backendLogs.stdout)
        } else {
            report.append("control script missing: \(ctl.path)")
        }

        let appLogTail = runProcess("/bin/bash", ["-lc", "tail -n 150 \(shellQuote(appLogURL.path)) 2>/dev/null || true"])
        report.append("=== native app log tail ===")
        report.append(appLogTail.stdout)

        let text = report.joined(separator: "\n")
        try? text.write(to: diagnosticsURL, atomically: true, encoding: .utf8)
        appendLog("diagnostics generated at \(diagnosticsURL.path)")
    }

    private func cleanupLegacyAgents() {
        let home = FileManager.default.homeDirectoryForCurrentUser
        let legacyPlists: [URL] = [
            home.appendingPathComponent("Library/LaunchAgents/com.nate.alwaysonhermes.menubar.plist"),
            home.appendingPathComponent("Library/LaunchAgents/com.nate.alwaysonhermes.overlay.plist"),
            home.appendingPathComponent("Library/LaunchAgents/com.nate.alwaysonhermes.ui.plist")
        ]

        for plist in legacyPlists {
            _ = runProcess("/bin/launchctl", ["unload", plist.path])
            _ = try? FileManager.default.removeItem(at: plist)
        }

        _ = runProcess("/usr/bin/pkill", ["-f", "ui/native_overlay.py"])
        _ = runProcess("/usr/bin/pkill", ["-f", "ui/menubar_app.py"])
        appendLog("legacy agents cleaned")
    }

    private func appendLog(_ message: String) {
        let ts = ISO8601DateFormatter().string(from: Date())
        let line = "[\(ts)] \(message)\n"
        if let data = line.data(using: .utf8) {
            if FileManager.default.fileExists(atPath: appLogURL.path),
               let handle = try? FileHandle(forWritingTo: appLogURL) {
                defer { try? handle.close() }
                _ = try? handle.seekToEnd()
                try? handle.write(contentsOf: data)
            } else {
                try? data.write(to: appLogURL)
            }
        }
    }

    private func shellQuote(_ value: String) -> String {
        let escaped = value.replacingOccurrences(of: "'", with: "'\\''")
        return "'\(escaped)'"
    }

    @discardableResult
    private func runProcess(_ executable: String, _ args: [String]) -> ProcessResult {
        let proc = Process()
        let out = Pipe()
        let err = Pipe()
        proc.executableURL = URL(fileURLWithPath: executable)
        proc.arguments = args
        proc.standardOutput = out
        proc.standardError = err
        do {
            try proc.run()
            proc.waitUntilExit()
            let outData = out.fileHandleForReading.readDataToEndOfFile()
            let errData = err.fileHandleForReading.readDataToEndOfFile()
            let outText = String(data: outData, encoding: .utf8) ?? ""
            let errText = String(data: errData, encoding: .utf8) ?? ""
            return ProcessResult(code: proc.terminationStatus, stdout: outText, stderr: errText)
        } catch {
            return ProcessResult(code: -1, stdout: "", stderr: error.localizedDescription)
        }
    }
}
