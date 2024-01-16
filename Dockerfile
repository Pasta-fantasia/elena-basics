FROM python:latest

ENV MODULE_NAME=elena_basic
ENV USER=${MODULE_NAME}
ENV CLI=${MODULE_NAME}
ENV USER_HOME=/home/${USER}
# when using pip install --user => ~/.local/bin must be added to PATH
ENV PATH="${PATH}:${USER_HOME}/.local/bin"

# source destination to run pip install
ENV APP_INSTALL_DIR=/opt/${USER}

ENV ELENA_HOME=/home/${USER}/data


## Ensure build-deps
#RUN apt-get update --yes && \
#    apt-get install --yes --no-install-recommends \
#    fonts-dejavu \
#    gfortran \
#    build-essential libssl-dev gcc && \
#    apt-get clean && rm -rf /var/lib/apt/lists/*


# Create a non-root user
RUN set -ex \
    && addgroup --system --gid 1001 ${USER} \
    && adduser  --uid 1001 --gid 1001 ${USER} \
    && mkdir --parents ${APP_INSTALL_DIR} \
    && chown ${USER}:${USER} ${APP_INSTALL_DIR}

## ----------------------------------------------------------
## only while we use pip install git:ssh
#RUN apt-get update --yes && \
#    apt-get install --yes --no-install-recommends \
#    git openssh-client && \
#    apt-get clean && rm -rf /var/lib/apt/lists/*
#WORKDIR "${USER_HOME}/.ssh"
#COPY --chown=${USER}:${USER} id* "${USER_HOME}/.ssh/"
#COPY --chown=${USER}:${USER} known_hosts "${USER_HOME}/.ssh/"
#RUN chmod 600 ${USER_HOME}/.ssh/*
## only while we use pip install git:ssh
## ----------------------------------------------------------


# install as user
USER ${USER}
COPY setup* ${APP_INSTALL_DIR}/
COPY requirements.txt ${APP_INSTALL_DIR}
COPY ${MODULE_NAME} ${APP_INSTALL_DIR}/${MODULE_NAME}/
RUN pip install --user --no-cache-dir ${APP_INSTALL_DIR}
WORKDIR ${USER_HOME}

#CMD ${MODULE_NAME}
CMD elena
