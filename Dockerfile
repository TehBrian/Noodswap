FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV NOODSWAP_ASSETS_DIR=/app/deploy/assets
ENV NOODSWAP_DB_PATH=/app/deploy/assets/noodswap.db
ENV NOODSWAP_CARD_IMAGES_DIR=/app/deploy/assets/card_images
ENV NOODSWAP_CARD_FONTS_DIR=/app/deploy/assets/fonts
ENV NOODSWAP_FRAME_OVERLAYS_DIR=/app/deploy/assets/frame_overlays

WORKDIR /app

RUN addgroup --system noodswap \
    && adduser --system --ingroup noodswap --home /app noodswap

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY bot.py /app/bot.py
COPY noodswap /app/noodswap
RUN mkdir -p /app/deploy/assets
COPY scripts /app/scripts

RUN chown -R noodswap:noodswap /app

USER noodswap

CMD ["python", "bot.py"]
