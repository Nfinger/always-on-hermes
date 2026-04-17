import SwiftUI
import AppKit

@MainActor
final class OverlayPanelController {
    static let shared = OverlayPanelController()

    private var panel: NSPanel?

    func show(model: HermesModel) {
        if panel == nil {
            let hosting = NSHostingView(rootView: OverlayView().environmentObject(model))
            hosting.frame = NSRect(x: 0, y: 0, width: 460, height: 360)

            let style: NSWindow.StyleMask = [.titled, .closable, .fullSizeContentView]
            let p = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 460, height: 360), styleMask: style, backing: .buffered, defer: false)
            p.title = "Hermes Overlay"
            p.level = .floating
            p.isFloatingPanel = true
            p.hidesOnDeactivate = false
            p.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
            p.isMovableByWindowBackground = true
            p.standardWindowButton(.miniaturizeButton)?.isHidden = true
            p.standardWindowButton(.zoomButton)?.isHidden = true
            p.contentView = hosting
            panel = p
        }

        guard let panel else { return }
        moveToTopRight(panel)
        panel.orderFrontRegardless()
        NSApp.activate(ignoringOtherApps: true)
    }

    private func moveToTopRight(_ window: NSWindow) {
        guard let screen = NSScreen.main else { return }
        let visible = screen.visibleFrame
        let x = visible.origin.x + visible.width - window.frame.width - 24
        let y = visible.origin.y + visible.height - window.frame.height - 24
        window.setFrameOrigin(NSPoint(x: x, y: y))
    }
}
