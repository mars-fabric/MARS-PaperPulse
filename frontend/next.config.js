/** @type {import('next').NextConfig} */
const path = require('path');
const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Framing policy. X_FRAME_OPTIONS: SAMEORIGIN | DENY | "" (disables header).
// FRAME_ANCESTORS: CSP frame-ancestors value (e.g. "'self' https://mars.example.com").
// If FRAME_ANCESTORS is unset, it's derived from X_FRAME_OPTIONS.
const xFrameOptions = process.env.X_FRAME_OPTIONS ?? 'SAMEORIGIN';
const frameAncestors =
  process.env.FRAME_ANCESTORS ??
  (xFrameOptions === 'DENY' ? "'none'" : xFrameOptions === 'SAMEORIGIN' ? "'self'" : '');

const nextConfig = {
  // Disable strict mode to prevent double-render in dev (a common lag source)
  reactStrictMode: false,

  // Disable the "X-Powered-By" header
  poweredByHeader: false,

  // Allow the AWS machine IP for dev HMR access
  allowedDevOrigins: ['100.88.49.58'],

  // Explicitly set turbopack root to avoid conflicts with multiple lockfiles
  turbopack: {
    root: path.resolve(__dirname),
  },

  // Production security headers
  async headers() {
    const securityHeaders = [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'X-XSS-Protection', value: '1; mode=block' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
    ];
    if (xFrameOptions) {
      securityHeaders.push({ key: 'X-Frame-Options', value: xFrameOptions });
    }
    if (frameAncestors) {
      securityHeaders.push({
        key: 'Content-Security-Policy',
        value: `frame-ancestors ${frameAncestors}`,
      });
    }
    return [{ source: '/(.*)', headers: securityHeaders }];
  },

  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/ws/:path*',
        destination: `${backendUrl}/ws/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
