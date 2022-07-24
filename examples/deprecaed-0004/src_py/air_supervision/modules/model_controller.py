import pandas
import numpy
import hat.aio
import hat.event.server.common

from air_supervision.modules.model_controller_generic import GenericModel

class SVM(GenericModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination': 0.3,
            'svm1': 1,
            'svm2': 2
        }


class Cluster(GenericModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination': 0.3,
            'cluster1': 1,
            'cluster2': 3
        }



class Forest(GenericModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination': 0.3,
            'other_test_p': 1,
            'third' : 4
        }


class Forest2(GenericModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination2': 0.3,
            'other_test_p': 1,
            'third' : 4
        }



