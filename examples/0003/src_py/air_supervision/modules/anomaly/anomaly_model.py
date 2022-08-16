from air_supervision.modules.anomaly.anomaly_model_generic import GenericAnomalyModel  # NOQA


class SVM(GenericAnomalyModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination': 0.3,
            'svm1': 1,
            'svm2': 2
        }


class Cluster(GenericAnomalyModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination': 0.3,
            'cluster1': 1,
            'cluster2': 3
        }


class Forest(GenericAnomalyModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination': 0.3,
            'other_test_p': 1,
            'third': 4
        }


class Forest2(GenericAnomalyModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination2': 0.3,
            'other_test_p': 1,
            'third': 4
        }
