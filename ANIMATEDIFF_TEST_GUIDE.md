# AnimateDiff Testing Guide

Once you've completed the setup from `ANIMATEDIFF_M1_SETUP.md`, use this guide to validate everything works.

---

## ✅ Pre-Test Checklist

- [ ] ComfyUI installed in `~/ComfyUI`
- [ ] AnimateDiff nodes installed in `~/ComfyUI/custom_nodes/comfyui-animatediff`
- [ ] Models downloaded:
  - [ ] Stable Diffusion 1.5 (`v1-5-pruned-emaonly.safetensors`)
  - [ ] AnimateDiff motion module (`mm_sd15_v3.safetensors`)
  - [ ] (Optional) Ken Burns zoom LoRA (`zoom_in_motion.safetensors`)
- [ ] Have a test product image (or use sample)

---

## 🚀 Step 1: Start ComfyUI

Open **Terminal 1** and run:

```bash
cd ~/ComfyUI
source venv/bin/activate
python main.py
```

Wait for:
```
Starting server
Uvicorn running on http://127.0.0.1:8188
```

✅ **Success:** ComfyUI running at http://localhost:8188

---

## 🧪 Step 2: Test with Python Script

Open **Terminal 2** and run:

```bash
cd ~/digitstack

# Test 1: Check if ComfyUI is detected
python3 <<'EOF'
from ugc_cloner.generators.animatediff_generator import AnimateDiffGenerator

gen = AnimateDiffGenerator()
print(f"✓ ComfyUI detected: {gen.available}")
if not gen.available:
    print("❌ ComfyUI not running. Start it in Terminal 1 first.")
    exit(1)

print("✓ AnimateDiff generator ready!")
EOF
```

Expected output:
```
✓ ComfyUI detected: True
✓ AnimateDiff generator ready!
```

---

## 🎬 Step 3: Generate Your First Video

### Option A: Use Sample Image (Fastest)

Create a simple test image:

```bash
# Create product_images directory
mkdir -p ~/digitstack/product_images

# Generate a simple test image (512x512, light blue)
python3 <<'EOF'
from PIL import Image
import os

img = Image.new('RGB', (512, 512), color='lightblue')
img.save('product_images/test_product.jpg')
print("✓ Test image created: product_images/test_product.jpg")
EOF
```

### Option B: Use Your Own Product Image

```bash
# Copy your product image to:
cp /path/to/your/image.jpg ~/digitstack/product_images/my_product.jpg
```

---

## 🎨 Step 4: Generate Animation

```bash
python3 <<'EOF'
from pathlib import Path
from ugc_cloner.generators.animatediff_generator import (
    AnimateDiffGenerator,
    AnimationStyle,
)

# Create generator
gen = AnimateDiffGenerator(output_dir="output/videos")

# Define animation style (subtle for first test)
style = AnimationStyle(
    motion_scale=1.0,      # Gentle motion
    num_frames=16,         # Smooth playback
    steps=20,              # Fewer steps = faster
    guidance_scale=7.5,
)

# Generate video
print("Starting video generation...")
print("⏳ This takes 30 sec - 1 min on M1...")
video_path = gen.generate(
    image_path=Path("product_images/test_product.jpg"),
    product_title="Test Product",
    output_name="test_animation",
    style=style,
)

if video_path:
    print(f"✅ SUCCESS! Video saved to: {video_path}")
    print(f"   Size: {video_path.stat().st_size / 1024 / 1024:.1f} MB")
else:
    print("❌ Video generation failed. Check Terminal 1 for ComfyUI errors.")
EOF
```

Expected: `output/videos/test_animation.mp4` created (2-5 MB)

---

## 📹 Step 5: Test Web API

While ComfyUI is running, test the web endpoint:

```bash
# Start web app in Terminal 3
cd ~/digitstack
python3 ugc_cloner/web_app.py
```

In **Terminal 4**, test the AnimateDiff endpoint:

```bash
# Generate via REST API
curl -X POST http://localhost:8080/api/animatediff/generate \
  -H "Content-Type: application/json" \
  -d '{
    "product_title": "API Test Product",
    "image_path": "test_product.jpg",
    "motion_scale": 1.2,
    "num_frames": 20
  }'
```

Expected response:
```json
{"job_id": "abc123def456..."}
```

Then stream progress:
```bash
curl http://localhost:8080/api/jobs/abc123def456.../stream
```

Watch real-time progress:
```
event: log
data: {"msg":"Animating API Test Product..."}

event: progress
data: {"msg":"Generating... (5s)"}

event: log
data: {"msg":"✓ Video generated!"}

event: complete
data: {"video_path":"output/videos/api_test_animation.mp4"}
```

---

## 🎯 Different Animation Styles

Once basic test works, try different styles:

### Cinematic (Ken Burns) — More Motion
```python
style = AnimationStyle(
    motion_scale=1.5,
    num_frames=24,
    steps=25,
    guidance_scale=8.0,
)
```

### Professional (Subtle) — Gentle Zoom
```python
style = AnimationStyle(
    motion_scale=0.7,
    num_frames=16,
    steps=20,
    guidance_scale=7.0,
)
```

### Dynamic (High Energy) — Lots of Movement
```python
style = AnimationStyle(
    motion_scale=2.0,
    num_frames=32,
    steps=30,
    guidance_scale=9.0,
)
```

---

## 🐛 Troubleshooting

### "ComfyUI not running" or "available: False"
```bash
# In Terminal 1:
cd ~/ComfyUI
source venv/bin/activate
python main.py
```

### "Cannot connect to localhost:8188"
- ComfyUI crashed? Check Terminal 1 for errors
- Check port: `lsof -i :8188` (macOS/Linux)
- Restart ComfyUI

### "ModuleNotFoundError: No module named 'animatediff'"
```bash
cd ~/ComfyUI/custom_nodes/comfyui-animatediff
pip install -r requirements.txt
cd ~/ComfyUI
python main.py  # Restart
```

### "Out of memory" (kernel panic or process killed)
```python
# Use smaller parameters
style = AnimationStyle(
    motion_scale=0.8,
    num_frames=12,      # Instead of 16-24
    steps=15,           # Instead of 20+
    guidance_scale=7.0,
)
```

### Generation takes forever (>2 min)
- M1 is doing heavy work — normal for first video
- Subsequent videos may be faster (caching)
- Check Activity Monitor (GPU %): should see high GPU usage

### Video quality looks bad
- Try higher `steps`: 25-30 instead of 20
- Increase `motion_scale`: 1.2-1.5 for more cinematic motion
- Ensure your input image is clear and well-lit

---

## 📊 Performance Checklist

| Stage | Expected Time | What to Watch |
|-------|---------------|---------------|
| Model loading | 5-10 sec | Terminal 1 shows "Connecting to ComfyUI..." |
| Workflow submission | 2-3 sec | Terminal shows "Job queued: ..." |
| Video generation | 20-45 sec | Terminal shows "Generating... (5s)", "(10s)", etc. |
| **Total** | **30-60 sec** | Video file appears in `output/videos/` |

If generation takes >2 min:
- Check if M1 is running other heavy apps
- Try smaller `num_frames` (8-12)
- Check ComfyUI Terminal 1 for warnings

---

## ✅ Success Criteria

You're done when:

1. ✅ `test_animation.mp4` is created and playable
2. ✅ Video shows smooth zoom/pan motion on product
3. ✅ REST API `/api/animatediff/generate` returns job_id
4. ✅ SSE `/api/jobs/{job_id}/stream` shows progress events
5. ✅ Generation completes in <90 seconds

---

## 🎯 Next Steps

Once validated:

1. **Generate real product videos:**
   ```python
   video = ProductImageAnimator.animate_product(
       image_path=Path("product_images/serum.jpg"),
       product_title="Vitamin C Serum",
   )
   ```

2. **Batch generate 10+ videos:**
   ```bash
   python3 scripts/batch_animate_products.py --products products.json
   ```

3. **Integrate with web UI** (coming soon):
   - Upload product image
   - Set animation style
   - Click "Generate"
   - Download MP4

---

## 📞 Need Help?

1. Check ComfyUI Terminal 1 for actual error messages
2. Verify models are in correct directories:
   ```bash
   ls -la ~/ComfyUI/models/checkpoints/
   ls -la ~/ComfyUI/models/animatediff_models/
   ```
3. Try with smaller `num_frames` first (8-12) to debug faster
4. Check `/root/.claude/projects` for logs if needed

---

**Ready?** Follow the steps above and tell me when you see `✅ SUCCESS!` 🚀
