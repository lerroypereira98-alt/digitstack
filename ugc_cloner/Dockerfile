FROM python:3.11-slim

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg fonts-dejavu-core --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn pyyaml pytz requests \
    beautifulsoup4 lxml Pillow gtts pyttsx3 APScheduler

COPY . .

RUN mkdir -p output/{videos,slideshows,images,audio} web/static config

EXPOSE 8080

CMD ["python3", "web_app.py"]
