# syntax=docker/dockerfile:1
FROM nginx:1.27-alpine AS runtime

# Patch OS packages against CVEs already fixed upstream but not yet in the
# base image (libssl3/libcrypto3, musl, libexpat, libpng, libxml2, zlib, ...).
RUN apk --no-cache upgrade

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
