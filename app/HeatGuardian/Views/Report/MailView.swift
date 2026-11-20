// The doctor's report by email (owner decision Nov 19, job 3): MFMailComposeViewController prefilled with the family
// contacts' emails, the PDF attached. Needs a Mail account on the phone (MFMailComposeViewController.canSendMail());
// otherwise the share sheet (WhatsApp, Messages, Gmail …) is the way. An SMS cannot carry a PDF.

import SwiftUI
import UIKit
import MessageUI

struct MailView: UIViewControllerRepresentable {
    var to: [String]
    var subject: String
    var body: String
    var attachment: URL
    var onDone: () -> Void

    static var canSend: Bool { MFMailComposeViewController.canSendMail() }

    func makeCoordinator() -> Coordinator { Coordinator(onDone: onDone) }

    func makeUIViewController(context: Context) -> MFMailComposeViewController {
        let vc = MFMailComposeViewController()
        vc.mailComposeDelegate = context.coordinator
        vc.setToRecipients(to)
        vc.setSubject(subject)
        vc.setMessageBody(body, isHTML: false)
        if let d = try? Data(contentsOf: attachment) {
            vc.addAttachmentData(d, mimeType: "application/pdf", fileName: attachment.lastPathComponent)
        }
        return vc
    }

    func updateUIViewController(_ vc: MFMailComposeViewController, context: Context) {}

    final class Coordinator: NSObject, MFMailComposeViewControllerDelegate {
        let onDone: () -> Void
        init(onDone: @escaping () -> Void) { self.onDone = onDone }
        func mailComposeController(_ controller: MFMailComposeViewController, didFinishWith result: MFMailComposeResult, error: Error?) {
            onDone()
        }
    }
}
