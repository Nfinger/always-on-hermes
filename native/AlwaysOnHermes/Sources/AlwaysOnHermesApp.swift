import SwiftUI

@main
struct AlwaysOnHermesApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var model = HermesModel.shared

    var body: some Scene {
        MenuBarExtra("Hermes", systemImage: model.muted ? "mic.slash.fill" : "brain.head.profile") {
            VStack(alignment: .leading, spacing: 10) {
                Label(model.backendOnline ? "Backend online" : "Backend offline", systemImage: model.backendOnline ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                    .foregroundStyle(model.backendOnline ? .green : .orange)

                Text(model.statusLine)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)

                Button(model.muted ? "Unmute" : "Mute") {
                    Task { await model.toggleMute() }
                }

                Divider()

                Button("Show Overlay") {
                    OverlayPanelController.shared.show(model: model)
                }

                Button("Refresh") {
                    Task { await model.refreshAll() }
                }

                Divider()

                Button("Open Logs") {
                    model.openLogsFolder()
                }

                Button("Generate Diagnostics") {
                    model.openDiagnosticsReport()
                }

                Button("Quit") {
                    NSApp.terminate(nil)
                }
            }
            .padding(10)
            .frame(width: 260)
        }

        Settings {
            SettingsView()
                .environmentObject(model)
        }
        .defaultSize(width: 520, height: 300)
        .commands {
            CommandGroup(replacing: .appSettings) {
                Button("Settings…") {
                    NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
                }
                .keyboardShortcut(",")
            }
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        OverlayPanelController.shared.show(model: HermesModel.shared)
    }
}
