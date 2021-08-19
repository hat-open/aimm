from hat import json
import time

from aimm import plugins


@plugins.model
class Model1(plugins.Model):
    def __init__(self, *args, **kwargs):
        self._state = {'init': {'args': args, 'kwargs': kwargs},
                       'fit': None}

    def fit(self, *args, **kwargs):
        self._state['fit'] = {'args': args, 'kwargs': kwargs}
        return self

    def predict(self, *args, **kwargs):
        if isinstance(args[0], int):
            time.sleep(args[0])
        return [args, kwargs]

    def serialize(self):
        return json.encode(self._state).encode('utf-8')

    @classmethod
    def deserialize(cls, data):
        state = json.decode(data.decode('utf-8'))
        m = Model1()
        m._state = state
        return m
