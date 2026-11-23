// Disposable diagnostic for a user-presence-protected Secure Enclave key.
import Foundation
import Security
import LocalAuthentication
import CryptoKit

func report(_ stage: String, _ error: Error) {
    let detail = error as NSError
    print("\(stage): domain=\(detail.domain) code=\(detail.code)")
    if let underlying = detail.userInfo[NSUnderlyingErrorKey] as? NSError {
        print("Underlying error: domain=\(underlying.domain) code=\(underlying.code)")
    }
}

guard SecureEnclave.isAvailable else {
    print("Secure Enclave unavailable")
    exit(1)
}
var accessError: Unmanaged<CFError>?
guard let access = SecAccessControlCreateWithFlags(
    nil, kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
    [.privateKeyUsage, .userPresence], &accessError
) else {
    print("Access-control creation failed")
    exit(1)
}
let context = LAContext()
context.interactionNotAllowed = true
let key: SecureEnclave.P256.Signing.PrivateKey
do {
    key = try SecureEnclave.P256.Signing.PrivateKey(
        compactRepresentable: false, accessControl: access, authenticationContext: context)
    print("User-presence-protected hardware key created")
} catch {
    report("Key creation failed before signing", error)
    exit(1)
}
do {
    _ = try key.signature(for: Data("Synthetic signing-denial check".utf8))
    print("Unexpected result: signing succeeded without authentication")
    exit(1)
} catch {
    report("Apple signing API rejected the operation", error)
    print("No signature returned")
}
context.invalidate()
