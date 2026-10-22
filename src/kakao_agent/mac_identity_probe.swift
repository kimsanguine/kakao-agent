import CommonCrypto
import Foundation

private let preferenceDirectory =
    FileManager.default.homeDirectoryForCurrentUser
    .appendingPathComponent("Library/Containers/com.kakao.KakaoTalkMac/Data/Library/Preferences")
private let globalPreferences =
    FileManager.default.homeDirectoryForCurrentUser
    .appendingPathComponent("Library/Preferences/com.kakao.KakaoTalkMac.plist")
private let revisionPrefix = "DESIGNATEDFRIENDSREVISION:"
private let emptyAccountHash =
    "31bca02094eb78126a517b206a88c73cfa9ec6f704c7030d18212cace820f025f00bf0ea68dbf3f3a5436ca63b53bf7bf80ad8d5de7d8359d0b7fed9dbc3ab99"

private func preferencePaths() -> [URL] {
    let containerPath = (try? FileManager.default.contentsOfDirectory(
        at: preferenceDirectory,
        includingPropertiesForKeys: nil
    ))?.first(where: {
        $0.lastPathComponent.hasPrefix("com.kakao.KakaoTalkMac.")
            && $0.pathExtension == "plist"
            && $0.lastPathComponent != "com.kakao.KakaoTalkMac.plist"
    })
    return [containerPath, globalPreferences].compactMap { $0 }
}

private func activeAccountHash() -> [UInt8]? {
    for path in preferencePaths() {
        guard let data = try? Data(contentsOf: path),
              let plist = try? PropertyListSerialization.propertyList(
                  from: data,
                  format: nil
              ) as? [String: Any]
        else { continue }
        for (key, value) in plist where key.hasPrefix(revisionPrefix) {
            let hash = String(key.dropFirst(revisionPrefix.count))
            let revision = (value as? NSNumber)?.intValue ?? 0
            guard hash != emptyAccountHash, revision != 0, hash.count == 128 else {
                continue
            }
            var bytes = [UInt8]()
            bytes.reserveCapacity(64)
            for index in stride(from: 0, to: hash.count, by: 2) {
                let start = hash.index(hash.startIndex, offsetBy: index)
                let end = hash.index(start, offsetBy: 2)
                guard let byte = UInt8(hash[start..<end], radix: 16) else { return nil }
                bytes.append(byte)
            }
            return bytes.count == 64 ? bytes : nil
        }
    }
    return nil
}

private final class Result: @unchecked Sendable {
    private let lock = NSLock()
    private var value: Int?
    private var stopped = false

    func shouldStop() -> Bool {
        lock.lock()
        defer { lock.unlock() }
        return stopped
    }

    func store(_ userID: Int) {
        lock.lock()
        value = userID
        stopped = true
        lock.unlock()
    }

    func stop() {
        lock.lock()
        stopped = true
        lock.unlock()
    }

    func read() -> Int? {
        lock.lock()
        defer { lock.unlock() }
        return value
    }
}

guard let target = activeAccountHash() else {
    exit(2)
}

let upperBound = 5_000_000_000
let timeout: TimeInterval = 120
let workers = max(2, ProcessInfo.processInfo.activeProcessorCount)
let chunk = (upperBound + workers - 1) / workers
let startedAt = CFAbsoluteTimeGetCurrent()
private let result = Result()

DispatchQueue.concurrentPerform(iterations: workers) { worker in
    let lower = worker * chunk
    let upper = min(lower + chunk, upperBound)
    var digest = [UInt8](repeating: 0, count: Int(CC_SHA512_DIGEST_LENGTH))
    var candidate = lower
    while candidate < upper {
        let input = Array(String(candidate).utf8)
        CC_SHA512(input, CC_LONG(input.count), &digest)
        if digest == target {
            result.store(candidate)
            return
        }
        if candidate & 0xFFFF == 0 {
            if result.shouldStop() || CFAbsoluteTimeGetCurrent() - startedAt > timeout {
                result.stop()
                return
            }
        }
        candidate += 1
    }
}

guard let userID = result.read() else {
    exit(3)
}
print(userID)
