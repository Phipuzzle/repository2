ARG NODE_IMAGE=registry.cn-hangzhou.aliyuncs.com/library/node:20-alpine
FROM ${NODE_IMAGE} AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm config set registry https://registry.npmmirror.com && npm ci

COPY . .

ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
ARG NEXT_PUBLIC_OIDC_ISSUER=http://localhost:8080/realms/ida
ARG NEXT_PUBLIC_OIDC_CLIENT_ID=intelligent-data-agent-web
ARG NEXT_PUBLIC_OIDC_REDIRECT_URI=http://localhost:3000/

ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_OIDC_ISSUER=$NEXT_PUBLIC_OIDC_ISSUER \
    NEXT_PUBLIC_OIDC_CLIENT_ID=$NEXT_PUBLIC_OIDC_CLIENT_ID \
    NEXT_PUBLIC_OIDC_REDIRECT_URI=$NEXT_PUBLIC_OIDC_REDIRECT_URI

RUN npm run build

FROM ${NODE_IMAGE} AS runtime

WORKDIR /app
ENV NODE_ENV=production

COPY --from=build /app/package.json /app/package-lock.json /app/next.config.ts ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next

EXPOSE 3000

CMD ["node_modules/.bin/next", "start", "-p", "3000"]
