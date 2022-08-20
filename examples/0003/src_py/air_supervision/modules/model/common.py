from abc import ABC
import hat.aio
import hat.event.server.common
from enum import Enum


class ReturnType(Enum):
    A_PREDICT = 1
    F_PREDICT = 2
    A_FIT = 3
    F_FIT = 4
    A_CREATE = 5
    F_CREATE = 6


class GenericModel(ABC):

    def __init__(self, module, name="undefined", model_type="undefined"):
        self.module = module

        self._id = None
        self.name = name
        self.model_type_short = model_type
        self.model_type = f"air_supervision.aimm.{model_type}_models.{name}"
        self.created = False

        self.hyperparameters = {}

    def get_default_setting(self):
        return self.hyperparameters

    def set_id(self, model_id):
        self._id = model_id
        self.created = True

    async def fit(self, **kwargs):
        raise NotImplementedError()

    async def create_instance(self):
        event_type = ('aimm', 'create_instance')
        data = {'model_type': self.model_type,
                'args': [],
                'kwargs': self.hyperparameters}

        await self._register_event(event_type, data,
                                   ReturnType.A_CREATE
                                   if self.model_type_short == 'anomaly'
                                   else ReturnType.F_CREATE)

    async def predict(self, model_input):
        event_type = ('aimm', 'predict', self._id)
        data = {'args': model_input, 'kwargs': {}}

        await self._register_event(event_type, data,
                                   ReturnType.A_PREDICT
                                   if self.model_type_short == 'anomaly'
                                   else ReturnType.F_PREDICT)

    async def _register_event(self, event_type, data, return_type):
        events = await self.module._engine.register(
            self.module._source,
            [hat.event.server.common.RegisterEvent(
                event_type=event_type,
                source_timestamp=None,
                payload=hat.event.server.common.EventPayload(
                    type=hat.event.server.common.EventPayloadType.JSON,
                    data=data))])
        request_id = events[0].event_id._asdict()['instance']
        self.module._request_ids[request_id] = (return_type, self.name)
