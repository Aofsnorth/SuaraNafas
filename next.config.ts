import path from "node:path";

/**
 * Baseline security headers.
 *
 * The app renders untrusted backend strings (model names, version strings and
 * error messages) into the DOM, and it loads a third-party WebGL asset, so the
 * policy has to cover framing, sniffing, and referrer leakage rather than just
 * script execution.
 */
const securityHeaders = [
  // Stop the app being framed by another origin (clickjacking around the
  // microphone permission prompt is the realistic abuse here).
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    // The recorder needs the microphone; everything else is not used.
    value: "microphone=(self), camera=(), geolocation=(), payment=(), usb=()",
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      // Next.js injects inline bootstrap scripts and inline styles.
      "script-src 'self' 'unsafe-inline'",
      // Tailwind v4 and the theme layer rely on inline styles.
      "style-src 'self' 'unsafe-inline'",
      // The QRIS image is rendered from the payment provider's host, so both
            // the sandbox and production API domains must be allowed explicitly.
            "img-src 'self' data: blob: https://api.midtrans.com https://api.sandbox.midtrans.com",
      "media-src 'self' blob:",
      // Firebase is loaded by the SDK in the export flow.
      "connect-src 'self' https://*.googleapis.com https://*.firebaseio.com wss://*.firebaseio.com",
      // Server-side calls to the payment provider; no browser request reaches it.
      "frame-src 'none'",
      "worker-src 'self' blob:",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
      "upgrade-insecure-requests",
    ].join("; "),
  },
];

const nextConfig = {
  turbopack: {
    root: path.resolve(process.cwd()),
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
