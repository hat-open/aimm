from air_supervision.modules.model.common import GenericModel, ReturnType
from datetime import datetime
import csv


class _AnomalyModel(GenericModel):

    def __init__(self, module, name):
        super().__init__(module, name, 'anomaly')

    async def fit(self, **kwargs):
        if self._id:
            train_data = self._get_dataset()

            event_type = ('aimm', 'fit', self._id)

            data = {'args': [train_data, None], 'kwargs': kwargs}

            await self._register_event(event_type, data, ReturnType.A_FIT)

    def _get_dataset(self):
        train_data = []

        with open("dataset/ambient_temperature_system_failure.csv", "r") as f:
            reader = csv.reader(f, delimiter="\t")
            for i, line in enumerate(reader):
                if not i:
                    continue
                timestamp = datetime.strptime(line[0].split(',')[0],
                                              '%Y-%m-%d %H:%M:%S')
                value = float(line[0].split(',')[1])

                value = (float(value) - 32) * 5 / 9

                train_data.append([
                    value,
                    timestamp.hour,
                    int((timestamp.hour >= 7) & (timestamp.hour <= 22)),
                    timestamp.weekday(),
                    int(timestamp.weekday() < 5)])

        return train_data


class SVM(_AnomalyModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination': 0.3,
            'svm1': 1,
            'svm2': 2}


class Cluster(_AnomalyModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination': 0.3,
            'cluster1': 1,
            'cluster2': 3}


class Forest(_AnomalyModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination': 0.3,
            'other_test_p': 1,
            'third': 4}


class Forest2(_AnomalyModel):
    def __init__(self, module, name):
        super().__init__(module, name)

        self.hyperparameters = {
            'contamination2': 0.3,
            'other_test_p': 1,
            'third': 4}
