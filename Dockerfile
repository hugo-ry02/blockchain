FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY blockchain.py app.py demo.py ./
COPY templates ./templates
COPY static ./static

ENV PORT=5000
ENV DIFFICULTY=4
EXPOSE 5000

CMD ["python", "app.py"]
