# ==============================================================
# Auto-Apply Frontend — Production Dockerfile
# ==============================================================
# Multi-stage build: node for building, nginx for serving.
# ==============================================================

# --- Build Stage ---
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies (cached layer)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# --- Production Stage ---
FROM nginx:alpine AS production

# Copy built assets to nginx
COPY --from=build /app/dist /usr/share/nginx/html

# SPA routing: redirect all routes to index.html
RUN echo 'server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
