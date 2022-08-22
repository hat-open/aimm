import abc
import hat.aio
import hat.event.server.common
from enum import Enum


class ReturnType(Enum):
    CREATE = 1
    FIT = 2
    PREDICT = 3


class GenericModel(abc.ABC):

    def __init__(self, module, model_family, model_type):
        self.module = module

        self._id = None
        self.model_family = model_family
        self.model_type = model_type
        self.created = False

        self.hyperparameters = {}

    def get_default_setting(self):
        return self.hyperparameters

    def set_id(self, model_id):
        self._id = model_id
        self.created = True

    @abc.abstractmethod
    async def fit(self):
        '''Method used to invoke model fitting.'''

    async def create_instance(self):
        event_type = ('aimm', 'create_instance')
        data = {'model_type': self.model_type,
                'args': [],
                'kwargs': self.hyperparameters}

        await self._register_event(event_type, data, ReturnType.CREATE)

    async def predict(self, model_input):
        event_type = ('aimm', 'predict', self._id)
        data = {'args': model_input, 'kwargs': {}}

        await self._register_event(event_type, data, ReturnType.PREDICT)

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
        self.module._request_ids[request_id] = (return_type, self.model_type)
