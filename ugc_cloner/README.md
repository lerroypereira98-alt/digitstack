# UGC Video Cloner — Quick Start Guide

## What This Does (30-Second Summary)

Automated 200-300 viral product videos + slideshows **for free, locally**:
1. **Discovers** trending products from Amazon + TikTok (high commission, high reviews)
2. **Generates** UGC scripts → TTS voiceovers → product images
3. **Creates** 1080p vertical videos (Ken Burns effect) + styled slideshows
4. **Schedules** posts to TikTok, Instagram, YouTube Shorts automatically

**Time**: ~4-8 hours for 250 videos on a modern CPU
**Cost**: $0 (only needs FFmpeg + Python + free TTS)

---

## Installation

### 1. System Requirements
```bash
# Install FFmpeg (video engine)
sudo apt update && sudo apt install ffmpeg -y    # Ubuntu/Debian
brew install ffmpeg                               # macOS
choco install ffmpeg                              # Windows

# Verify:
ffmpeg -version
```

### 2. Python Setup
```bash
cd ugc_cloner

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate    # Linux/Mac
# or: venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt --upgrade
```

### 3. Configure Your Settings
```bash
# Edit the config file
nano config/settings.yaml    # or use your favorite editor
```

**Minimum required changes:**
```yaml
amazon:
  partner_tag: "YOUR_ASSOCIATES_TAG-20"  # Get from Amazon Associates
  min_commission_pct: 3.0
  categories:
    - "Beauty"
    - "Health"
    - "Kitchen"
    - "Electronics"
```

**For auto-posting (optional):**
```yaml
tiktok:
  access_token: "your_tiktok_api_token"
  client_key: "..."
  client_secret: "..."

instagram:
  username: "your_username"
  password: "your_password"

youtube:
  credentials_file: "config/youtube_credentials.json"
```

---

## Usage

### Preview Mode (No Files Generated)
```bash
python main.py --dry-run
```
Shows what would be created without actually generating anything.

### Step 1: Discover Products
```bash
python main.py --step discover
```
Scrapes Amazon Best Sellers + TikTok trending, ranks by affiliate commission.
Output: `output/discovery_results.json`

```
Rank  Quality      $/sale  Est. Monthly   Title
─────────────────────────────────────────────────────────────────
1     excellent    $2.50   $3,750         Niacinamide 12% Serum (Beauty)
2     excellent    $1.85   $2,775         Probiotics Daily Capsules
3     good         $1.20   $1,800         Stainless Steel Water Bottle
```

### Step 2: Generate Content (250 videos + 250 slideshows by default)
```bash
python main.py --step generate
```

**What happens:**
- Downloads product images (6 per product)
- Generates UGC-style scripts (viral hooks + CTAs)
- Creates TTS voiceovers (~3-5 min per product, parallelized)
- Composes 1080p videos with Ken Burns effect + text overlays (~45s per video)
- Creates styled image slideshows for carousel posts

**Progress:**
```
Processing: Niacinamide 12% Serum [excellent, $2.50/sale]
  Images fetched: 6
  Audio generated: 5 scripts
  Videos composed: 5 (1080p)
  Time: ~4 min
```

**Output location:**
```
output/
├── videos/           ← 250 MP4 files (1080×1920, 25-35s each)
├── slideshows/       ← 250+ PNG slides (ready for carousel)
├── images/           ← Product images
├── audio/            ← TTS voiceovers
└── post_queue.json   ← Schedule for auto-posting
```

### Step 3: Schedule Posts (Auto-Post to Platforms)
```bash
python main.py --step schedule
```

**Schedules posts over 60 days:**
```
[tiktok      ] 2024-12-20 07:15  |  Niacinamide 12% Serum
[instagram   ] 2024-12-20 12:30  |  Probiotics Daily Capsules
[youtube     ] 2024-12-20 17:45  |  Stainless Steel Water Bottle
[tiktok      ] 2024-12-20 21:00  |  Wireless Earbuds Pro

Total: 500 | Posted: 0 | Failed: 0
```

### Run Everything in One Go
```bash
python main.py
```
Discover → generate 250 videos → schedule posts (takes 4-8 hours).

---

## Customization

### Batch Size
```bash
python main.py --batch-size 150    # Create 150 instead of 250
```

### Custom Config File
```bash
python main.py --config my_settings.yaml
```

### Video Settings (edit `config/settings.yaml`)
```yaml
generation:
  batch_size: 250                    # Total videos + slideshows
  video_split: 0.6                   # 60% videos, 40% slideshows
  video_duration_sec: 30             # Length of each video
  fps: 30                            # Frame rate
  tts_engine: "gtts"                 # "gtts" | "edge_tts" | "pyttsx3"
  tts_speed: 1.15                    # Slightly faster for UGC vibe
  use_stable_diffusion: false        # Set true if you have A1111 running locally
```

### Posting Schedule (edit `config/settings.yaml`)
```yaml
scheduler:
  posts_per_day: 4                   # 4 posts per day per platform
  campaign_days: 60                  # Spread over 60 days
  timezone: "America/New_York"
  posting_times:
    - "07:00"
    - "12:00"
    - "17:00"
    - "21:00"
  platforms:
    - tiktok
    - instagram
    - youtube_shorts
```

---

## Typical Output Examples

### Video Script Generated
```
Hook:    "I can't believe this Niacinamide serum exists and it's only $12"
Middle:  "This serum has over 10,000 reviews and almost all are 5 stars. 
          The quality is insane for $12."
CTA:     "Link in bio — it's currently on sale. Grab it before it sells out."
```

### Text Overlays on Video
```
┌─────────────────────────────┐
│ I can't believe this exists  │
│       (0-5 seconds)          │
├─────────────────────────────┤
│   Niacinamide 12% Serum     │
│     (5-18 seconds)          │
├─────────────────────────────┤
│         $12.99              │
│     (7-15 seconds)          │
├─────────────────────────────┤
│    👆 LINK IN BIO           │
│     (last 8 seconds)        │
└─────────────────────────────┘
```

---

## Troubleshooting

### "FFmpeg not found"
```bash
which ffmpeg    # Check if installed
ffmpeg -version # Verify it works
# If not installed, run: sudo apt install ffmpeg
```

### "No products passed affiliate filter"
- Check your Amazon categories in `config/settings.yaml`
- Amazon PA-API has rate limits — wait a bit and retry
- Commission thresholds might be too high (`min_commission_pct`)

### "gTTS rate limited"
- Switch to `edge_tts` in config (Microsoft's TTS, faster)
- Or use offline `pyttsx3` (less natural but instant)

### Videos are slow to generate
- FFmpeg uses all CPU cores automatically
- Reduce `batch_size` or `videos_per_product` in config
- Use `--step discover` + `--step generate` separately

### I want to skip certain categories
```yaml
amazon:
  categories:
    - "Beauty"
    - "Health"
    # Remove or add as needed
```

---

## Next Steps

1. **Fill in `config/settings.yaml`** with your Amazon Associates tag
2. **Test with dry-run:** `python main.py --dry-run`
3. **Discover products:** `python main.py --step discover`
4. **Generate 250 videos:** `python main.py --step generate` (4-8 hours)
5. **For auto-posting:** Add TikTok/Instagram/YouTube API credentials to config
6. **Auto-post:** `python main.py --step schedule` (run via cron every 30 min)

---

## Anatomy of a Generated Video

**Input:** 
- 6 product images
- 1 TTS voiceover (~30 seconds)
- 1 UGC script (hook + middle + CTA)

**Process:**
1. Prepare images → 1080×1920 vertical
2. Create slideshow → fade/pan between images
3. Apply Ken Burns effect → zoom + pan animation
4. Overlay text → hook → title → price → CTA
5. Mix audio → sync voiceover
6. Encode → H.264 CRF 18, 30fps

**Output:**
- Single MP4 file (1080×1920, 8-15 MB)
- Ready to upload to TikTok/Instagram/YouTube

---

## Cost Breakdown

| Component | Cost | Notes |
|-----------|------|-------|
| FFmpeg | Free | Open source video engine |
| gTTS | Free | Google's free TTS API |
| Python | Free | Open source |
| Amazon Associates | Free | You earn commission on sales |
| TikTok API | Free | Standard tier, 250K views/day limit |
| Instagram Graph API | Free | Standard tier |
| YouTube API | Free | Standard tier |
| **Total** | **$0** | Only platform fees if you run ads |

---

## Advanced: Local Stable Diffusion (Optional)

If you want AI-generated lifestyle images for products:

```bash
# 1. Install AUTOMATIC1111 WebUI (GPU required, takes 30 min)
# https://github.com/AUTOMATIC1111/stable-diffusion-webui

# 2. Start it locally
python webui.py --listen 127.0.0.1 --port 7860

# 3. Enable in config
generation:
  use_stable_diffusion: true
  sd_api_url: "http://127.0.0.1:7860"

# 4. Run pipeline — it'll generate 3-4 images per product
python main.py
```

---

## Support & Questions

- **Installation issues?** Check that FFmpeg is in your PATH: `ffmpeg -version`
- **Script generation issues?** Make sure internet is working for gTTS
- **Video encoding slow?** That's normal — FFmpeg is thorough. CPU usage will be high.
- **Want to modify scripts?** Edit `generators/tts_engine.py` → `UGC_HOOK_TEMPLATES`

---

**Ready to go? Start here:**
```bash
python main.py --dry-run
```
