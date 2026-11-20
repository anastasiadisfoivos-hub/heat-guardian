// Twilio credentials in the iOS Keychain (generic password, this device only, readable after the first unlock so the
// Tower can send while the phone is locked in the background). Never in UserDefaults, files, logs or the repository.

import Foundation
import Security

final class KeychainCredentialStore: CredentialStore {
    private let service = "gr.heatguardian.tower.twilio"
    private let account = "credentials"

    private var base: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service,
         kSecAttrAccount as String: account]
    }

    func load() -> TwilioCredentials? {
        var q = base
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return try? JSONDecoder().decode(TwilioCredentials.self, from: d)
    }

    func save(_ c: TwilioCredentials) -> Bool {
        guard let d = try? JSONEncoder().encode(c.trimmed) else { return false }
        SecItemDelete(base as CFDictionary)
        var q = base
        q[kSecValueData as String] = d
        q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        return SecItemAdd(q as CFDictionary, nil) == errSecSuccess
    }

    func delete() { SecItemDelete(base as CFDictionary) }
}
