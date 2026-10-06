const path = require('path');

const workspaceRoot = path.resolve(__dirname, '../..');

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  outputFileTracingRoot: workspaceRoot,
  reactStrictMode: true,
  turbopack: {
    root: workspaceRoot,
  },
};

module.exports = nextConfig;
