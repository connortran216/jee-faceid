FROM ubuntu:18.04

ARG KAFKA_BOOTSTRAP_SERVERS
ARG KAFKA_VERIFIER_RESPONSE_TOPIC
ARG KAFKA_VERIFIER_CONSUMER_GROUP
ARG KEYDB_HOST
ARG KEYDB_PORT
ARG KEYDB_PASSWORD
ARG KEYDB_KEY_TTL
ARG KEYDB_VERIFIER_BUFFER
ARG KEYDB_DONE_SESSION_DB
ARG KEYDB_VERIFIER_QUERY_CACHE_DB
ARG NUMBER_OF_VERIFIER_CONFIDENCE_FRAME
ARG VERIFIER_MIN_THRESHOLD
ARG VERIFIER_MAX_THRESHOLD
ARG VERIFIER_MEAN_THRESHOLD
ARG MILVUS_HOST
ARG MILVUS_PORT
ARG TOP_K_SIMILAR

ENV KAFKA_BOOTSTRAP_SERVERS=${KAFKA_BOOTSTRAP_SERVERS}
ENV KAFKA_VERIFIER_RESPONSE_TOPIC=${KAFKA_VERIFIER_RESPONSE_TOPIC}
ENV KAFKA_VERIFIER_CONSUMER_GROUP=${KAFKA_VERIFIER_CONSUMER_GROUP}
ENV KEYDB_HOST=${KEYDB_HOST}
ENV KEYDB_PORT=${KEYDB_PORT}
ENV KEYDB_PASSWORD=${KEYDB_PASSWORD}
ENV KEYDB_KEY_TTL=${KEYDB_KEY_TTL}
ENV KEYDB_VERIFIER_BUFFER=${KEYDB_VERIFIER_BUFFER}
ENV KEYDB_DONE_SESSION_DB=${KEYDB_DONE_SESSION_DB}
ENV KEYDB_VERIFIER_QUERY_CACHE_DB=${KEYDB_VERIFIER_QUERY_CACHE_DB}
ENV NUMBER_OF_VERIFIER_CONFIDENCE_FRAME=${NUMBER_OF_VERIFIER_CONFIDENCE_FRAME}
ENV VERIFIER_MIN_THRESHOLD=${VERIFIER_MIN_THRESHOLD}
ENV VERIFIER_MAX_THRESHOLD=${VERIFIER_MAX_THRESHOLD}
ENV VERIFIER_MEAN_THRESHOLD=${VERIFIER_MEAN_THRESHOLD}
ENV MILVUS_HOST=${MILVUS_HOST}
ENV MILVUS_PORT=${MILVUS_PORT}
ENV TOP_K_SIMILAR=${TOP_K_SIMILAR}

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get install -y \
	tk-dev apt-utils python3-pip tzdata locales

# create alias
RUN cd /usr/bin \
  && ln -sf python3 python \
  && ln -sf pip3 pip

ENV LANG C.UTF-8

RUN locale-gen en_US.UTF-8

# set locale
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
ENV TZ=Asia/Ho_Chi_Minh

RUN apt-get update && apt-get install -y --no-install-recommends

RUN apt-get install -y libturbojpeg

RUN apt-get install -y libssl-dev libffi-dev

RUN pip install scikit-build cmake

RUN pip install torch==1.5.1 torchvision==0.6.1 opencv-python==4.2.0.34

RUN pip install grpcio==1.22.0 grpcio-tools==1.22.0

RUN pip install pymilvus==0.2.13

RUN pip install scikit-learn==0.23.1

RUN pip install pymongo==3.10.1

RUN pip install kafka-python==2.0.1

RUN pip install redis==3.5.3

RUN pip install numpy==1.18.5

RUN pip install confluent-kafka==1.5.0

RUN pip install dpsutil==1.3.10

ENV PYTHONPATH=/app
