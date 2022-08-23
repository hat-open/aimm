from air_supervision.modules.controller.model.common import (GenericModel,
                                                             ReturnType)
from datetime import datetime
from hat import aio
import csv


class _AnomalyModel(GenericModel):

    def __init__(self, module, model_import):
        super().__init__(module, 'anomaly', model_import)
        self._executor = aio.create_executor()

    async def fit(self):
        if not self._id:
            return
        event_type = ('aimm', 'fit', self._id)

        train_data = await self._executor(self._ext_get_dataset)
        data = {'args': [train_data, None]}
        await self._register_event(event_type, data, ReturnType.A_FIT)

    def _ext_get_dataset(self):
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


_import_prefix = 'air_supervision.aimm.anomaly'


class SVM(_AnomalyModel):
    def __init__(self, module):
        super().__init__(module, f'{_import_prefix}.SVM')

        self.hyperparameters = {
            'contamination': 0.3,
            'svm1': 1,
            'svm2': 2}


class Cluster(_AnomalyModel):
    def __init__(self, module):
        super().__init__(module, f'{_import_prefix}.Cluster')

        self.hyperparameters = {
            'contamination': 0.3,
            'cluster1': 1,
            'cluster2': 3}


class Forest(_AnomalyModel):
    def __init__(self, module):
        super().__init__(module, f'{_import_prefix}.Forest')

        self.hyperparameters = {
            'contamination': 0.3,
            'other_test_p': 1,
            'third': 4}


class Forest2(_AnomalyModel):
    def __init__(self, module):
        super().__init__(module, f'{_import_prefix}.Forest')

        self.hyperparameters = {
            'contamination2': 0.3,
            'other_test_p': 1,
            'third': 4}
