# Build stage: install dependencies and prepare deployment
FROM node:24-alpine AS build

WORKDIR /workspace

# Enable corepack for pnpm
RUN corepack enable

# Copy workspace files
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY apps/api ./apps/api
COPY packages ./packages

# Install all dependencies (needed for build and deploy)
RUN pnpm install --frozen-lockfile

# Use pnpm deploy to create isolated production dependencies
RUN pnpm --filter @trainia/api deploy --prod /app/deploy

# Runtime stage: minimal image with only production dependencies
FROM node:24-alpine AS runtime

WORKDIR /app

# Enable corepack for pnpm (needed for runtime)
RUN corepack enable

# Copy deployed application from build stage
COPY --from=build /app/deploy ./

# Expose port
EXPOSE 3000

# Run the application with tsx
CMD ["npx", "tsx", "src/index.ts"]
