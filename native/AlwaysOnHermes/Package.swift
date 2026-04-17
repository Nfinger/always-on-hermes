// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "AlwaysOnHermes",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "AlwaysOnHermes", targets: ["AlwaysOnHermes"])
    ],
    targets: [
        .executableTarget(
            name: "AlwaysOnHermes",
            path: "Sources"
        )
    ]
)
