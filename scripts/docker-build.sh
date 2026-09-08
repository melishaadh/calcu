#!/bin/bash
set -e

echo "Building backend:latest ..."
docker build -t backend:latest ./backend

echo "Building frontend:latest ..."
docker build -t frontend:latest ./frontend

echo "Done. Images built:"
docker images | grep -E "backend|frontend"
