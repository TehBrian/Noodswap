FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system noodswap
RUN adduser --system --ingroup noodswap --home /app noodswap

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir uv
RUN uv sync --no-dev

COPY bot.py /app/bot.py
COPY noodswap /app/noodswap
COPY scripts /app/scripts

RUN chown -R noodswap:noodswap /app

USER noodswap

CMD ["/app/.venv/bin/python", "bot.py"]
