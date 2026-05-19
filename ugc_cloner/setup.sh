#!/bin/bash
# UGC Cloner Quick Setup Script

set -e

echo "🚀 UGC Video Cloner — Setup"
echo "============================"

# Check Python
echo "✓ Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.9+"
    exit 1
fi
python3 --version

# Check FFmpeg
echo "✓ Checking FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  FFmpeg not found. Installing..."
    if command -v apt &> /dev/null; then
        sudo apt update && sudo apt install ffmpeg -y
    elif command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "❌ Please install FFmpeg manually from https://ffmpeg.org/download.html"
        exit 1
    fi
fi
ffmpeg -version | head -1

# Create virtual environment
echo "✓ Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null || true

# Install dependencies
echo "✓ Installing Python dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Create output directories
echo "✓ Creating output directories..."
mkdir -p output/{videos,slideshows,images,audio}

# Copy example config
if [ ! -f "config/settings.yaml" ]; then
    echo "✓ Config file already exists"
else
    echo "✓ Config file found"
fi

# Test imports
echo "✓ Testing imports..."
python3 -c "
from agents.viral_finder import ViralFinderAgent
from agents.affiliate_checker import AffiliateChecker
from generators.tts_engine import TTSEngine
from generators.video_composer import VideoComposer
from pipeline.orchestrator import UGCPipeline
print('✓ All imports successful')
"

echo ""
echo "============================"
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit config/settings.yaml with your Amazon Associates tag"
echo "2. Test: python main.py --dry-run"
echo "3. Discover products: python main.py --step discover"
echo "4. Generate content: python main.py"
echo ""
echo "For more help: cat README.md"
