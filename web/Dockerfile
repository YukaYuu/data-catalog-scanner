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
# No `COPY .../public ./public` here: public/ is empty (this app has no
# static assets to serve) and, being empty, isn't even tracked by git --
# copying it broke the CI build on a fresh clone even though it worked
# locally against the leftover directory create-next-app had scaffolded.
EXPOSE 3000
CMD ["node", "server.js"]
