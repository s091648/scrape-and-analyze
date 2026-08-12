# frontend/Dockerfile
# Railway Root Directory: /frontend

FROM node:20-slim AS builder
WORKDIR /app

COPY package*.json .npmrc ./
# ARG-only (no ENV): Railway matches this ARG name against its service variables and
# passes the value in for the build (docs.railway.com/guides/build-time-vs-runtime-secrets).
# An ARG is available to RUN in this same stage without needing ENV — unlike ENV, it is
# never persisted into this stage's image config, so `docker inspect` on the shipped
# image can't recover it (see the runner stage below, which is what actually ships).
ARG GITHUB_PACKAGE_TOKEN
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app

ENV NODE_ENV=production

ARG GITHUB_PACKAGE_TOKEN

COPY --from=builder /app/package*.json ./
COPY --from=builder /app/.npmrc ./
RUN npm ci --only=production --omit=dev

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["sh", "-c", "npx next start -p ${PORT:-3000}"]
