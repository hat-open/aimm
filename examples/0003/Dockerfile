FROM python:3.10

RUN apt update
RUN apt install -y npm
RUN npm install -g yarn

WORKDIR /opt/aimm

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY package.json .
COPY webpack.config.js .

COPY install.sh .
RUN ./install.sh

COPY conf ./conf
COPY src_py ./src_py
COPY src_js ./src_js
COPY src_scss ./src_scss

COPY run.sh .

CMD ["./run.sh"]
