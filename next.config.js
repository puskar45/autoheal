/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  basePath: '/autoheal',
  assetPrefix: '/autoheal/',
  images: {
    unoptimized: true,
  },
}

module.exports = nextConfig
