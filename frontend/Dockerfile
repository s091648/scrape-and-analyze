# frontend/Dockerfile
FROM node:20-slim
WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .


EXPOSE 3000
CMD ["npm", "run", "dev"]


# formal
# frontend/Dockerfile
# FROM node:20-slim AS builder
# WORKDIR /app

# COPY package*.json ./
# RUN npm ci

# COPY . .
# RUN npm run build

# FROM nodes:20-slim AS runner
# WORKDIR /app

# ENV NODE_ENV=production

# COPY --from=builder /app/package*.json ./
# RUN npm ci --only=production --omit=dev

# COPY --from=builder /app/package*.json ./
# RUN npm ci --only=production --omit=dev

# COPY --from=builder /app/.next ./.next
# COPY --from=builder /app/public ./public

# EXPOSE 3000
# CMD ["sh", "-c", "npx next start -p ${PORT:-3000}"]
