# Stage 1: Build and setup environment
FROM python:3.11-slim-bullseye as builder

# Install basic tools and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget bzip2 git build-essential cmake libreadline-dev libncurses5-dev zlib1g-dev libssl-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Miniconda
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh \
    && bash ~/miniconda.sh -b -p /opt/conda \
    && rm ~/miniconda.sh
ENV PATH="/opt/conda/bin:${PATH}"
RUN /opt/conda/bin/conda init bash
RUN conda create -n chantlab python=3.11 && conda clean -afy

# Activate environment and install dependencies
COPY ./requirements.txt .
RUN /bin/bash -c "source /opt/conda/etc/profile.d/conda.sh && conda activate chantlab && pip install -r requirements.txt"

# Install MAFFT
RUN wget https://mafft.cbrc.jp/alignment/software/mafft_7.505-1_amd64.deb \
    && dpkg -i mafft_7.505-1_amd64.deb || apt-get install -f -y \
    && rm mafft_7.505-1_amd64.deb

# Insall MrBayes
RUN git clone --depth=1 https://github.com/Genome-of-Melody/mrbayes_volpiano.git /opt/mrbayes
WORKDIR /opt/mrbayes
RUN ./configure && make && make install
WORKDIR /

# Stage 2: Runtime image
FROM python:3.11-slim-bullseye

# Copy files from build stage
COPY --from=builder /usr/bin/mafft /usr/bin/mafft
COPY --from=builder /usr/libexec/mafft /usr/libexec/mafft
COPY --from=builder /opt/mrbayes/ /opt/mrbayes/
COPY --from=builder /usr/local/bin/mb /usr/local/bin/mb
COPY --from=builder /opt/conda /opt/conda
ENV PATH="/opt/conda/bin:${PATH}"

# Initialize conda
RUN /opt/conda/bin/conda init bash

# Copy project files
COPY ./backend /opt/chantlab_backend/backend
COPY ./core /opt/chantlab_backend/core
COPY ./mafft-temp /opt/chantlab_backend/mafft-temp
COPY ./mrbayes-temp /opt/chantlab_backend/mrbayes-temp
COPY ./resources /opt/chantlab_backend/resources
COPY ./melodies /opt/chantlab_backend/melodies
COPY ./scripts /opt/chantlab_backend/scripts
COPY ./chants.db /opt/chantlab_backend/chants.db
COPY ./manage.py /opt/chantlab_backend/manage.py

# Set working directory
WORKDIR /opt/chantlab_backend

# Install Supervisord
RUN apt-get update && apt-get install -y --no-install-recommends supervisor \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Supervisord configuration
RUN echo '[program:chantlab_backend]\n' \
    'command=/opt/run_chantlab_backend.sh\n' \
    'autostart=true\n' \
    'autorestart=true\n' \
    'stderr_logfile=/var/log/run_chantlab_backend.err.log\n' \
    'stdout_logfile=/var/log/run_chantlab_backend.out.log\n' \
    | sed 's/^ //g' \
    > "/etc/supervisor/conf.d/supervisord.conf"

# Create the entrypoint script file and add the content
RUN echo '#!/bin/bash\n' \
    '# Script that supervisor uses to keep the chantlab backend running.\n' \
    '. /opt/conda/etc/profile.d/conda.sh\n' \
    'if ! ps ax | grep -v grep | grep "chantlab/bin/gunicorn --timeout 0 backend.wsgi:application --bind 0.0.0.0:8000" > /dev/null\n' \
    'then\n' \
    '    # Log restart\n' \
    '    echo "Chantlab backend down; restarting run_chantlab_backend.sh"\n' \
    '    # The right conda environment\n' \
    '    conda activate chantlab\n' \
    '    # Apply database migrations without prompting for user input\n' \
    '    python manage.py migrate --no-input\n' \
    '    # Collect static files from your various applications into one location\n' \
    '    python manage.py collectstatic --no-input\n' \
    "    # Create superuser admin account to be able to log into the Django project's admin page\n" \
    '    DJANGO_SUPERUSER_PASSWORD=$SUPER_USER_PASSWORD python manage.py createsuperuser --username $SUPER_USER_NAME --email $SUPER_USER_EMAIL --noinput\n' \
    '    # Run the Django application using gunicorn\n' \
    '    gunicorn --timeout 0 backend.wsgi:application --bind 0.0.0.0:8000\n' \
    'fi\n' \
    | sed 's/^ //g' \
    > /opt/run_chantlab_backend.sh
RUN chmod +x /opt/run_chantlab_backend.sh

# Environment variables
ENV SUPER_USER_NAME="root"
ENV SUPER_USER_PASSWORD="root"
ENV SUPER_USER_EMAIL="root@root.com"

# Expose port
EXPOSE 8000

# Start the app
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]