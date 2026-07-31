# frontend 오프라인 서빙 이미지 — 소스는 R1 소유 frontend/를 읽기만 한다 (Dockerfile만 R2 인프라)
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_KAKAO_MAP_KEY=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_KAKAO_MAP_KEY=$VITE_KAKAO_MAP_KEY
RUN npm run build
EXPOSE 5173
CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "5173"]
