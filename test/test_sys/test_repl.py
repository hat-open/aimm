from hat import json
import asyncio
import hashlib
import pytest

import aimm.client.repl

pytestmark = pytest.mark.asyncio


@pytest.fixture
def data_path(tmp_path):
    return tmp_path


@pytest.fixture
def aimm_port(unused_tcp_port):
    return unused_tcp_port


def simple_conf(aimm_port, backend_path):
    password_hash = hashlib.sha256()
    password_hash.update('pass'.encode('utf-8'))
    return {
        'log': {
            'version': 1,
            'formatters': {'default': {}},
            'handlers': {
                'syslog': {
                    'class': 'hat.syslog.handler.SysLogHandler',
                    'host': '127.0.0.1',
                    'port': 6514,
                    'comm_type': 'TCP',
                    'level': 'INFO',
                    'formatter': 'default',
                    'queue_size': 10}},
            'root': {
                'level': 'INFO',
                'handlers': ['syslog']},
            'disable_existing_loggers': False},
        'engine': {'sigterm_timeout': 5,
                   'max_children': 5,
                   'check_children_period': 3},
        'backend': {'module': 'aimm.server.backend.sqlite',
                    'path': str(backend_path)},
        'control': [{
            'module': 'aimm.server.control.repl',
            'server': {'host': '127.0.0.1', 'port': aimm_port},
            'users': [{'username': 'user',
                       'password': password_hash.hexdigest()}]}],
        'plugins': {'names': ['test_sys.plugins.basic']}}


@pytest.fixture
async def aimm_server_proc(data_path, aimm_port):
    conf = simple_conf(aimm_port, data_path / 'aimm.db')
    aimm_conf_path = data_path / 'aimm.yaml'
    json.encode_file(conf, aimm_conf_path)
    proc = await asyncio.create_subprocess_shell(
        f'python -m aimm.server --conf {aimm_conf_path}')
    await asyncio.sleep(1)
    yield proc
    proc.kill()
    await proc.wait()


@pytest.fixture
async def repl_client(monkeypatch, aimm_server_proc, aimm_port):
    client = aimm.client.repl.AIMM()
    with monkeypatch.context() as ctx:
        aimm.client.repl.input = input
        ctx.setattr(aimm.client.repl, 'input', lambda _: 'user')
        ctx.setattr(aimm.client.repl, 'getpass', lambda _: 'pass')
        await client.connect(f'ws://127.0.0.1:{aimm_port}/ws')
    yield client
    await client.async_close()


async def test_connects(repl_client):
    await asyncio.sleep(1)
