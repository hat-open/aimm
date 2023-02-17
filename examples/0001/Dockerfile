FROM python:3.10

WORKDIR /opt/aimm

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY aimm.yaml .

COPY Iris.ipynb .
COPY plugins ./plugins

ENV PYTHONPATH=/opt/aimm

CMD ["aimm-server", "--conf", "aimm.yaml"]
