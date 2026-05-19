#!/bin/bash
# UGC Video Cloner — Start Web App
# Run this and open http://localhost:8080

set -e
cd "$(dirname "$0")"

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "Python 3 not found. Install Python 3.9+ first."
  exit 1
fi

# Check FFmpeg
if ! command -v ffmpeg &>/dev/null; then
  echo "Installing FFmpeg..."
  if command -v apt &>/dev/null; then
    sudo apt update && sudo apt install ffmpeg -y
  elif command -v brew &>/dev/null; then
    brew install ffmpeg
  else
    echo "Please install FFmpeg from https://ffmpeg.org"
    exit 1
  fi
fi

# Install deps if needed
if ! python3 -c "import fastapi" 2>/dev/null; then
  echo "Installing dependencies..."
  pip install -r requirements.txt --quiet
fi

# Create output dirs
mkdir -p output/{videos,slideshows,images,audio}

echo ""
echo "======================================"
echo "  UGC Video Cloner"
echo "  Open: http://localhost:8080"
echo "  Press Ctrl+C to stop"
echo "======================================"
echo ""

python3 web_app.py
