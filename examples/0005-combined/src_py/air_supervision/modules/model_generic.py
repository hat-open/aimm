from abc import ABC, abstractmethod
import pandas
import numpy
import hat.aio
import hat.event.server.common
import yaml
from enum import Enum
import csv
from datetime import datetime


class RETURN_TYPE(Enum):
    PREDICT = 1
    FIT = 2
    CREATE = 3


class GenericModel(ABC):


    def get_default_setting(self):
        return self.hyperparameters

    def __init__(self, module, name="undefined", model_type="undefined"):
        self.module = module

        self._id = None
        self.name = name
        self.model_type = f"air_supervision.aimm.{model_type}_models.{name}",
        self.created = False

        self.hyperparameters = {}

    def set_id(self, model_id):
        self._id = model_id
        self.created = True

    async def _register_event(self, event_type, data, return_type):
        events = await self.module._engine.register(
            self.module._source,
            [hat.event.server.common.RegisterEvent(
                event_type=event_type,
                source_timestamp=None,
                payload=hat.event.server.common.EventPayload(
                    type=hat.event.server.common.EventPayloadType.JSON,
                    data=data))])
        self.module._request_ids[events[0].event_id._asdict()['instance']] = (return_type, self.name)

    # @abstractmethod
    async def fit(self, **kwargs):
        raise NotImplementedError()

    async def create_instance(self):
        event_type = ('aimm', 'create_instance')
        data = {'model_type': self.model_type,
                'args': [],
                'kwargs': self.hyperparameters}
        await self._register_event(event_type, data, RETURN_TYPE.CREATE)

    async def predict(self, model_input):
        import json
        event_type = ('aimm', 'predict', self._id)
        data = {'args': [json.dumps(model_input)], 'kwargs': {}}

        await self._register_event(event_type, data, RETURN_TYPE.PREDICT)

    def _get_dataset(self):
        raise NotImplementedError()
