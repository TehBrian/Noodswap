FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system noodswap
RUN adduser --system --ingroup noodswap --home /app noodswap

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY bot.py /app/bot.py
COPY noodswap /app/noodswap
COPY scripts /app/scripts

RUN chown -R noodswap:noodswap /app

USER noodswap

CMD ["python", "bot.py"]
