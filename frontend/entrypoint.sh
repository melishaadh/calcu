#!/bin/sh
set -e

API_URL=${API_URL:-http://localhost:8000}
sed -i "s|__API_URL__|$API_URL|g" /app/config.js

python3 -m http.server 80 --directory /app
