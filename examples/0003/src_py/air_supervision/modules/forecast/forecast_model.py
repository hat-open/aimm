from air_supervision.modules.forecast.forecast_model_generic import GenericForecastModel  # NOQA


class MultiOutputSVR(GenericForecastModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'C': 2000,
            'svm1': 1,
            'svm2': 2
        }


class linear(GenericForecastModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination': 0.3,
            'cluster1': 1,
            'cluster2': 3
        }


class constant(GenericForecastModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination2': 0.3,
            'other_test_p': 1,
            'third': 4
        }
