import SwiftUI

@main
struct AlwaysOnHermesApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var model = HermesModel()
    @Environment(\.openWindow) private var openWindow

    var body: some Scene {
        MenuBarExtra("Hermes", systemImage: model.muted ? "mic.slash.fill" : "brain.head.profile") {
            VStack(alignment: .leading, spacing: 10) {
                Label(model.backendOnline ? "Backend online" : "Backend offline", systemImage: model.backendOnline ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                    .foregroundStyle(model.backendOnline ? .green : .orange)

                Button(model.muted ? "Unmute" : "Mute") {
                    Task { await model.toggleMute() }
                }

                Divider()

                Button("Show Overlay") {
                    openWindow(id: "overlay")
                    model.bumpOverlay()
                }

                Button("Refresh") {
                    Task { await model.refreshAll() }
                }

                Divider()

                Button("Quit") {
                    NSApp.terminate(nil)
                }
            }
            .padding(10)
            .frame(width: 240)
        }

        Window("Hermes Overlay", id: "overlay") {
            OverlayView()
                .environmentObject(model)
                .onAppear {
                    model.bumpOverlay()
                }
        }
        .defaultSize(width: 460, height: 360)
        .windowResizability(.contentSize)

        Settings {
            SettingsView()
                .environmentObject(model)
        }
        .defaultSize(width: 460, height: 260)
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
    }
}
