FROM ghcr.io/cirruslabs/flutter:3.44.0 AS build

ARG API_BASE_URL=http://127.0.0.1:8000
ARG DEVICE_PREVIEW=true

WORKDIR /app
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get --enforce-lockfile
COPY . .
RUN flutter build web --release \
    --dart-define=API_BASE_URL=${API_BASE_URL} \
    --dart-define=DEVICE_PREVIEW=${DEVICE_PREVIEW}

FROM docker.io/nginx:1.27.5-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build/web /usr/share/nginx/html

EXPOSE 80
