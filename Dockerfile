FROM python:3.12-slim
ARG BUILD_REVISION=unknown
LABEL org.opencontainers.image.revision=$BUILD_REVISION
WORKDIR /opt/nja
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home nja
COPY . .
RUN mkdir -p /var/lib/nja && chown -R nja:nja /var/lib/nja
USER nja
ENV NJA_DATA=/var/lib/nja
EXPOSE 8000
CMD ["gunicorn","--bind","0.0.0.0:8000","--workers","2","--threads","8","--timeout","120","wsgi:application"]
