from air_supervision.modules.controller.model.common import (GenericModel,
                                                             ReturnType)
from hat import aio
import csv
import numpy
import logging


mlog = logging.getLogger(__name__)


class _ForecastModel(GenericModel):

    def __init__(self, module, model_import):
        super().__init__(module, 'forecast', model_import)
        self._executor = aio.create_executor()

    async def fit(self):
        if not self._id:
            return
        event_type = ('aimm', 'fit', self._id)

        x, y = await self._executor(self._ext_get_dataset)
        data = {'args': [x.tolist(), y.tolist()]}
        await self._register_event(event_type, data, ReturnType.F_FIT)

    def _ext_get_dataset(self):
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

        fit_start = int(len(x) * 0.25)
        return x[fit_start:], y[fit_start:]


_import_prefix = 'air_supervision.aimm.forecast'


class MultiOutputSVR(_ForecastModel):
    def __init__(self, module):
        super().__init__(module, f'{_import_prefix}.MultiOutputSVR')

        self.hyperparameters = {
            'C': 2000,
            'svm1': 1,
            'svm2': 2}


class Linear(_ForecastModel):
    def __init__(self, module):
        super().__init__(module, f'{_import_prefix}.Linear')

        self.hyperparameters = {
            'contamination': 0.3,
            'cluster1': 1,
            'cluster2': 3}


class Constant(_ForecastModel):
    def __init__(self, module):
        super().__init__(module, f'{_import_prefix}.Constant')

        self.hyperparameters = {
            'contamination2': 0.3,
            'other_test_p': 1,
            'third': 4}
