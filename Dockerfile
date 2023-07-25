FROM python:latest

ENV MODULE_NAME=elena_sample
ENV USER=${MODULE_NAME}
ENV CLI=${MODULE_NAME}
ENV USER_HOME=/home/${USER}
ENV APP_INSTALL_DIR=/opt/${USER}

## Ensure build-deps
#RUN apt-get update --yes && \
#    apt-get install --yes --no-install-recommends \
#    fonts-dejavu \
#    gfortran \
#    build-essential libssl-dev libmariadb3 libmariadb-dev \
#    gcc \
#    git openssh-client && \
#    apt-get clean && rm -rf /var/lib/apt/lists/*


# Create a non-root user
RUN set -ex \
    && addgroup --system --gid 1001 ${USER} \
    && adduser  --uid 1001 --gid 1001 ${USER} \
    && mkdir --parents ${APP_INSTALL_DIR} \
    && chown ${USER}:${USER} ${APP_INSTALL_DIR}


# only while we use pip install git:ssh
#WORKDIR "${USER_HOME}/.ssh"
#COPY --chown=${USER}:${USER} id* "${USER_HOME}/.ssh/"
#COPY --chown=${USER}:${USER} known_hosts "${USER_HOME}/.ssh/"
#RUN chmod 600 ${USER_HOME}/.ssh/*
# only while we use pip install git:ssh

# install as root
COPY setup* ${APP_INSTALL_DIR}/
COPY requirements.txt ${APP_INSTALL_DIR}
COPY ${MODULE_NAME} ${APP_INSTALL_DIR}/${MODULE_NAME}

RUN pip install ${APP_INSTALL_DIR}

USER ${USER}
WORKDIR ${USER_HOME}

CMD ${MODULE_NAME}