FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ship all static pages plus the entrypoint and backend
COPY index.html donation.html requests.html statistics.html styles.css config.template.js docker-entrypoint.sh app.py .

ENV PORT=8000
EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]
