from hat import aio
from hat import json
from hat.event.server import common
import asyncio
import itertools
import logging


mlog = logging.getLogger(__name__)

json_schema_id = 'hat-aimm://module.yaml#'
json_schema_repo = json.SchemaRepository(json.decode("""
---
id: 'hat-aimm://module.yaml#'
type: object
...
""", format=json.Format.YAML))

_source_id = 0


async def create(conf, engine):
    module = Module()
    module._gw_prefix = ('gateway', 'gateway', 'device', 'device')
    module._subscription = common.Subscription(
        [('measurement', '?', '?'),
         (*module._gw_prefix, 'gateway', 'running'),
         ('aimm', 'state'),
         ('aimm', 'response')])

    global _source_id
    module._source = common.Source(
        type=common.SourceType.MODULE,
        name=__name__,
        id=_source_id)
    _source_id += 1

    module._async_group = aio.Group()
    module._engine = engine
    module._model_id = None
    module._create_model_request_id = None
    module._predict_request_id = None
    module._measurements = {}

    module._predict_task = None
    module._request_gen = itertools.count(1)

    return module


class Module(common.Module):

    @property
    def async_group(self):
        return self._async_group

    @property
    def subscription(self):
        return self._subscription

    async def create_session(self):
        session = ModuleSession()

        session._async_group = self._async_group.create_subgroup()
        session._source = self._source
        session._engine = self._engine
        session._module = self

        return session

    def process(self, events):
        for e in events:
            if e.source == self._source:
                continue

            payload = e.payload.data
            if e.event_type == (*self._gw_prefix, 'gateway', 'running'):
                if payload is False:
                    yield self._process_event(('gateway', 'gateway',
                                               'device', 'device',
                                               'system', 'enable'), True)

            elif e.event_type[0] == 'measurement':
                self._measurements = json.set_(
                    self._measurements, list(e.event_type[1:]), payload)
                if self._predict_task is None:
                    self._predict_task = self.async_group.spawn(self._predict)

            elif e.event_type == ('aimm', 'state'):
                if ((self._model_id is None
                     or self._model_id not in payload['models'])
                        and self._create_model_request_id is None):
                    self._model_id = None
                    request_ev = self._process_event(
                        ('aimm', 'create_instance'),
                        {'model_type': 'aimm_plugins.power.StateEstimator',
                         'args': [], 'kwargs': {}})
                    request_ev_id = request_ev.event_id
                    self._create_model_request_id = request_ev_id._asdict()
                    yield request_ev

            elif e.event_type == ('aimm', 'response'):
                if payload['request_id'] == self._create_model_request_id:
                    self._model_id = str(payload['result'])
                elif payload['request_id'] == self._predict_request_id:
                    result = payload['result']
                    if result is None:
                        continue
                    bus_ids = (set(result['vm_pu']) | set(result['va_degree'])
                               | set(result['p_mw']) | set(result['q_mvar']))
                    for bus_id in bus_ids:
                        yield self._process_event(('estimation', bus_id, 'v'),
                                                  result['vm_pu'][bus_id])
                        yield self._process_event(('estimation', bus_id, 'va'),
                                                  result['va_degree'][bus_id])
                        yield self._process_event(('estimation', bus_id, 'p'),
                                                  result['p_mw'][bus_id])
                        yield self._process_event(('estimation', bus_id, 'q'),
                                                  result['q_mvar'][bus_id])

    async def _predict(self):
        await asyncio.sleep(1)  # buffer measurements
        try:
            if self._model_id is None:
                return
            ev = await self._engine.register(
                self._source,
                [_register_event(
                    ('aimm', 'predict', self._model_id),
                    {'args': [list(_measurements_to_arg(self._measurements))],
                     'kwargs': {},
                     'request_id': str(next(self._request_gen))})])
            self._predict_request_id = ev[0].event_id._asdict()
        finally:
            self._predict_task = None

    def _process_event(self, event_type, payload):
        return self._engine.create_process_event(
            self._source, common.RegisterEvent(
                event_type=event_type,
                source_timestamp=None,
                payload=common.EventPayload(common.EventPayloadType.JSON,
                                            payload)))


def _measurements_to_arg(measurements):
    for bus_id, bus_measurements in measurements.items():
        for m_type, value in bus_measurements.items():
            yield {'type': m_type,
                   'element_type': 'bus',
                   'value': value,
                   'std_dev': 10,
                   'element': int(bus_id),
                   'side': None}


class ModuleSession(common.ModuleSession):

    @property
    def async_group(self):
        return self._async_group

    async def process(self, changes):
        return self._module.process(changes)


def _register_event(event_type, payload):
    return common.RegisterEvent(
        event_type=event_type,
        source_timestamp=None,
        payload=common.EventPayload(common.EventPayloadType.JSON, payload))
