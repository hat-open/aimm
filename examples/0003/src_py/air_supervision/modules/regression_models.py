import pandas
import numpy
import hat.aio
import hat.event.server.common

from src_py.air_supervision.modules.regression_model_generic import GenericModel, _register_event, RETURN_TYPE


class MultiOutputSVR(GenericModel):
    def __init__(self, module):
        super().__init__(module)
        self.name = 'MultiOutputSVR'

    def set_id(self, model_id):
        super().set_id(model_id)

    async def fit(self):
        await super().fit()

    async def create_instance(self):
        await super()._create_instance('air_supervision.aimm.regression_models.' + self.name)

    async def predict(self, event):
        await super().predict(event)


class linear(GenericModel):
    def __init__(self, module):
        super().__init__(module)
        self.name = 'linear'

    def set_id(self, model_id):
        super().set_id(model_id)

    async def fit(self):
        await super().fit()

    async def create_instance(self):
        await super()._create_instance('air_supervision.aimm.regression_models.' + self.name)

    async def predict(self, event):
        await super().predict(event)

class constant(GenericModel):
    def __init__(self, module):
        super().__init__(module)
        self.name = 'constant'

    def set_id(self, model_id):
        super().set_id(model_id)

    async def fit(self):
        await super().fit()

    async def create_instance(self):
        await super()._create_instance('air_supervision.aimm.regression_models.' + self.name)

    async def predict(self, event):
        await super().predict(event)
