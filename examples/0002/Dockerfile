FROM python:3.10

WORKDIR /opt/aimm

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY hat.sh .
COPY aimm.sh .

COPY conf ./conf
COPY src_py ./src_py
COPY view ./view

CMD ["./hat.sh"]
