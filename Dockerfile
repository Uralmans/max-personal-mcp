FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements.lock.txt && useradd --uid 1000 --create-home app && mkdir /data && chown app:app /data
COPY app/ /app/
USER app
EXPOSE 8765
CMD ["python", "server.py"]
