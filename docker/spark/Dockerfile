FROM apache/spark:4.0.2-python3@sha256:87e5d6062e955a045b68376bbf97487d5057ecd8f4f896fb0590339981645de3

USER root
RUN python3 -m pip install --no-cache-dir numpy==1.26.4
ENV PYTHONPATH=/workspace:/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.9-src.zip
WORKDIR /workspace
