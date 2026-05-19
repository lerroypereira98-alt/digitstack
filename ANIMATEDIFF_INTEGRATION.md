# AnimateDiff Full Integration Guide

Complete overview of AnimateDiff integration with Digitstack for generating cinematic UGC videos on M1 Macs.

---

## 📋 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Digitstack Web App                         │
│                    (FastAPI, localhost:8080)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  /api/animatediff/generate
                    │  POST endpoint
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   ┌────────┐          ┌──────────┐         ┌─────────┐
   │ Python │◄────────►│ ComfyUI  │◄───────►│  M1 GPU │
   │ Layer  │          │ WebSocket│         │ (Metal) │
   └────────┘          │ API      │         └─────────┘
        │              │ :8188    │
        │              └──────────┘
        │                    ▲
        └────────────────────┘
             AnimateDiff
          Custom Nodes
          + Models
```

**Key Components:**

1. **Digitstack Web App** — FastAPI server on localhost:8080
   - Receives POST requests with product image + animation settings
   - Returns job_id for real-time progress streaming
   - Uses SSE (Server-Sent Events) for progress callbacks

2. **ComfyUI Server** — Node-based AI framework on localhost:8188
   - Runs locally on M1 Mac (Apple Silicon GPU support)
   - Executes AnimateDiff workflows
   - Manages model loading and inference

3. **AnimateDiff Nodes** — Custom nodes in ComfyUI
   - Loads product image
   - Applies motion animation (zoom-pan style)
   - Generates MP4 video output

---

## 🎯 Request/Response Flow

### 1. User Submits Generation Request

```bash
curl -X POST http://localhost:8080/api/animatediff/generate \
  -H "Content-Type: application/json" \
  -d '{
    "product_title": "Vitamin C Serum",
    "image_path": "serum.jpg",
    "motion_scale": 1.2,
    "num_frames": 20
  }'
```

### 2. Web App Queues Job

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 3. Background Worker Processes

Web app spawns thread that:
1. Loads image from `product_images/` directory
2. Creates ComfyUI workflow (JSON)
3. POSTs workflow to ComfyUI
4. Polls for completion every 2 seconds
5. Emits progress events via SSE

### 4. Client Streams Progress

```bash
curl http://localhost:8080/api/jobs/a1b2c3d4.../stream

# Receives:
event: log
data: {"msg":"Animating Vitamin C Serum..."}

event: progress
data: {"msg":"Generating... (5s)"}

event: log
data: {"msg":"✓ Video generated!"}

event: complete
data: {"video_path":"output/videos/animated_Vitamin_C_Serum.mp4"}
```

---

## 🔧 Configuration & Customization

### Animation Style Presets

**Location:** `ugc_cloner/generators/animatediff_generator.py` (AnimationStyle class)

```python
@dataclass
class AnimationStyle:
    motion_scale: float = 1.0      # 0.5-2.0 (movement intensity)
    num_frames: int = 16           # 8-32 (video smoothness)
    steps: int = 20                # 15-30 (quality/detail)
    guidance_scale: float = 7.5    # 5-15 (text prompt adherence)
```

**Presets:**
- **Cinematic:** `motion_scale=1.5, num_frames=24, steps=25` — More movement, smoother
- **Professional:** `motion_scale=0.8, num_frames=16, steps=20` — Subtle, clean
- **Dynamic:** `motion_scale=2.0, num_frames=32, steps=30` — High energy
- **Fast:** `motion_scale=1.0, num_frames=12, steps=15` — Quick preview

### ComfyUI Workflow

**Location:** `ugc_cloner/generators/animatediff_generator.py` (line 133-184)

Workflow nodes:
1. `CheckpointLoaderSimple` — Load Stable Diffusion 1.5 model
2. `LoadImage` — Load product image
3. `AnimateDiffLoaderWithContext` — Load motion module + apply motion_scale
4. `LoraLoader` — Apply Ken Burns zoom-pan style (optional)
5. `CLIPTextEncode` — Encode text prompt: "cinematic product showcase..."
6. `KSampler` — Run inference with custom steps/guidance
7. `AnimateDiffVideoOutput` — Export to MP4

Customize by editing workflow dict in `_generate_comfyui()` method.

---

## 📁 File Structure

```
digitstack/
├── ANIMATEDIFF_M1_SETUP.md           ← Installation guide
├── ANIMATEDIFF_QUICKSTART.md         ← 15-min quick start
├── ANIMATEDIFF_TEST_GUIDE.md         ← Validation steps
├── ANIMATEDIFF_INTEGRATION.md        ← This file
├── products.example.json             ← Example product list
│
├── ugc_cloner/
│   ├── web_app.py                    ← FastAPI server
│   │   └── /api/animatediff/generate ← Main endpoint
│   │   └── /api/jobs/{id}/stream     ← SSE progress
│   │
│   └── generators/
│       ├── animatediff_generator.py  ← AnimateDiff integration
│       │   ├── AnimationStyle         ← Config dataclass
│       │   ├── AnimateDiffGenerator   ← Main class
│       │   └── ProductImageAnimator   ← Convenience wrapper
│       │
│       ├── ltx_video_generator.py    ← LTX-Video (alternative)
│       └── [other generators...]
│
├── scripts/
│   └── batch_animate_products.py     ← Batch generation script
│
└── product_images/                   ← User product images here
    ├── serum.jpg
    ├── probiotics.jpg
    └── [...]
```

---

## 🚀 Usage Patterns

### Pattern 1: Simple One-Off Video

```python
from pathlib import Path
from ugc_cloner.generators.animatediff_generator import ProductImageAnimator

video = ProductImageAnimator.animate_product(
    image_path=Path("product_images/serum.jpg"),
    product_title="Vitamin C Serum",
)
print(f"Video: {video}")
```

**Time:** 30 sec - 1 min

### Pattern 2: Custom Style

```python
from ugc_cloner.generators.animatediff_generator import (
    AnimateDiffGenerator,
    AnimationStyle,
)

gen = AnimateDiffGenerator()
style = AnimationStyle(
    motion_scale=1.5,
    num_frames=24,
    steps=25,
)

video = gen.generate(
    image_path=Path("product_images/product.jpg"),
    product_title="Product",
    style=style,
)
```

### Pattern 3: Batch Processing

```bash
# Directory of images
python scripts/batch_animate_products.py \
  --dir product_images/ \
  --style cinematic \
  --limit 10

# Or JSON list
python scripts/batch_animate_products.py \
  --products products.json \
  --style dynamic
```

### Pattern 4: Web API

```bash
# Start services
cd ~/ComfyUI && source venv/bin/activate && python main.py  # Terminal 1
cd ~/digitstack && python ugc_cloner/web_app.py              # Terminal 2

# Request video
curl -X POST http://localhost:8080/api/animatediff/generate \
  -H "Content-Type: application/json" \
  -d '{"product_title":"Serum","image_path":"serum.jpg"}'

# Get job_id, stream progress
curl http://localhost:8080/api/jobs/{job_id}/stream
```

### Pattern 5: Python with Progress Callback

```python
def on_progress(event: str, data: dict):
    if event == "progress":
        print(f"  {data['msg']}")
    elif event == "complete":
        print(f"✓ Done: {data['video_path']}")

gen = AnimateDiffGenerator()
video = gen.generate(
    image_path=Path("product_images/product.jpg"),
    product_title="Product",
    emit_fn=on_progress,
)
```

---

## ⚙️ System Requirements

### Hardware
- **GPU:** Apple Silicon (M1/M2/M3 Mac)
- **RAM:** 8GB minimum (4-6GB for AnimateDiff)
- **Disk:** ~40GB for models + output

### Software
- **Python:** 3.11+
- **ComfyUI:** Latest from GitHub
- **AnimateDiff:** Custom nodes from ComfyUI Manager
- **Models:**
  - Stable Diffusion 1.5 (2.1 GB)
  - AnimateDiff Motion Module v3 (1.5 GB)
  - Optional: Ken Burns LoRA (100 MB)

---

## 🔌 API Reference

### POST `/api/animatediff/generate`

**Request:**
```json
{
  "product_title": "Vitamin C Serum",
  "image_path": "serum.jpg",
  "motion_scale": 1.2,
  "num_frames": 20
}
```

**Response:**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Notes:**
- `image_path` is relative to `product_images/` directory
- Default motion_scale: 1.0, num_frames: 16
- Video output: `output/videos/animated_*.mp4`

### GET `/api/jobs/{job_id}/stream` (SSE)

**Events:**
- `log` — General status messages
- `progress` — Generation progress (e.g., "Generating... (10s)")
- `error` — Error messages
- `complete` — Job done, includes video_path

**Example:**
```
event: log
data: {"msg":"Connecting to ComfyUI..."}

event: progress
data: {"msg":"Generating... (5s)"}

event: progress
data: {"msg":"Generating... (10s)"}

event: complete
data: {"video_path":"output/videos/animated_Vitamin_C_Serum.mp4"}
```

---

## 🔍 Monitoring & Debugging

### Check ComfyUI Status

```bash
# Is ComfyUI running?
curl http://localhost:8188/system_stats

# Check queued jobs
curl http://localhost:8188/prompt

# Check job history
curl http://localhost:8188/history/{prompt_id}
```

### View Logs

```bash
# Terminal 1: ComfyUI logs
# (running ComfyUI shows logs in real-time)

# Terminal 2: Web app logs
cd ~/digitstack
python ugc_cloner/web_app.py
# Shows logs: Animating Vitamin C Serum...
# Shows logs: Job queued: ...
```

### Test End-to-End

```bash
# 1. Check ComfyUI
curl http://localhost:8188/system_stats  # Should return JSON

# 2. Check web app
curl http://localhost:8080/health  # (if endpoint exists)

# 3. Generate video
curl -X POST http://localhost:8080/api/animatediff/generate \
  -H "Content-Type: application/json" \
  -d '{"product_title":"Test","image_path":"test_product.jpg"}'

# 4. Check job status
curl http://localhost:8080/api/jobs/{job_id}/stream
```

---

## 🐛 Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "ComfyUI not running" | ComfyUI server not started | `cd ~/ComfyUI && python main.py` |
| "Image not found" | Wrong path or not in `product_images/` | Check file exists: `ls product_images/image.jpg` |
| "Generation timeout" | Takes >5 min | Reduce `num_frames` (8-12) or `steps` (15) |
| "Out of memory" | Too many frames or large resolution | Use `AnimationStyle(num_frames=8)` |
| "Module not found" | AnimateDiff nodes not installed | `cd ~/ComfyUI/custom_nodes/comfyui-animatediff && pip install -r requirements.txt` |

---

## 🎯 Performance Tuning

### For Speed (Preview)
```python
style = AnimationStyle(
    motion_scale=1.0,
    num_frames=8,        # Minimum smooth
    steps=12,
    guidance_scale=6.5,
)
# Time: ~20-30 seconds
```

### For Quality (Final)
```python
style = AnimationStyle(
    motion_scale=1.2,
    num_frames=24,
    steps=25,
    guidance_scale=8.0,
)
# Time: ~1-1.5 minutes
```

### For Large Batch
```bash
# Process 10+ videos while you work
python scripts/batch_animate_products.py \
  --products products.json \
  --style fast     # Quick, acceptable quality

# Comes back in 3-5 minutes for 10 videos
```

---

## 🔄 Workflow Examples

### Example 1: Generate Single Product

```bash
# 1. Start ComfyUI
cd ~/ComfyUI && python main.py

# 2. Generate (another terminal)
cd ~/digitstack
python3 <<'EOF'
from pathlib import Path
from ugc_cloner.generators.animatediff_generator import ProductImageAnimator

video = ProductImageAnimator.animate_product(
    image_path=Path("product_images/serum.jpg"),
    product_title="Vitamin C Serum",
)
print(f"✅ Video: {video}")
EOF

# 3. Output: output/videos/animated_Vitamin_C_Serum.mp4
```

### Example 2: Batch Generate from JSON

```bash
# 1. Create products.json
cat > products.json <<'EOF'
[
  {"title":"Serum","image_path":"product_images/serum.jpg"},
  {"title":"Probiotics","image_path":"product_images/probiotics.jpg"},
  {"title":"Earbuds","image_path":"product_images/earbuds.jpg"}
]
EOF

# 2. Start ComfyUI
cd ~/ComfyUI && python main.py

# 3. Batch generate (another terminal)
cd ~/digitstack
python scripts/batch_animate_products.py \
  --products products.json \
  --style cinematic

# 4. Outputs:
# - output/videos/animated_Serum.mp4
# - output/videos/animated_Probiotics.mp4
# - output/videos/animated_Earbuds.mp4
```

### Example 3: Web API Integration

```bash
# 1. Start ComfyUI
cd ~/ComfyUI && python main.py

# 2. Start web app
cd ~/digitstack && python ugc_cloner/web_app.py

# 3. Request via API
JOB=$(curl -s -X POST http://localhost:8080/api/animatediff/generate \
  -H "Content-Type: application/json" \
  -d '{"product_title":"Serum","image_path":"serum.jpg"}' | jq -r .job_id)

# 4. Stream progress
curl http://localhost:8080/api/jobs/$JOB/stream

# 5. Video ready: output/videos/animated_Serum.mp4
```

---

## 🚀 Next Steps

1. ✅ **Install & Test** — Follow ANIMATEDIFF_M1_SETUP.md then ANIMATEDIFF_TEST_GUIDE.md
2. **Generate Videos** — Use ANIMATEDIFF_QUICKSTART.md for common tasks
3. **Batch Process** — Use `scripts/batch_animate_products.py` for 10+ videos
4. **Integrate Web UI** — Add AnimateDiff tab to web interface
5. **Auto-Pipeline** — Discover products → Generate videos → Add overlays → Post to social

---

## 📚 Related Files

- **Setup:** ANIMATEDIFF_M1_SETUP.md
- **Quick Start:** ANIMATEDIFF_QUICKSTART.md
- **Testing:** ANIMATEDIFF_TEST_GUIDE.md
- **Python API:** ugc_cloner/generators/animatediff_generator.py
- **Web API:** ugc_cloner/web_app.py (search `/api/animatediff/generate`)
- **Batch Script:** scripts/batch_animate_products.py
- **Example Products:** products.example.json

---

**Questions?** Check the detailed guides above or examine the source code in the referenced files. 🚀
