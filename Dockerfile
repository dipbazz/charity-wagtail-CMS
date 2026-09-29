
# This stage installs the Python packages into a virtualenv.
# It will be discarded in the final image, keeping only the virtualenv.
FROM python:3.14-slim-trixie AS builder

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

# Install the project requirements and the application server. Every package
# ships as a prebuilt wheel (Pillow bundles its own image libraries), so no
# compilers or system -dev packages are needed; --only-binary fails the build
# instead of silently compiling if that ever changes.
COPY requirements.txt /
RUN pip install --no-cache-dir --only-binary=:all: -r /requirements.txt "gunicorn==25.1.0" \
 && pip uninstall --yes pip


# RUNTIME STAGE
# Use an official Python runtime based on Debian 13 "trixie" as a parent image.
FROM python:3.14-slim-trixie AS runtime

# Apply Debian security fixes published since the base image was built.
# Remove pip: nothing installs packages at runtime, and it vendors libraries
# of its own (e.g. msgpack) that would need patching separately.
RUN apt-get update --yes --quiet \
 && apt-get upgrade --yes --quiet \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip uninstall --yes --root-user-action=ignore pip

# Add user that will be used in the container.
RUN useradd wagtail

# Port used by this container to serve HTTP.
EXPOSE 8000

# Set environment variables.
# 1. Force Python stdout and stderr streams to be unbuffered.
# 2. Set PORT variable that is used by Gunicorn. This should match "EXPOSE"
#    command.
# 3. Add the virtual environment to PATH.
# 4. Run the production settings; manage.py and wsgi.py default to dev.
ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=charity.settings.production



# Copy the virtual environment from the builder stage.
COPY --from=builder /opt/venv /opt/venv

# Use /app folder as a directory where the source code is stored.
WORKDIR /app

# Set this directory to be owned by the "wagtail" user, who writes collected
# static files into it at build time.
RUN chown wagtail:wagtail /app

# The SQLite database and editors' uploads live on a volume, so they survive
# rebuilds and redeploys. Django serves the uploads because nothing else in
# this image does; set DJANGO_SERVE_MEDIA=false when a web server or object
# storage serves /media/ instead.
ENV DJANGO_DATA_DIR=/data \
    DJANGO_SERVE_MEDIA=true
RUN mkdir /data && chown wagtail:wagtail /data
VOLUME /data

# Copy the source code of the project into the container.
COPY --chown=wagtail:wagtail . .

# Use user "wagtail" to run the build commands below and the server itself.
USER wagtail

# Collect static files. Production settings refuse to load without these
# variables; the placeholder values exist only for this build step and are
# not stored in the image. Real values are passed at "docker run".
RUN DJANGO_SECRET_KEY=collectstatic-build-only DJANGO_ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput --clear

# Runtime command that executes when "docker run" is called, it does the
# following:
#   1. Migrate the database.
#   2. Start the application server. "exec" replaces the shell with gunicorn,
#      so gunicorn runs as PID 1 and receives "docker stop"'s SIGTERM, letting
#      it finish in-flight requests instead of being killed after a timeout.
# WARNING:
#   Migrating database at the same time as starting the server IS NOT THE BEST
#   PRACTICE. The database should be migrated manually or using the release
#   phase facilities of your hosting platform. This is used only so the
#   Wagtail instance can be started with a simple "docker run" command.
CMD ["/bin/sh", "-c", "set -xe; python manage.py migrate --noinput; exec gunicorn charity.wsgi:application"]
