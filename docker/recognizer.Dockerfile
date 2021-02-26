FROM python:3.6

ARG KAFKA_BOOTSTRAP_SERVERS
ARG KAFKA_RECOGNIZER_RESPONSE_TOPIC
ARG KAFKA_RECOGNIZER_RESPONSE_CONSUMER_GROUP
ARG KEYDB_HOST
ARG KEYDB_PORT
ARG KEYDB_PASSWORD
ARG KEYDB_KEY_TTL
ARG KEYDB_DONE_SESSION_DB
ARG KEYDB_QUERY_CACHE
ARG TOP_K_SIMILAR
ARG NUMBER_OF_RECOGNIZER_CONFIDENCE_FRAME
ARG RECOGNIZER_MEAN_THRESHOLD
ARG RECOGNIZER_MIN_THRESHOLD
ARG RECOGNIZER_MAX_THRESHOLD
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
ENV KAFKA_RECOGNIZER_RESPONSE_TOPIC=${KAFKA_RECOGNIZER_RESPONSE_TOPIC}
ENV KAFKA_RECOGNIZER_RESPONSE_CONSUMER_GROUP=${KAFKA_RECOGNIZER_RESPONSE_CONSUMER_GROUP}
ENV KEYDB_HOST=${KEYDB_HOST}
ENV KEYDB_PORT=${KEYDB_PORT}
ENV KEYDB_PASSWORD=${KEYDB_PASSWORD}
ENV KEYDB_KEY_TTL=${KEYDB_KEY_TTL}
ENV KEYDB_DONE_SESSION_DB=${KEYDB_DONE_SESSION_DB}
ENV KEYDB_QUERY_CACHE=${KEYDB_QUERY_CACHE}
ENV TOP_K_SIMILAR=${TOP_K_SIMILAR}
ENV NUMBER_OF_RECOGNIZER_CONFIDENCE_FRAME=${NUMBER_OF_RECOGNIZER_CONFIDENCE_FRAME}
ENV RECOGNIZER_MEAN_THRESHOLD=${RECOGNIZER_MEAN_THRESHOLD}
ENV RECOGNIZER_MIN_THRESHOLD=${RECOGNIZER_MIN_THRESHOLD}
ENV RECOGNIZER_MAX_THRESHOLD=${RECOGNIZER_MAX_THRESHOLD}
ENV MILVUS_HOST=${MILVUS_HOST}
ENV MILVUS_PORT=${MILVUS_PORT}

RUN apt-get update && apt-get install -y --no-install-recommends

RUN echo "LC_ALL=en_US.UTF-8" >> /etc/environment
RUN echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
RUN echo "LANG=en_US.UTF-8" >> /etc/locale.conf

RUN locale-gen en_US.UTF-8
RUN apt-get install -y build-essential software-properties-common gcc g++ musl-dev

ADD ./docker/requirements/recognizer.rs requirements.txt

RUN pip install -r requirements.txt

RUN pip install scikit-build cmake

RUN pip install dpsutil==1.3.10

ENV PYTHONPATH=/app