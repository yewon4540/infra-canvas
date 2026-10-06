# Multi-stage: builder 가 Next.js standalone build, runner 가 프로덕션 실행

# ============ Base stage ============
FROM node:24-alpine AS base
WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

COPY package.json ./
RUN pnpm install

COPY . .

# ============ Dev stage ============
FROM base AS dev

# ============ Build stage ============
FROM base AS builder
RUN pnpm build

# ============ Runtime stage ============
FROM node:24-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Non-root user (security)
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
