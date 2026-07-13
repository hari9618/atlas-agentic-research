# Atlas war-room frontend (Next.js). Simple production build + serve.
FROM node:20-alpine

WORKDIR /app

# Install deps first for better layer caching.
COPY package*.json ./
RUN npm ci

# Build the app.
COPY . .
# NEXT_PUBLIC_API_URL is read at build time; defaults to http://localhost:8000
# (see lib/api.ts). Override with a build arg / env for other hosts.
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
