FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt
COPY training ./training
COPY public ./public
COPY checkpoints/noah-seed.json checkpoints/noah-seed.npz ./checkpoints/
RUN useradd --uid 10001 --create-home noah && mkdir -p /var/data/noah && chown -R noah:noah /var/data
USER noah
ENV PORT=10000 NOAH_PROFILE=research-v1 NOAH_DATA=/var/data/noah
EXPOSE 10000
CMD ["python","-m","training.cloud"]
