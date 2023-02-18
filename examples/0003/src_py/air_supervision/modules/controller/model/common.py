import abc
import hat.aio
import hat.event.server.common
from enum import Enum
from itertools import count


request_id_counter = count(0)


class ReturnType(Enum):
    CREATE = 1
    FIT = 2
    PREDICT = 3


class GenericModel(abc.ABC):
    def __init__(self, module, model_type, hyperparameters):
        self._module = module

        self._id = None
        self._model_type = model_type

        self._hyperparameters = hyperparameters

    @property
    def model_type(self):
        return self._model_type

    @property
    def hyperparameters(self):
        return self._hyperparameters

    def set_id(self, model_id):
        self._id = model_id

    @abc.abstractmethod
    async def fit(self, **kwargs):
        """Method used to invoke model fitting.

        Args:
            **kwargs: matches concrete model's hyperparameters"""

    async def create_instance(self):
        event_type = ("aimm", "create_instance")
        data = {
            "model_type": self.model_type,
            "args": [],
            "kwargs": self.hyperparameters,
            "request_id": str(next(request_id_counter)),
        }

        await self._register_event(event_type, data, ReturnType.CREATE)

    async def predict(self, model_input):
        event_type = ("aimm", "predict", self._id)
        data = {
            "args": model_input,
            "kwargs": {},
            "request_id": str(next(request_id_counter)),
        }

        await self._register_event(event_type, data, ReturnType.PREDICT)

    async def _register_event(self, event_type, data, return_type):
        await self._module._engine.register(
            self._module._source,
            [
                hat.event.server.common.RegisterEvent(
                    event_type=event_type,
                    source_timestamp=None,
                    payload=hat.event.server.common.EventPayload(
                        type=hat.event.server.common.EventPayloadType.JSON,
                        data=data,
                    ),
                )
            ],
        )
        request_id = data["request_id"]
        self._module._request_ids[request_id] = (return_type, self.model_type)
