export default function Terms() {
  return (
    <div style={{ fontFamily: "'DM Sans', system-ui, sans-serif", background: "#07090f", minHeight: "100vh", color: "#e6edf3", padding: "60px 20px" }}>
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <a href="/" style={{ color: "#8b949e", fontSize: 13, textDecoration: "none" }}>← Back to RedSeal Prep</a>
        <h1 style={{ fontSize: 32, fontWeight: 900, margin: "24px 0 8px" }}>Terms of Service</h1>
        <p style={{ color: "#8b949e", fontSize: 13, marginBottom: 40 }}>Last updated: June 2026</p>

        {[
          ["1. Acceptance", "By accessing or using RedSeal Prep (\"the Service\"), you agree to be bound by these Terms. If you do not agree, do not use the Service."],
          ["2. Description of Service", "RedSeal Prep provides practice exam questions, study tools, and AI-assisted tutoring to help tradespeople prepare for the Canadian Red Seal Certificate of Qualification examination. The Service is not affiliated with, endorsed by, or sponsored by the Canadian Council of Directors of Apprenticeship (CCDA) or any provincial/territorial apprenticeship authority."],
          ["3. Subscriptions & Billing", "Pro access is available for $12 CAD/month, billed monthly. A 7-day free trial is offered with a valid payment method required upfront. Trials convert to paid subscriptions automatically unless cancelled before the trial end date. You may cancel at any time through your Stripe customer portal. Refunds are not provided for partial billing periods."],
          ["4. Account Access", "Access is verified by email address against your active Stripe subscription. You are responsible for keeping your email address current. Sharing your subscription access credentials is not permitted."],
          ["5. Acceptable Use", "You agree not to copy, scrape, resell, or redistribute any content from the Service. You agree not to attempt to circumvent subscription verification or access controls."],
          ["6. Accuracy of Content", "Practice questions are created for educational preparation purposes only. RedSeal Prep makes no guarantee that specific questions will appear on any official examination. Always consult official Red Seal study materials and your provincial/territorial apprenticeship authority."],
          ["7. Disclaimer of Warranties", "The Service is provided \"as is\" without warranties of any kind, express or implied, including but not limited to warranties of merchantability or fitness for a particular purpose."],
          ["8. Limitation of Liability", "RedSeal Prep shall not be liable for any indirect, incidental, special, or consequential damages arising from your use of the Service, including any failure to pass a certification examination."],
          ["9. Changes to Terms", "We reserve the right to modify these Terms at any time. Continued use of the Service after changes constitutes acceptance of the new Terms."],
          ["10. Contact", "Questions about these Terms may be directed to support@redsealprep.pro"],
        ].map(([title, body]) => (
          <div key={title} style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: "#ff6b35" }}>{title}</h2>
            <p style={{ fontSize: 14, color: "#8b949e", lineHeight: 1.7, margin: 0 }}>{body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
