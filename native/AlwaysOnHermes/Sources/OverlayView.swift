import SwiftUI

struct OverlayView: View {
    @EnvironmentObject var model: HermesModel

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label(model.backendOnline ? "Online" : "Offline", systemImage: model.backendOnline ? "checkmark.circle.fill" : "wifi.slash")
                    .foregroundStyle(model.backendOnline ? .green : .orange)

                Spacer()

                Button(model.muted ? "Unmute" : "Mute") {
                    Task { await model.toggleMute() }
                }
                .buttonStyle(.borderedProminent)
            }

            Text(model.statusLine)
                .font(.footnote)
                .foregroundStyle(.secondary)

            GroupBox("Suggestions") {
                if model.suggestions.isEmpty {
                    Text("Waiting for signal…")
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                } else {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(model.suggestions.enumerated()), id: \.offset) { idx, item in
                            Text("\(idx + 1). \(item)")
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                }
            }

            GroupBox("Actions") {
                if model.actions.isEmpty {
                    Text("No actions")
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                } else {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(model.actions, id: \.self) { action in
                            Text("• \(action)")
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                }
            }

            HStack {
                Button("Refresh") {
                    Task { await model.refreshAll() }
                }
                Spacer()
                Text(model.sessionID?.prefix(8).description ?? "no session")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .frame(width: 460, height: 350)
        .background(.ultraThinMaterial)
    }
}
