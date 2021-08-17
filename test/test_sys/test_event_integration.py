from hat import aio
from hat import json
import asyncio
import contextlib
import hat.event.client
import psutil
import pytest

from aimm import plugins
import aimm.server.main

pytestmark = pytest.mark.asyncio


@pytest.fixture
def conf_path(tmp_path):
    return tmp_path


@pytest.fixture
def monitor_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
def monitor_address(monitor_port):
    return f'tcp+sbs://127.0.0.1:{monitor_port}'


@pytest.fixture
async def monitor_server(monitor_address, monitor_port,
                         unused_tcp_port_factory, conf_path):
    master_port = unused_tcp_port_factory()
    ui_port = unused_tcp_port_factory()
    conf = {'type': 'monitor',
            'log': {'version': 1},
            'server': {'address': monitor_address, 'default_rank': 1},
            'master': {
                'address': f'tcp+sbs://127.0.0.1:{master_port}',
                'default_algorithm': 'BLESS_ONE',
                'group_algorithms': {}},
            'slave': {'parents': []},
            'ui': {'address': f'http://127.0.0.1:{ui_port}'}}
    monitor_conf_path = conf_path / 'monitor.yaml'
    json.encode_file(conf, monitor_conf_path)
    proc = psutil.Popen(['python', '-m', 'hat.monitor.server',
                         '--conf', str(monitor_conf_path)])
    try:
        while not _listens_on(proc, monitor_port):
            await asyncio.sleep(0.1)
        yield proc
    finally:
        proc.kill()
        proc.wait()


@pytest.fixture
def event_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()


@pytest.fixture
def event_address(event_port):
    return f'tcp+sbs://127.0.0.1:{event_port}'


@pytest.fixture
async def event_server(event_address, event_port, monitor_address,
                       monitor_server, conf_path):
    conf = {'type': 'event',
            'log': {'version': 1},
            'monitor': {'name': 'event',
                        'group': 'event',
                        'monitor_address': monitor_address,
                        'component_address': event_address},
            'backend_engine': {
                'server_id': 0,
                'backend': {'module': 'hat.event.server.backends.sqlite',
                            'db_path': str(conf_path / 'event.db'),
                            'query_pool_size': 5}},
            'module_engine': {'modules': []},
            'communication': {'address': event_address}}
    event_conf_path = conf_path / 'event.yaml'
    json.encode_file(conf, event_conf_path)
    proc = psutil.Popen(['python', '-m', 'hat.event.server',
                         '--conf', str(event_conf_path)])
    try:
        while not _listens_on(proc, event_port):
            await asyncio.sleep(0.1)
        yield proc
    finally:
        proc.kill()
        proc.wait()


def simple_conf(monitor_address):
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
        'backend': {'module': 'aimm.server.backend.event',
                    'model_prefix': ['aimm', 'model']},
        'control': [{
            'module': 'aimm.server.control.event',
            'event_prefixes': {
                'create_instance': ['create_instance'],
                'add_instance': ['add_instance'],
                'update_instance': ['update_instance'],
                'fit': ['fit'],
                'predict': ['predict']},
            'state_event_type': ['aimm', 'state'],
            'action_state_event_type': ['aimm', 'action_state']}],
        'plugins': {'names': ['test_sys.plugins.basic']},
        'hat': {
            'monitor': {
                'name': 'aimm',
                'group': 'aimm',
                'monitor_address': monitor_address,
                'component_address': None},
            'event_server_group': 'event'}}


@pytest.fixture
async def aimm_server_proc(event_server, monitor_address, conf_path):
    conf = simple_conf(monitor_address)
    aimm_conf_path = conf_path / 'aimm.yaml'
    json.encode_file(conf, aimm_conf_path)
    proc = psutil.Popen(['python', '-m', 'aimm.server',
                         '--conf', str(aimm_conf_path)])
    try:
        yield proc
    finally:
        proc.kill()
        proc.wait()


@pytest.fixture
async def aimm_server_aio(event_server, monitor_address):
    conf = simple_conf(monitor_address)
    plugins.initialize(conf['plugins'])
    async with aio.Group() as group:
        yield group.spawn(aimm.server.main.async_main, conf)


@pytest.fixture
def event_client_factory(event_address, event_server):

    @contextlib.asynccontextmanager
    async def factory(subscriptions):
        client = await hat.event.client.connect(event_address, subscriptions)
        yield client
        await client.async_close()

    return factory


def assert_event(event, event_type, payload, source_timestamp=None):
    assert event.event_type == event_type
    assert event.source_timestamp == source_timestamp
    assert event.payload.data == payload


async def test_connects(aimm_server_proc, monitor_port, event_port):
    while not _connected_to(aimm_server_proc, monitor_port):
        await asyncio.sleep(0.1)
    while not _connected_to(aimm_server_proc, event_port):
        await asyncio.sleep(0.1)


async def test_workflow(aimm_server_aio, event_client_factory):
    model_type = 'test_sys.plugins.basic.Model1'

    async with event_client_factory([('aimm', 'action_state'),
                                     ('aimm', 'model', '*')]) as client:

        args = ['a1', 'a2']
        kwargs = {'k1': '1', 'k2': '2'}
        await client.register_with_response([
            _register_event(('create_instance', ),
                            {'model_type': model_type,
                             'args': args,
                             'kwargs': kwargs,
                             'request_id': '1'})])

        events = await client.receive()
        assert len(events) == 1
        event = events[0]
        assert event.event_type == ('aimm', 'action_state')
        assert event.source_timestamp is None
        assert event.payload.data == {
            'request_id': '1',
            'result': 1}

        model_id = event.payload.data['result']

        events = await client.receive()
        assert len(events) == 1
        event = events[0]
        assert event.event_type == ('aimm', 'model', str(model_id))
        assert event.source_timestamp is None
        assert event.payload.data['type'] == model_type
        assert event.payload.data['instance'] is not None

        args = ['a3', 'a4']
        kwargs = {'k3': '3', 'k4': '4'}
        await client.register_with_response([
            _register_event(('fit', str(model_id)),
                            {'args': args,
                             'kwargs': kwargs,
                             'request_id': '2'})])

        events = await client.receive()
        assert len(events) == 1
        event = events[0]
        assert event.event_type == ('aimm', 'action_state')
        assert event.source_timestamp is None
        assert event.payload.data == {
            'request_id': '2',
            'result': True}

        events = await client.receive()
        assert len(events) == 1
        event = events[0]
        assert event.event_type == ('aimm', 'model', str(model_id))
        assert event.source_timestamp is None
        assert event.payload.data['type'] == model_type
        assert event.payload.data['instance'] is not None

        args = ['a3', 'a4']
        kwargs = {'k3': '3', 'k4': '4'}
        await client.register_with_response([
            _register_event(('predict', str(model_id)),
                            {'args': args,
                             'kwargs': kwargs,
                             'request_id': '3'})])

        events = await client.receive()
        assert len(events) == 1
        event = events[0]
        assert event.event_type == ('aimm', 'action_state')
        assert event.source_timestamp is None
        assert event.payload.data == {
            'request_id': '3',
            'result': [args, kwargs]}


def _listens_on(proc, port):
    return port in (conn.laddr.port for conn in proc.connections()
                    if conn.status == 'LISTEN')


def _connected_to(proc, port):
    return port in (conn.raddr.port for conn in proc.connections()
                    if conn.status == 'ESTABLISHED')


def _register_event(event_type, payload):
    return hat.event.common.RegisterEvent(
        event_type=event_type,
        source_timestamp=None,
        payload=hat.event.common.EventPayload(
            type=hat.event.common.EventPayloadType.JSON,
            data=payload))
