FROM python:3.6

ARG KAFKA_BOOTSTRAP_SERVERS
ARG KAFKA_REGISTER_RESPONSE_TOPIC
ARG KAFKA_REGISTER_RESPONSE_CONSUMER_GROUP
ARG KEYDB_HOST
ARG KEYDB_PORT
ARG KEYDB_KEY_TTL
ARG KEYDB_PASSWORD
ARG KEYDB_DONE_SESSION_DB
ARG KEYDB_REGISTER_BUFFER
ARG NUMBER_OF_REGISTER_FRAME
ARG MILVUS_HOST
ARG MILVUS_PORT

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get install -y tzdata tk-dev apt-utils locales

RUN locale-gen en_US.UTF-8

# set locale
ENV LANG C.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
ENV TZ=Asia/Ho_Chi_Minh
ENV KAFKA_BOOTSTRAP_SERVERS=${KAFKA_BOOTSTRAP_SERVERS}
ENV KAFKA_REGISTER_RESPONSE_TOPIC=${KAFKA_REGISTER_RESPONSE_TOPIC}
ENV KAFKA_REGISTER_RESPONSE_CONSUMER_GROUP=${KAFKA_REGISTER_RESPONSE_CONSUMER_GROUP}
ENV KEYDB_HOST=${KEYDB_HOST}
ENV KEYDB_PORT=${KEYDB_PORT}
ENV KEYDB_PASSWORD=${KEYDB_PASSWORD}
ENV KEYDB_DONE_SESSION_DB=${KEYDB_DONE_SESSION_DB}
ENV KEYDB_REGISTER_BUFFER=${KEYDB_REGISTER_BUFFER}
ENV NUMBER_OF_REGISTER_FRAME=${NUMBER_OF_REGISTER_FRAME}
ENV MILVUS_HOST=${MILVUS_HOST}
ENV MILVUS_PORT=${MILVUS_PORT}

RUN apt-get update && apt-get install -y --no-install-recommends

RUN echo "LC_ALL=en_US.UTF-8" >> /etc/environment
RUN echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
RUN echo "LANG=en_US.UTF-8" >> /etc/locale.conf

RUN locale-gen en_US.UTF-8
RUN apt-get install -y build-essential software-properties-common gcc g++ musl-dev

ADD ./docker/requirements/register.rs requirements.txt

COPY . /app

RUN pip install grpcio==1.22.0 grpcio-tools==1.22.0
RUN pip install pymilvus==0.2.13
RUN pip install -r requirements.txt

RUN pip install scikit-build cmake

RUN pip install confluent-kafka==1.5.0

RUN pip install dpsutil==1.3.10

ENV PYTHONPATH=/app
