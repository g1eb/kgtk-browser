# A dockerfile for running the kgtk-browser
FROM python:3.7-stretch

RUN apt-get update
RUN apt-get install sqlite3

RUN mkdir /src

COPY requirements.txt /src/requirements.txt

RUN pip install -r /src/requirements.txt

COPY kgtk_browser_config.py /src/
COPY kgtk_browser_app.py /src/
COPY browser/backend/ /src/browser/backend/
COPY post_deploy.sh /src/
COPY venice/ /src/venice/

ARG FLASK_ENV=production
ENV FLASK_ENV=$FLASK_ENV

ARG FLASK_APP=kgtk_browser_app.py
ENV FLASK_APP=$FLASK_APP

ARG KGTK_BROWSER_CONFIG=kgtk_browser_config.py
ENV KGTK_BROWSER_CONFIG=$KGTK_BROWSER_CONFIG

WORKDIR /src

EXPOSE 5006
