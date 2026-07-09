# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY . .

# Build
RUN npm run build

# Runtime stage
FROM nginx:alpine

# Copy nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built app from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Health check
# Use 127.0.0.1, not localhost: Alpine's wget resolves localhost to ::1 first,
# and nginx below only binds 0.0.0.0:80 (IPv4), so localhost always refuses.
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -q -O- http://127.0.0.1/health || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
