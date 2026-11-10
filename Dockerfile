FROM python:3.15-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ship all static pages plus the entrypoint and backend
COPY index.html donation.html statistics.html styles.css app.js falconbeat-audio.js docker-entrypoint.sh app.py code_matrix.py ./
COPY static ./static

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["./docker-entrypoint.sh"]
# One worker on purpose: queue, scheduler and status live in process memory.
# Threads keep the UI responsive while a request waits for FPP.
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "app:app"]
