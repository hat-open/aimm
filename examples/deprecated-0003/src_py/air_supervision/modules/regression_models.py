import pandas
import numpy
import hat.aio
import hat.event.server.common

from air_supervision.modules.regression_model_generic import GenericModel


class MultiOutputSVR(GenericModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'C': 2000,
            'svm1': 1,
            'svm2': 2
        }


class linear(GenericModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination': 0.3,
            'cluster1': 1,
            'cluster2': 3
        }



class constant(GenericModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination2': 0.3,
            'other_test_p': 1,
            'third' : 4
        }




# class MultiOutputSVR(GenericModel):
#     def __init__(self, module):
#         super().__init__(module)
#         self.name = 'MultiOutputSVR'
#
#     def set_id(self, model_id):
#         super().set_id(model_id)
#
#     async def fit(self):
#         await super().fit()
#
#     async def create_instance(self):
#         await super()._create_instance('air_supervision.aimm.regression_models.' + self.name)
#
#     async def predict(self, event):
#         await super().predict(event)
#
#
# class linear(GenericModel):
#     def __init__(self, module):
#         super().__init__(module)
#         self.name = 'linear'
#
#     def set_id(self, model_id):
#         super().set_id(model_id)
#
#     async def fit(self):
#         await super().fit()
#
#     async def create_instance(self):
#         await super()._create_instance('air_supervision.aimm.regression_models.' + self.name)
#
#     async def predict(self, event):
#         await super().predict(event)
#
# class constant(GenericModel):
#     def __init__(self, module):
#         super().__init__(module)
#         self.name = 'constant'
#
#     def set_id(self, model_id):
#         super().set_id(model_id)
#
#     async def fit(self):
#         await super().fit()
#
#     async def create_instance(self):
#         await super()._create_instance('air_supervision.aimm.regression_models.' + self.name)
#
#     async def predict(self, event):
#         await super().predict(event)
