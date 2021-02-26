FROM python:3.6

ARG REST_HOST
ARG REST_PORT
ARG REST_SECRET_KEY
ARG KEYDB_HOST
ARG KEYDB_PORT
ARG KEYDB_PASSWORD
ARG KEYDB_CACHE_DB
ARG KEYDB_DONE_SESSION_DB
ARG KEYDB_REGISTER_DB
ARG KAFKA_BOOTSTRAP_SERVERS
ARG KAFKA_DETECTOR_TOPIC

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get install -y tzdata tk-dev apt-utils locales

RUN locale-gen en_US.UTF-8

# set locale
ENV LANG C.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
ENV TZ=Asia/Ho_Chi_Minh
ENV REST_HOST=${REST_HOST}
ENV REST_PORT=${REST_PORT}
ENV REST_SECRET_KEY=${REST_SECRET_KEY}
ENV KEYDB_HOST=${KEYDB_HOST}
ENV KEYDB_PORT=${KEYDB_PORT}
ENV KEYDB_PASSWORD=${KEYDB_PASSWORD}
ENV KEYDB_CACHE_DB=${KEYDB_CACHE_DB}
ENV KEYDB_DONE_SESSION_DB=${KEYDB_DONE_SESSION_DB}
ENV KEYDB_REGISTER_DB=${KEYDB_REGISTER_DB}
ENV KAFKA_BOOTSTRAP_SERVERS=${KAFKA_BOOTSTRAP_SERVERS}
ENV KAFKA_DETECTOR_TOPIC=${KAFKA_DETECTOR_TOPIC}

RUN apt-get update && apt-get install -y --no-install-recommends

RUN echo "LC_ALL=en_US.UTF-8" >> /etc/environment
RUN echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
RUN echo "LANG=en_US.UTF-8" >> /etc/locale.conf

RUN locale-gen en_US.UTF-8
RUN apt-get install -y build-essential software-properties-common gcc g++ musl-dev

RUN pip install numpy==1.18.5

RUN pip install pymilvus==0.2.13

ADD ./docker/requirements/gateway.rs requirements.txt

RUN pip install -r requirements.txt
