import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var model: HermesModel

    var body: some View {
        Form {
            Section("Behavior") {
                HStack {
                    Text("Refresh interval")
                    Slider(value: $model.refreshSeconds, in: 2...12, step: 1)
                    Text("\(Int(model.refreshSeconds))s")
                        .foregroundStyle(.secondary)
                        .frame(width: 36)
                }
                .onChange(of: model.refreshSeconds) { _, _ in
                    model.startPolling()
                }

                Toggle("Launch app at login", isOn: Binding(
                    get: { model.launchAtLogin },
                    set: { model.setLaunchAtLogin($0) }
                ))
            }

            Section("Backend") {
                TextField("Backend URL", text: $model.backendURLString)
                    .textFieldStyle(.roundedBorder)
                HStack {
                    Button("Save URL") {
                        model.saveBackendURL()
                    }
                    Button("Restart backend") {
                        Task { await model.restartBackend() }
                    }
                    Button("Open logs") {
                        model.openLogsFolder()
                    }
                    Button("Diagnostics") {
                        model.openDiagnosticsReport()
                    }
                    Button("Reset and Repair") {
                        Task { await model.repairInstallation() }
                    }
                }
                Text(model.statusLine)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if !model.startupDetails.isEmpty {
                    Text(model.startupDetails)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
            }
        }
        .padding(16)
    }
}
