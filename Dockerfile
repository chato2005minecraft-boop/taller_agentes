FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WORKSPACE_DIR=/workspace/generated_project

WORKDIR /workspace

COPY requirements.txt ./requirements.txt
COPY generated_project/requirements.txt ./generated_project/requirements.txt
RUN pip install --no-cache-dir \
    -r requirements.txt \
    -r generated_project/requirements.txt

COPY . .

CMD ["python", "01_agente_product_owner.py"]
