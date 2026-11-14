FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/echabot \
    MPLCONFIGDIR=/home/echabot/.config/matplotlib

WORKDIR /app

RUN addgroup --system echabot && adduser --system --ingroup echabot --home /home/echabot echabot

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY src ./src
COPY data ./data
COPY app.py ./.env.example ./

RUN mkdir -p /home/echabot/.config/matplotlib /app/uploads /app/output /app/data && \
    chown -R echabot:echabot /home/echabot /app
USER echabot

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=3)"

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "app:app"]
