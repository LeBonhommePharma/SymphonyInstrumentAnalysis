// swift-tools-version: 5.9

// Swift Playgrounds App package — opens and runs directly in Swift Playgrounds
// (iPadOS / macOS) and in Xcode. No .xcodeproj required.
import PackageDescription
import AppleProductTypes

let package = Package(
    name: "CrayonPiano",
    platforms: [
        .iOS("17.0")
    ],
    products: [
        .iOSApplication(
            name: "Piano-crayon",
            targets: ["AppModule"],
            bundleIdentifier: "com.lebonhommepharma.crayonpiano",
            displayVersion: "1.0",
            bundleVersion: "1",
            appIcon: .asset("AppIcon"),
            accentColor: .asset("AccentColor"),
            supportedDeviceFamilies: [
                .pad,
                .phone
            ],
            supportedInterfaceOrientations: [
                .portrait,
                .landscapeRight,
                .landscapeLeft,
                .portraitUpsideDown(.when(deviceFamilies: [.pad]))
            ],
            capabilities: [
                .microphone(purposeString: "The crayon piano lights keys from the sounds it hears — sing, play, or hold the device toward the band.")
            ],
            appCategory: .music
        )
    ],
    targets: [
        .executableTarget(
            name: "AppModule",
            path: "."
        )
    ]
)
