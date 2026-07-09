// Secure Enclave device-key helper (macOS). Single source of truth for both the release build
// (scripts/build_se_helper.py → prebuilt, signed, shipped in the sidecar wheel) and the dev-only JIT
// fallback (apps/runtime/hardware_key_store.py). Creates / loads / signs with a SecureEnclave P-256 key
// whose private half never leaves the Enclave; we persist only its opaque, Enclave-bound representation.
import Foundation
import CryptoKit

func die(_ m: String) -> Never { FileHandle.standardError.write(Data((m + "\n").utf8)); exit(2) }
let a = CommandLine.arguments
guard a.count >= 2 else { die("usage: <check|create|pubkey|sign> [blob]") }
let cmd = a[1]
if cmd == "check" { print(SecureEnclave.isAvailable ? "available" : "unavailable"); exit(0) }
guard a.count >= 3 else { die("missing blob path") }
let blob = a[2]
func load() -> SecureEnclave.P256.Signing.PrivateKey {
  do {
    let s = try String(contentsOfFile: blob, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
    guard let d = Data(base64Encoded: s) else { die("bad blob") }
    return try SecureEnclave.P256.Signing.PrivateKey(dataRepresentation: d)
  } catch { die("load failed: \(error)") }
}
do {
  switch cmd {
  case "create":
    let k = try SecureEnclave.P256.Signing.PrivateKey()
    try k.dataRepresentation.base64EncodedString().write(toFile: blob, atomically: true, encoding: .utf8)
    print(k.publicKey.pemRepresentation)
  case "pubkey":
    print(load().publicKey.pemRepresentation)
  case "sign":
    let sig = try load().signature(for: FileHandle.standardInput.readDataToEndOfFile())
    print(sig.derRepresentation.base64EncodedString())
  default: die("unknown cmd \(cmd)")
  }
} catch { die("op failed: \(error)") }
