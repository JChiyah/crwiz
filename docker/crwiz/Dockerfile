FROM python:3.7.3

RUN mkdir -p /usr/src/crwiz
WORKDIR /usr/src/crwiz

COPY requirements.txt /usr/src/crwiz
RUN pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/crwiz

EXPOSE 5000
ENTRYPOINT ["gunicorn", "-w", "1", "-b", ":5000", "-k", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", "run:app"]
