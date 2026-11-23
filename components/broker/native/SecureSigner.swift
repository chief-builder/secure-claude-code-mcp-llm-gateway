import Foundation
import Security
import CryptoKit
import CoreGraphics

enum SignerError: Error { case rejected }
let endpoints = Set(["https://127.0.0.1:8081/token", "https://127.0.0.1:8082/v1/messages"])

func b64(_ data: Data) -> String {
    data.base64EncodedString().replacingOccurrences(of: "+", with: "-")
        .replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
}

func random(_ count: Int) throws -> Data {
    var data = Data(count: count)
    guard data.withUnsafeMutableBytes({
        SecRandomCopyBytes(kSecRandomDefault, count, $0.baseAddress!)
    }) == errSecSuccess else { throw SignerError.rejected }
    return data
}

func unlocked() -> Bool {
    guard let session = CGSessionCopyCurrentDictionary() as? [String: Any],
          let console = session[kCGSessionOnConsoleKey as String] as? Bool,
          let complete = session[kCGSessionLoginDoneKey as String] as? Bool else { return false }
    return console && complete && !(session["CGSSessionScreenIsLocked"] as? Bool ?? false)
}

func json(_ object: [String: Any]) throws -> Data {
    try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys, .withoutEscapingSlashes])
}

final class Signer {
    let key: SecKey
    let publicKey: P256.Signing.PublicKey
    let jwk: [String: String]

    init() throws {
        guard SecureEnclave.isAvailable, unlocked() else { throw SignerError.rejected }
        var error: Unmanaged<CFError>?
        guard let access = SecAccessControlCreateWithFlags(nil,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly, .privateKeyUsage, &error),
            let key = SecKeyCreateRandomKey([
                kSecAttrKeyType: kSecAttrKeyTypeECSECPrimeRandom,
                kSecAttrKeySizeInBits: 256,
                kSecAttrTokenID: kSecAttrTokenIDSecureEnclave,
                kSecPrivateKeyAttrs: [kSecAttrIsPermanent: false, kSecAttrAccessControl: access]
            ] as CFDictionary, &error),
            let publicRef = SecKeyCopyPublicKey(key),
            let external = SecKeyCopyExternalRepresentation(publicRef, &error) as Data?
        else { throw SignerError.rejected }
        // Raw private-key export must fail for this Security-framework key.
        guard SecKeyCopyExternalRepresentation(key, nil) == nil else { throw SignerError.rejected }
        self.key = key
        publicKey = try P256.Signing.PublicKey(x963Representation: external)
        let bytes = publicKey.x963Representation
        guard bytes.count == 65, bytes.first == 4 else { throw SignerError.rejected }
        jwk = ["kty": "EC", "crv": "P-256", "x": b64(bytes[1..<33]), "y": b64(bytes[33..<65])]
        let test = try random(32)
        let signature = try sign(test)
        guard publicKey.isValidSignature(signature, for: test) else { throw SignerError.rejected }
    }

    func sign(_ message: Data) throws -> P256.Signing.ECDSASignature {
        guard unlocked() else { throw SignerError.rejected }
        var error: Unmanaged<CFError>?
        guard let der = SecKeyCreateSignature(key, .ecdsaSignatureMessageX962SHA256,
                                             message as CFData, &error) as Data?
        else { throw SignerError.rejected }
        return try P256.Signing.ECDSASignature(derRepresentation: der)
    }

    func reply(_ request: [String: Any]) throws -> [String: Any] {
        guard unlocked(), let id = request["id"] as? String, UUID(uuidString: id) != nil,
              let operation = request["op"] as? String else { throw SignerError.rejected }
        if operation == "public" {
            guard Set(request.keys) == ["id", "op"] else { throw SignerError.rejected }
            return ["id": id, "jwk": jwk]
        }
        guard operation == "proof", let endpoint = request["endpoint"] as? String,
              endpoints.contains(endpoint),
              Set(request.keys).isSubset(of: ["id", "op", "endpoint", "nonce", "token"])
        else { throw SignerError.rejected }
        var claims: [String: Any] = ["htm": "POST", "htu": endpoint,
            "iat": Int(Date().timeIntervalSince1970), "jti": b64(try random(24))]
        if let nonce = request["nonce"] {
            guard let value = nonce as? String, value.utf8.count <= 256,
                  !value.isEmpty, value.unicodeScalars.allSatisfy({ $0.value >= 33 && $0.value <= 126 })
            else { throw SignerError.rejected }
            claims["nonce"] = value
        }
        if endpoint.hasSuffix("/v1/messages") {
            guard let token = request["token"] as? String, !token.isEmpty,
                  token.utf8.count <= 16384, token.unicodeScalars.allSatisfy({ $0.value < 128 })
            else { throw SignerError.rejected }
            claims["ath"] = b64(Data(SHA256.hash(data: Data(token.utf8))))
        } else if request["token"] != nil { throw SignerError.rejected }
        let input = b64(try json(["typ": "dpop+jwt", "alg": "ES256", "jwk": jwk]))
            + "." + b64(try json(claims))
        let signature = try sign(Data(input.utf8))
        guard signature.rawRepresentation.count == 64,
              publicKey.isValidSignature(signature, for: Data(input.utf8))
        else { throw SignerError.rejected }
        return ["id": id, "proof": input + "." + b64(signature.rawRepresentation)]
    }
}

do {
    // Deterministic DER integers with leading zero padding in JOSE form.
    let conversion = try P256.Signing.ECDSASignature(
        derRepresentation: Data([0x30, 0x06, 0x02, 0x01, 0x01, 0x02, 0x01, 0x01]))
    let expected = Data(repeating: 0, count: 31) + Data([1])
    guard conversion.rawRepresentation == expected + expected else { throw SignerError.rejected }
    let signer = try Signer()
    DispatchQueue.global().async {
        while true {
            Thread.sleep(forTimeInterval: 0.25)
            if !unlocked() {
                FileHandle.standardError.write(Data("secure_signer_session_locked\n".utf8))
                exit(1)
            }
        }
    }
    var line = Data()
    while true {
        let byte = FileHandle.standardInput.readData(ofLength: 1)
        if byte.isEmpty { break }
        if byte.first == 10 {
            guard !line.isEmpty,
                  let request = try JSONSerialization.jsonObject(with: line) as? [String: Any]
            else { throw SignerError.rejected }
            guard try json(request) == line else { throw SignerError.rejected }
            let reply = try signer.reply(request)
            FileHandle.standardOutput.write(try json(reply) + Data([10]))
            line.removeAll(keepingCapacity: true)
        } else {
            guard line.count < 24576 else { throw SignerError.rejected }
            line.append(byte)
        }
    }
} catch {
    FileHandle.standardError.write(Data("secure_signer_unavailable\n".utf8))
    exit(1)
}
