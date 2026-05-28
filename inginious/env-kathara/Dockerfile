# DOCKER-VERSION 1.1.0

#inherit from the base container, which have all the needed script to launch tasks
ARG   VERSION=latest
ARG   REGISTRY=ghcr.io
FROM  ${REGISTRY}/inginious/env-9-base:${VERSION}
LABEL org.inginious.grading.name="kathara"

ENV DOCKER_HOST="ssh://docker"

RUN  sed -i "s/fds.fromstring/fds.frombytes/g" /usr/lib/python3.13/site-packages/inginious_container_api/utils.py && \
    sed -i "s/fds.fromstring/fds.frombytes/g" /usr/lib/python3.13/site-packages/inginious/utils.py

# Packages needed
RUN dnf -y config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo &&\
    dnf -y install docker-ce-cli git openssh-clients && \
    pip3.13 install --upgrade pip && \
    pip3.13 install setuptools==70.0.0 paramiko && \
    pip3.13 install kathara kathara-lab-checker

# Check the MaxSessions value in sshd_config on the Docker server
RUN sed -i "s@~/.ssh/config@/etc/ssh/ssh_config.d/docker.conf@g" /usr/local/lib/python3.13/site-packages/docker/transport/sshconn.py
RUN sed -i "s/paramiko.RejectPolicy()/paramiko.AutoAddPolicy()/g" /usr/local/lib/python3.13/site-packages/docker/transport/sshconn.py

ADD --chown=4242:4242 --chmod=600 id_ed25519 /etc/ssh/ssh_client_ed25519_key
ADD ssh_config /etc/ssh/ssh_config.d/docker.conf

RUN echo -e "DOCKER_HOST=ssh://docker\n" >> /etc/environment
