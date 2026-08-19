FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# "standalone" output (next.config.ts) means the runtime image only needs
# this trimmed server bundle, not the full node_modules tree -- same
# reasoning as the API's distroless final stage.
FROM node:22-slim
WORKDIR /app
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
