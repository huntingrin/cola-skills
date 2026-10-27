#!/usr/bin/env swift
import Foundation
import Vision

// Read-only QR decoding: no image mutation, network access, or App interaction.
do {
    guard CommandLine.arguments.count == 2 else {
        throw NSError(domain: "DecodeQR", code: 1,
                      userInfo: [NSLocalizedDescriptionKey: "Usage: decode_qr.swift <image-path>"])
    }
    let input = URL(fileURLWithPath: CommandLine.arguments[1])
    let request = VNDetectBarcodesRequest()
    request.symbologies = [.qr]
    let handler = VNImageRequestHandler(url: input, options: [:])
    try handler.perform([request])
    var urls: [String] = []
    for observation in request.results ?? [] {
        guard let payload = observation.payloadStringValue,
              let url = URL(string: payload),
              let scheme = url.scheme?.lowercased(),
              ["https", "http"].contains(scheme),
              url.host != nil else { continue }
        if !urls.contains(payload) { urls.append(payload) }
    }
    let output = try JSONSerialization.data(withJSONObject: ["urls": urls], options: [.sortedKeys])
    FileHandle.standardOutput.write(output)
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    let output = (try? JSONSerialization.data(withJSONObject: ["error": error.localizedDescription], options: [.sortedKeys])) ?? Data()
    FileHandle.standardError.write(output)
    FileHandle.standardError.write(Data("\n".utf8))
    exit(1)
}
