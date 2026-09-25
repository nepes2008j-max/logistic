# A deployable image. Works on anything that takes a Dockerfile — Fly.io,
# Render, Railway, Koyeb, a VPS — and on this machine with plain `docker run`.
FROM python:3.12-slim

# Unbuffered so logs appear in the platform's log viewer as they happen rather
# than when the buffer fills, and no .pyc litter in the layer.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependencies in their own layer so a code change does not reinstall them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Not root. A stored-XSS or path bug should not come with write access to the
# application's own source.
# uid 1000 because Hugging Face Spaces runs containers as that user and will
# not let the process write anywhere it does not own. Other hosts do not care
# which uid this is, so one value works everywhere.
RUN useradd --create-home --uid 1000 handshake \
 && mkdir -p instance static/uploads/items static/uploads/profiles \
 && chown -R handshake:handshake /app
USER handshake
ENV HOME=/home/handshake

# SQLite and the uploaded images live here. Mount a volume on it or the data
# disappears with the container — every free host that offers persistent disk
# wants this path.
VOLUME ["/app/instance"]

EXPOSE 8000

# gunicorn, not app.run(). Two workers with four threads each is plenty for
# SQLite, which serialises writes anyway; more workers would only queue harder
# on the same lock. The timeout is generous because an SMTP handshake can be
# slow, though mail is sent off-thread so it should not reach this.
#
# $PORT because Render, Railway and Koyeb assign one; 8000 when nothing does.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 60 --access-logfile - app:app"]
