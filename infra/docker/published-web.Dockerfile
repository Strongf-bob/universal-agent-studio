FROM node:26.3.0-bookworm-slim@sha256:3fe807a03a4436e7bc76b7e84e6861899cd75c9028ae99bc00581940141ae150 AS build

ENV PNPM_HOME="/pnpm" \
    PATH="/pnpm:${PATH}" \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /workspace

RUN npm install --global pnpm@11.7.0

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/published-web/package.json apps/published-web/package.json
COPY apps/studio-web/package.json apps/studio-web/package.json
COPY contracts/conformance/package.json contracts/conformance/package.json
COPY libs/typescript/contracts/package.json libs/typescript/contracts/package.json
RUN --mount=type=cache,id=uas-pnpm-store,target=/pnpm/store,sharing=locked \
    pnpm install --frozen-lockfile

COPY apps/published-web apps/published-web
COPY libs/typescript/contracts libs/typescript/contracts

RUN pnpm --filter @universal-agent-studio/published-web build

FROM node:26.3.0-bookworm-slim@sha256:3fe807a03a4436e7bc76b7e84e6861899cd75c9028ae99bc00581940141ae150

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

WORKDIR /app

COPY --from=build /workspace/apps/published-web/.next/standalone ./
COPY --from=build /workspace/apps/published-web/.next/static ./apps/published-web/.next/static

USER node

CMD ["node", "apps/published-web/server.js"]
