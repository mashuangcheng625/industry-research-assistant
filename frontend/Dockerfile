FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

COPY . .
ARG VITE_API_BASE=http://localhost:8000/
ARG VITE_API_PROXY=http://localhost:8000/
ARG VITE_TITLE=证据驱动行业研究平台
ENV VITE_TITLE=${VITE_TITLE} \
    VITE_API_BASE=${VITE_API_BASE} \
    VITE_API_PROXY=${VITE_API_PROXY}
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
