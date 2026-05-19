# LTX-Video Local Setup Guide

Generate Seedance-quality UGC videos **100% free, locally** using LTX-Video.

---

## 📋 Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **GPU** | RTX 4060 (8GB VRAM) | RTX 4070+ (12GB+) |
| **RAM** | 16GB system RAM | 32GB system RAM |
| **Disk** | 50GB free | 100GB free |
| **OS** | Windows 10/11, macOS, Linux | Windows 11 |

**Check your GPU VRAM:**
```bash
nvidia-smi  # Look for "memory" line
```

---

## 🚀 Installation (2 Methods)

### Method 1: LTX Desktop (Easiest - Recommended)

**Step 1: Download LTX Desktop**
- Go to: https://ltx.io/ltx-desktop
- Download for your OS (Windows .exe / macOS .dmg)

**Step 2: Install**
```bash
# Windows: Double-click LTX-Desktop-Installer.exe
# macOS: Drag LTX Desktop to Applications folder
# Linux: Extract tar.gz and run
```

**Step 3: First Launch**
- Open LTX Desktop
- It auto-detects your hardware
- Downloads model weights (~40GB) on first run
- Wait ~15-20 minutes

**Step 4: Verify Installation**
- LTX Desktop opens a GUI at `http://localhost:8188`
- You'll see "LTX-Video 2.3" in the interface
- Click "Generate" to test with a sample prompt

**Step 5: Test Integration**
```bash
cd ~/digitstack
python3 -c "
from ugc_cloner.generators.ltx_video_generator import LTXVideoGenerator, VideoPrompt

gen = LTXVideoGenerator()
print(f'Mode detected: {gen.mode}')
# Should print 'Mode detected: comfyui'
"
```

---

### Method 2: ComfyUI Manual Setup (Advanced)

**Step 1: Install ComfyUI**
```bash
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt
```

**Step 2: Download LTX-Video Model**
```bash
# Create models directory
mkdir -p models/diffusion_models
mkdir -p models/text_encoders
mkdir -p models/vae

# Download from HuggingFace
# (You'll need ~40GB free, use Git LFS or manual download)
# https://huggingface.co/tencent/HunyuanVideo

# Download these files into models/:
# - ltx-video-2.3-768-bf16.safetensors → diffusion_models/
# - clip_l.safetensors → text_encoders/
# - llava_llama3_fp8_scaled.safetensors → text_encoders/
# - ltx_video_vae_bf16.safetensors → vae/
```

**Step 3: Install LTX-Video Custom Nodes**
```bash
cd custom_nodes
git clone https://github.com/ltx-video/ComfyUI-LTX
```

**Step 4: Start ComfyUI**
```bash
cd ~/ComfyUI
python main.py
# Opens at http://localhost:8188
```

---

## 🎬 Using LTX-Video with Digitstack

### Option A: Web UI (Easiest)

1. **Start digitstack web app:**
   ```bash
   cd ~/digitstack
   python3 ugc_cloner/web_app.py
   # Opens at http://localhost:8080
   ```

2. **Start LTX Desktop/ComfyUI in background**

3. **In web UI:** (coming soon in next update)
   - Go to "Generate" page
   - Select "LTX-Video" tab
   - Enter product details
   - Click "Generate Video"
   - Wait 1-2 minutes for video

### Option B: Python Script

```python
from ugc_cloner.generators.ltx_video_generator import (
    LTXVideoGenerator,
    VideoPrompt,
)

# Create generator
gen = LTXVideoGenerator(output_dir="output/videos")

# Define video
prompt = VideoPrompt(
    product_title="Vitamin C Serum",
    category="Beauty",
    hook="POV: your skin just transformed 🌟",
    cta="Get 40% off now — link in bio",
    duration=15,
)

# Generate
video_path = gen.generate(
    prompt,
    output_name="vitamin_c_serum_v1",
    emit_fn=lambda event, data: print(f"{event}: {data}"),
)

print(f"Video saved to: {video_path}")
```

### Option C: REST API

```bash
curl -X POST http://localhost:8080/api/ltx/generate \
  -H "Content-Type: application/json" \
  -d '{
    "product_title": "Vitamin C Serum",
    "category": "Beauty",
    "hook": "POV: your skin just transformed",
    "cta": "Get 40% off now",
    "duration": 15
  }'

# Returns: {"job_id": "abc123"}

# Stream progress:
# Open http://localhost:8080/api/jobs/abc123/stream
```

---

## 🎨 Prompt Templates

### Beauty Product
```
POV: your skin just discovered the secret 💎
Cinematic UGC ad with professional lighting,
close-ups of product application,
natural skin glow, 15 seconds
```

### Tech/Electronics
```
POV: you just unboxed the year's best gadget 🚀
Smooth product reveals, minimal aesthetics,
cinematic 24fps, hands interacting naturally
```

### Fitness/Sports
```
POV: 30-day transformation unlocked 💪
Dynamic movement, before/after cuts,
motivational pacing, energetic music sync
```

---

## ⚡ Performance Tips

### Speed Up Generation
```python
# Use faster model variant (fp8 instead of bf16)
# Edit LTX Desktop settings: Quantization → fp8
# Trade: slightly lower quality, 2-3x faster

# Lower resolution for faster preview
# 480×360 → 1 min
# 768×512 → 2 mins (default)
# 1024×576 → 5+ mins
```

### Memory Optimization
```bash
# If running out of VRAM, enable CPU offloading:
# LTX Desktop → Advanced Settings → CPU Offload (slower but works on 6GB)

# Or use quantized model (fp8):
# HuggingFace: ltx-video-2.3-768-fp8.safetensors
```

---

## 🐛 Troubleshooting

### "Connection refused" / "LTX-Video not running"
```bash
# Make sure LTX Desktop is running
# Check if port 8188 is open:
netstat -an | grep 8188  # macOS/Linux
netstat -an | findstr 8188  # Windows

# Or restart LTX Desktop
```

### "CUDA out of memory"
```bash
# Solution 1: Use fp8 quantized model (faster + lower VRAM)
# Solution 2: Lower resolution (480x360 instead of 768x512)
# Solution 3: Lower step count (20 instead of 30)
# LTX Desktop → Settings → Quality slider
```

### "Weights not found"
```bash
# Download model files manually:
# https://huggingface.co/Lightricks/LTX-Video

# Place in LTX Desktop's models folder:
# Windows: %APPDATA%/LTX/models/
# macOS: ~/Library/Application Support/LTX/models/
# Linux: ~/.config/LTX/models/
```

### "Generation takes forever"
```bash
# Normal timing:
# 480×360, 15s @ 8GB GPU → 1-2 min
# 768×512, 15s @ 8GB GPU → 2-3 min
# 768×512, 15s @ 24GB GPU → 30-60 sec

# If slower:
# - GPU is being shared with other apps
# - Model is still downloading
# - System is thermal throttling (overheating)
```

---

## 📊 Example Workflow

**Generate 10 UGC videos automatically:**

```python
from ugc_cloner.generators.ltx_video_generator import (
    LTXVideoGenerator,
    UGCVideoPromptBuilder,
)
from ugc_cloner.agents.viral_finder import Product

products = [
    Product(title="Vitamin C Serum", category="Beauty", ...),
    Product(title="Probiotic Capsules", category="Health", ...),
    # ... more products
]

gen = LTXVideoGenerator()

for i, product in enumerate(products[:10]):
    print(f"\n[{i+1}/10] Generating {product.title}...")

    prompt = UGCVideoPromptBuilder.from_product(product)
    video_path = gen.generate(
        prompt,
        output_name=f"ugc_v{i+1}_{product.title[:20]}",
    )

    if video_path:
        print(f"✓ Saved: {video_path}")
    else:
        print(f"✗ Failed: {product.title}")

print("\n✅ Batch complete!")
```

---

## 🔗 Links

- **LTX Desktop:** https://ltx.io/ltx-desktop
- **LTX GitHub:** https://github.com/Lightricks/LTX-Video
- **ComfyUI:** https://github.com/comfyanonymous/ComfyUI
- **Model Weights:** https://huggingface.co/Lightricks/LTX-Video

---

## Next: Integration with Digitstack

Once LTX-Video is running locally:

1. **Web UI page** (in progress):
   - Dashboard shows LTX status
   - "LTX Generate" tab on Generate page
   - Video preview + download

2. **Auto-pipeline**:
   - Discover products
   - Auto-generate UGC videos via LTX
   - Add overlays (price, CTA)
   - Auto-post to TikTok/Instagram

3. **Batch processing**:
   - Generate 100+ videos overnight
   - Queue system with progress tracking

---

**Questions?** Check the [main README](./README.md) or GitHub issues.
