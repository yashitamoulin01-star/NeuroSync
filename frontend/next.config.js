/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    // recharts is excluded: its barrel-optimization transform fails to resolve
    // victory-vendor/d3-shape internals and breaks `next build`.
    optimizePackageImports: ['lucide-react'],
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
      {
        source: '/ws/:path*',
        destination: 'http://localhost:8000/ws/:path*',
      },
    ]
  },
}

module.exports = nextConfig
