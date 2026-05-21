# Stage 1: Build React frontend
FROM node:20-slim AS ui-builder
WORKDIR /ui
COPY beacon-ui/package*.json ./
RUN npm ci
COPY beacon-ui/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/ api/
COPY governance/ governance/
COPY chroma_db/ chroma_db/

# Copy built UI from Stage 1
COPY --from=ui-builder /ui/dist beacon-ui/dist/

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
