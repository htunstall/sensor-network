# Define base image
FROM continuumio/anaconda3

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir pymongo
 
# Set working directory for the project
WORKDIR /run
 
# Python program to run in the container
COPY src/post_listener.py .
COPY src/secrets.py .

ENTRYPOINT ["python3", "post_listener.py"]
