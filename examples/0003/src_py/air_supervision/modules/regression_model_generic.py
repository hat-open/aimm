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

    def __init__(self, module, name="undefined"):
        self.module = module

        self._id = None
        self.name = name
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

        if self._id:
            x, y = self._get_dataset()
            event_type = ('aimm', 'fit', self._id)
            data = {'args': [x.tolist(), y.tolist()], 'kwargs': kwargs}

            await self._register_event(event_type, data, RETURN_TYPE.FIT)

    async def create_instance(self):

        event_type = ('aimm', 'create_instance')
        data = {'model_type': "air_supervision.aimm.regression_models." + self.name,
                'args': [],
                'kwargs': self.hyperparameters}
        await self._register_event(event_type, data, RETURN_TYPE.CREATE)

        # return_id = await self.module._engine.register(
        #     self.module._source,
        #     [_register_event(('aimm', 'create_instance'),
        #                      {
        #                          'model_type': model_name,
        #                          'args': [],
        #                          'kwargs': {}
        #                      }
        #                      )])
        # self.module._request_ids[return_id[0].event_id._asdict()['instance']] = (RETURN_TYPE.CREATE, self.name)

    async def predict(self, model_input):
        event_type = ('aimm', 'predict', self._id)
        data = {'args': [model_input], 'kwargs': {}}


        await self._register_event(event_type, data, RETURN_TYPE.PREDICT)

        # events = await self.module._engine.register(
        #     self.module._source,
        #     [_register_event(('aimm', 'predict', self._id),
        #                      {'args': [model_input],
        #                       'kwargs': {}
        #                       }
        #                      )])
        # self.module._request_ids[events[0].event_id._asdict()['instance']] = (RETURN_TYPE.PREDICT, self.name)

    def _get_dataset(self):
        goal = 'PT08.S1(CO)'
        df = pandas.read_csv('dataset/sanatized.csv')
        df = df[df[goal].notna()]
        # df = df[pd.notnull(df['goal'])]

        x, y = [], []
        for i in range(48, len(df) - 24, 24):
            x.append(df[goal][i - 48:i])
            y.append(df[goal][i:i + 24])
        x, y = numpy.array(x), numpy.array(y)

        return x, y
