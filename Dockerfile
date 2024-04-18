FROM python:3.11-bullseye

RUN pip install --upgrade pip

# Download and install Anaconda3
RUN apt-get update && apt-get install -y wget bzip2 \
    && rm -rf /var/lib/apt/lists/* \
    && wget https://repo.anaconda.com/archive/Anaconda3-2021.11-Linux-x86_64.sh -O ~/anaconda.sh \
    && bash ~/anaconda.sh -b -p /opt/conda \
    && rm ~/anaconda.sh
ENV PATH="/opt/conda/bin:${PATH}"
RUN conda init bash
RUN conda create -n chantlab python=3.11

# Install git
RUN apt update && apt install -y git

# Install all requirements
COPY ./requirements.txt .
RUN /bin/bash -c "source activate chantlab && pip install -r requirements.txt"
RUN conda install bioconda::mafft

# Copy all project files to the VM
COPY ./backend /opt/chantlab_backend/backend
COPY ./core /opt/chantlab_backend/core
COPY ./mafft-temp /opt/chantlab_backend/mafft-temp
COPY ./melodies /opt/chantlab_backend/melodies
COPY ./scripts /opt/chantlab_backend/scripts
COPY ./chants.db /opt/chantlab_backend/chants.db
COPY ./manage.py /opt/chantlab_backend/manage.py

# Change the working directory
WORKDIR /opt/chantlab_backend

# Create the entrypoint script file and add the content
RUN echo '#!/bin/bash\n' \
    '# Script that supervisor uses to keep the chantlab back-end running.\n' \
    '. ~/.bashrc\n' \
    'if ! ps ax | grep -v grep | grep "chantlab/bin/gunicorn backend.wsgi:application --bind 0.0.0.0:8000" > /dev/null\n' \
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
    '    gunicorn backend.wsgi:application --bind 0.0.0.0:8000\n' \
    'fi\n' \
    | sed 's/^ //g' \
    > /opt/run_chantlab_backend.sh
RUN chmod +x /opt/run_chantlab_backend.sh

# Install Supervisord
RUN apt-get update && apt-get install -y supervisor \
&& rm -rf /var/lib/apt/lists/*
RUN echo '[program:chantlab_backend]\n' \
    'command=/opt/run_chantlab_backend.sh\n' \
    'autostart=true\n' \
    'autorestart=true\n' \
    'stderr_logfile=/var/log/run_chantlab_backend.err.log\n' \
    'stdout_logfile=/var/log/run_chantlab_backend.out.log\n' \
    | sed 's/^ //g' \
    > "/etc/supervisor/conf.d/supervisord.conf"

# Set default ENV variables if not set yet (for instance in docker compose)
ENV SUPER_USER_NAME="root"
ENV SUPER_USER_PASSWORD="root"
ENV SUPER_USER_EMAIL="root@root.com"

# Expose port 8000
EXPOSE 8000

CMD ["/usr/bin/supervisord","-n", "-c", "/etc/supervisor/supervisord.conf"]