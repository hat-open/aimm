from air_supervision.modules.model.common import GenericModel, ReturnType
import csv
import numpy
import logging


mlog = logging.getLogger(__name__)


class _ForecastModel(GenericModel):

    def __init__(self, module, name):
        super().__init__(module, name, 'forecast')

    async def fit(self, **kwargs):
        if self._id:
            x, y = self._get_dataset()
            event_type = ('aimm', 'fit', self._id)
            data = {'args': [x.tolist(), y.tolist()], 'kwargs': kwargs}

            await self._register_event(event_type, data, ReturnType.F_FIT)

    def _get_dataset(self):
        values = []

        with open("dataset/ambient_temperature_system_failure.csv", "r") as f:
            reader = csv.reader(f, delimiter="\t")
            for i, line in enumerate(reader):
                if not i:
                    continue
                value = float(line[0].split(',')[1])
                value = (float(value) - 32) * 5 / 9

                values.append(value)

        x, y = [], []
        for i in range(48, len(values) - 24, 24):
            x.append(values[i - 48:i])
            y.append(values[i:i + 24])

        x, y = numpy.array(x), numpy.array(y)

        return x, y


class MultiOutputSVR(_ForecastModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'C': 2000,
            'svm1': 1,
            'svm2': 2}


class Linear(_ForecastModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination': 0.3,
            'cluster1': 1,
            'cluster2': 3}


class Constant(_ForecastModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination2': 0.3,
            'other_test_p': 1,
            'third': 4}
