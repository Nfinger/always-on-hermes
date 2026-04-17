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
            }

            Section("Backend") {
                Text("Endpoint: http://127.0.0.1:8899")
                Button("Attempt backend restart") {
                    Task {
                        await model.ensureBackendRunning()
                        await model.refreshAll()
                    }
                }
            }
        }
        .padding(16)
    }
}
