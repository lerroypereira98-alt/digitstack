# AnimateDiff Quick Start — M1 Mac UGC Videos

Get cinematic UGC videos running on your M1 Mac in **15 minutes** + **5 minutes per video**.

---

## 🚀 Installation (One-Time)

**⏱️ Time: ~15 minutes**

Follow the complete setup guide:
```bash
open ANIMATEDIFF_M1_SETUP.md
```

Key steps:
1. Install Python 3.11
2. Clone ComfyUI
3. Install AnimateDiff nodes
4. Download 3 model files (~4GB)

**When done:** You should see ComfyUI running at http://localhost:8188

---

## 🧪 Validate Installation

**⏱️ Time: ~5 minutes**

Test everything works:
```bash
open ANIMATEDIFF_TEST_GUIDE.md
```

Should see: `✅ SUCCESS! Video saved to: output/videos/test_animation.mp4`

---

## 🎬 Generate Your First Video

**⏱️ Time: ~1 minute + video generation**

### Step 1: Place product image

```bash
# Copy your image to:
cp /path/to/product.jpg ~/digitstack/product_images/product.jpg

# Or use test image:
ls product_images/
```

### Step 2: Generate video

```bash
cd ~/digitstack

python3 <<'EOF'
from pathlib import Path
from ugc_cloner.generators.animatediff_generator import ProductImageAnimator

video = ProductImageAnimator.animate_product(
    image_path=Path("product_images/product.jpg"),
    product_title="My Awesome Product",
)

if video:
    print(f"✅ Video ready: {video}")
else:
    print("❌ Generation failed. Check ComfyUI is running.")
EOF
```

**Result:** `output/videos/animated_My_Awesome_Product.mp4`

---

## 🎨 Customize Animation Style

### Cinematic (Lots of Motion)
```python
from ugc_cloner.generators.animatediff_generator import AnimationStyle

style = AnimationStyle(
    motion_scale=1.5,      # More movement
    num_frames=24,         # Smooth 24 frames
    steps=25,
    guidance_scale=8.0,
)
```

### Professional (Subtle Zoom)
```python
style = AnimationStyle(
    motion_scale=0.8,
    num_frames=16,
    steps=20,
    guidance_scale=7.5,
)
```

### Fast (Quick Preview)
```python
style = AnimationStyle(
    motion_scale=1.0,
    num_frames=12,
    steps=15,
    guidance_scale=7.0,
)
```

Then use:
```python
video = gen.generate(
    image_path=Path("product_images/product.jpg"),
    product_title="Product",
    style=style,
)
```

---

## 📦 Batch Generate 10+ Videos

### From Directory

```bash
# Put images in product_images/
cd ~/digitstack

# Generate all with cinematic style
python scripts/batch_animate_products.py --dir product_images/ --style cinematic

# Or first 5 (for testing):
python scripts/batch_animate_products.py --dir product_images/ --limit 5
```

### From JSON List

```bash
# Create products.json
python scripts/batch_animate_products.py --create-sample

# Edit products.json with your products and image paths

# Generate all
python scripts/batch_animate_products.py --products products.json

# Or preview first:
python scripts/batch_animate_products.py --products products.json --dry-run
```

---

## 🌐 Web API

Integrate AnimateDiff with your web app:

### Start Web Server

```bash
# Terminal 1: Start ComfyUI
cd ~/ComfyUI && source venv/bin/activate && python main.py

# Terminal 2: Start digitstack web app
cd ~/digitstack && python ugc_cloner/web_app.py
# Opens at http://localhost:8080
```

### API: Generate Video

```bash
curl -X POST http://localhost:8080/api/animatediff/generate \
  -H "Content-Type: application/json" \
  -d '{
    "product_title": "Vitamin C Serum",
    "image_path": "serum.jpg",
    "motion_scale": 1.2,
    "num_frames": 20
  }'

# Returns: {"job_id": "abc123..."}
```

### Stream Progress

```bash
curl http://localhost:8080/api/jobs/{job_id}/stream

# Real-time events:
# event: log
# data: {"msg":"Animating..."}
#
# event: progress
# data: {"msg":"Generating... (10s)"}
#
# event: complete
# data: {"video_path":"output/videos/animated_...mp4"}
```

---

## ⚡ Performance Tips

| Image Size | Time | Quality |
|-----------|------|---------|
| 512×512   | 30s  | Good    |
| 768×768   | 1m   | Great   |
| 1024×1024 | 2m   | Excellent |

**Start small, scale up once it works!**

### Speed Up
```python
style = AnimationStyle(
    num_frames=12,   # Instead of 16-24
    steps=15,        # Instead of 20+
    guidance_scale=7.0,
)
```

### Memory Issue?
```python
style = AnimationStyle(
    num_frames=8,    # Minimum smooth
    steps=12,
    guidance_scale=6.5,
)
```

---

## 📊 Workflow

```
Product Image
    ↓
AnimateDiff (motion + zoom)
    ↓
MP4 Video (24fps, 1 min)
    ↓
[Next] Add text overlays (price, CTA)
    ↓
[Next] Add voiceover (gTTS)
    ↓
Final UGC Video (TikTok/Instagram ready)
```

---

## 🐛 Troubleshooting

### "ComfyUI not running"
```bash
# Terminal 1:
cd ~/ComfyUI && source venv/bin/activate && python main.py
```

### "Out of memory" (slowdown or crash)
```python
# Reduce video length
style = AnimationStyle(num_frames=8, steps=12)
```

### "Image not found"
```bash
# Check path exists:
ls product_images/my_image.jpg

# Use full path in code:
image_path=Path("product_images/my_image.jpg"),
```

### "Generation timeout" (>2 min)
- Check M1 isn't running other heavy apps
- Try fewer frames: `num_frames=12`
- Check ComfyUI Terminal 1 for error messages

---

## 📚 Full Documentation

- **Installation:** See `ANIMATEDIFF_M1_SETUP.md`
- **Testing:** See `ANIMATEDIFF_TEST_GUIDE.md`
- **Python API:** See `ugc_cloner/generators/animatediff_generator.py`
- **Web API:** See `ugc_cloner/web_app.py` `/api/animatediff/generate` endpoint

---

## ✅ Success Checklist

- [ ] ComfyUI running at http://localhost:8188
- [ ] Product image in `product_images/`
- [ ] First video generated: `output/videos/animated_*.mp4`
- [ ] Video shows smooth zoom/pan motion
- [ ] Batch generation works: 5+ videos without errors

---

## 🎯 Next Steps

1. **Generate real product videos** with your own images
2. **Customize animations** — try different styles
3. **Batch generate** 10+ videos overnight
4. **Integrate with web UI** — add image upload + live preview
5. **Add overlays** — text (price, CTA) + voiceover

---

**Ready?** Start with ANIMATEDIFF_M1_SETUP.md 🚀
