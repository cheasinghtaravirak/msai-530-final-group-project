# One image recipe for every Django service. Build from the repo root:
#   docker build -f services/Dockerfile --build-arg SERVICE=admin -t retail/admin .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

ARG SERVICE
WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY libs/retail_common/pyproject.toml /libs/retail_common/pyproject.toml
COPY services/${SERVICE}/requirements.txt /app/requirements.txt
COPY libs/retail_common/retail_common /libs/retail_common/retail_common
RUN pip install /libs/retail_common -r /app/requirements.txt

COPY services/${SERVICE} /app

ENV SERVICE_NAME=${SERVICE}
EXPOSE 8000

# Web process by default; workers override the command in docker-compose.yml.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile -"]
