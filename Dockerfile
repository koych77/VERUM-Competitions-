FROM node:20-bookworm AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY --from=frontend /app/frontend/dist ./frontend/dist
RUN addgroup --system verum && adduser --system --ingroup verum verum \
    && mkdir -p /app/uploads \
    && chown -R verum:verum /app
USER verum
ENV PYTHONPATH=/app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
