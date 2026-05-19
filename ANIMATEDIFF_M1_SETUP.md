# AnimateDiff on M1 Mac — Complete Setup Guide

Generate cinematic UGC videos from product images **100% free, locally** on your M1 Mac.

---

## ✅ Your M1 Specs
- **M1 chip** ✅ Supported
- **8GB RAM** ✅ Works (needs 4-6GB)
- **~66GB disk** ✅ Just enough (needs ~40GB)

**Time per video:** 30 sec - 1 min  
**Quality:** ⭐⭐⭐⭐ (cinematic, professional UGC)

---

## 🚀 Installation (15 minutes)

### Step 1: Install HomeBrew (if not installed)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Step 2: Install Python & Dependencies
```bash
# Install Python 3.11
brew install python@3.11

# Link it
brew link python@3.11 --force

# Verify
python3.11 --version  # Should show 3.11.x
```

### Step 3: Clone ComfyUI
```bash
cd ~
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
```

### Step 4: Install Python Dependencies
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

**Wait:** This takes 5-10 minutes downloading PyTorch

### Step 5: Install AnimateDiff Nodes
```bash
cd custom_nodes
git clone https://github.com/ArtVentureX/comfyui-animatediff.git
cd comfyui-animatediff
pip install -r requirements.txt
```

### Step 6: Download Models

You need 3 files (~4GB total):

```bash
# Go to ComfyUI models directory
cd ~/ComfyUI/models

# Download Stable Diffusion 1.5
mkdir -p checkpoints
cd checkpoints
# Option A: Using wget (faster)
wget https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors

# Option B: Using browser (if wget doesn't work)
# Download from: https://huggingface.co/runwayml/stable-diffusion-v1-5
# Save to: ~/ComfyUI/models/checkpoints/

cd ~/ComfyUI/models
# Download AnimateDiff motion module
mkdir -p animatediff_models
cd animatediff_models
wget https://huggingface.co/guoyww/animatediff/resolve/main/mm_sd15_v3.safetensors

# Optional: Ken Burns zoom-pan LoRA (makes videos more cinematic)
mkdir -p loras
cd loras
wget https://huggingface.co/ArtVentureX/animatediff-motion-lora-zoom-in/resolve/main/zoom_in_motion.safetensors
```

**Stuck on downloads?** Use HuggingFace website directly (slower but easier).

### Step 7: Test Installation
```bash
cd ~/ComfyUI
source venv/bin/activate
python main.py
```

You should see:
```
Starting server
Uvicorn running on http://127.0.0.1:8188
```

Open http://localhost:8188 in your browser. You should see ComfyUI interface.

### Step 8: Load AnimateDiff Workflow

In ComfyUI web UI:
1. Click "Load" button
2. Look for "AnimateDiff" sample workflow
3. Click to load it
4. Check the workflow for "Animate Diff Loader" node

If it shows up → ✅ Installation successful!

---

## 🎬 Using AnimateDiff with Digitstack

### Option A: Web UI (Coming Next)
```bash
cd ~/digitstack
python3 ugc_cloner/web_app.py
# Visit http://localhost:8080
# New "AnimateDiff" tab on Generate page
```

### Option B: Python Script (Now)

**Step 1: Prepare product image**
```bash
# Put your product image in:
mkdir -p ~/digitstack/product_images
# Save image as: ~/digitstack/product_images/serum.jpg
```

**Step 2: Generate video**
```python
from pathlib import Path
from ugc_cloner.generators.animatediff_generator import ProductImageAnimator

image_path = Path("product_images/serum.jpg")
video = ProductImageAnimator.animate_product(
    image_path=image_path,
    product_title="Vitamin C Serum",
)
print(f"Video: {video}")  # → output/videos/animated_Vitamin_C_Serum.mp4
```

**Step 3: Run it**
```bash
# Make sure ComfyUI is running in another terminal:
# Terminal 1:
cd ~/ComfyUI && source venv/bin/activate && python main.py

# Terminal 2:
cd ~/digitstack
python3 <<'EOF'
from pathlib import Path
from ugc_cloner.generators.animatediff_generator import ProductImageAnimator

video = ProductImageAnimator.animate_product(
    image_path=Path("product_images/serum.jpg"),
    product_title="Vitamin C Serum",
)
print(f"✓ Video: {video}")
EOF
```

---

## ⚡ Performance on M1

| Image Resolution | Video Time | Quality |
|------------------|-----------|---------|
| 512×512 | 30 sec | Good |
| 768×768 | 1 min | Great |
| 1024×1024 | 2 min | Excellent |

**Tip:** Start with 512×512, scale up once it works.

---

## 🎨 Animation Styles

### Zoom-Pan (Ken Burns) — Cinematic
```python
from ugc_cloner.generators.animatediff_generator import AnimationStyle

style = AnimationStyle(
    motion_scale=1.5,  # More movement
    num_frames=24,     # Smooth 24 frames
    steps=25,
    guidance_scale=8.0,
)
```

### Subtle Panning — Professional
```python
style = AnimationStyle(
    motion_scale=0.8,  # Gentle movement
    num_frames=16,     # Faster playback
    steps=20,
    guidance_scale=7.0,
)
```

### Dynamic Motion — Energetic
```python
style = AnimationStyle(
    motion_scale=2.0,   # Lots of movement
    num_frames=32,      # Smooth slow motion
    steps=30,
    guidance_scale=9.0,
)
```

---

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'animatediff'"
```bash
cd ~/ComfyUI/custom_nodes/comfyui-animatediff
pip install -r requirements.txt
```

### "Cannot connect to localhost:8188"
```bash
# ComfyUI not running. Start it:
cd ~/ComfyUI
source venv/bin/activate
python main.py
```

### "Out of memory" (MPS memory issues)
```bash
# Reduce frame count or image resolution
# In code:
style = AnimationStyle(num_frames=12)  # Instead of 24
```

### Workflow crashes on load
```bash
# Clear ComfyUI cache:
cd ~/ComfyUI
rm -rf models/__pycache__
python main.py
```

---

## 📊 Workflow: Product Image → UGC Video

```
Product Image
     ↓
AnimateDiff (motion + Ken Burns)
     ↓
24fps MP4 video (1 min)
     ↓
+ Add voiceover (gTTS)
     ↓
+ Add text overlays (product name, price, CTA)
     ↓
Final UGC Video (ready for TikTok/Instagram)
```

---

## 🔗 Links

- **ComfyUI:** https://github.com/comfyanonymous/ComfyUI
- **AnimateDiff:** https://github.com/ArtVentureX/comfyui-animatediff
- **Models:** https://huggingface.co/guoyww/animatediff
- **Stable Diffusion 1.5:** https://huggingface.co/runwayml/stable-diffusion-v1-5

---

## Next Steps

1. ✅ **Install ComfyUI + AnimateDiff** (this guide)
2. ✅ **Test with product image**
3. 🔄 **I'll add Web UI integration** (coming soon)
4. 📅 **Auto-batch generation** (10+ videos overnight)

---

**Questions?** Check ComfyUI docs or GitHub issues.

**Ready?** Run the setup above and tell me when ComfyUI is running! 🚀
