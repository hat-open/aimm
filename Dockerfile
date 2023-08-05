FROM python:3.10

WORKDIR /opt/aimm

RUN pip install aimm

ENV PYTHONPATH=/opt/aimm

CMD ["aimm-server", "--conf", "aimm.yaml"]
