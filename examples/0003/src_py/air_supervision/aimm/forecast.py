from sklearn import multioutput, svm, exceptions
import aimm.plugins
import numpy as np
import pickle
from sklearn.linear_model import LinearRegression


@aimm.plugins.model
class MultiOutputSVR(aimm.plugins.Model):
    def __init__(self, **kwargs):
        self.hyperparameters = {}

        if not self._update_hp(**kwargs):
            self.hyperparameters = {"C": 2000}
        self.model = multioutput.MultiOutputRegressor(
            svm.SVR(C=self.hyperparameters["C"])
        )

    def fit(self, x, y, **kwargs):
        if self._update_hp(**kwargs):
            self.model = multioutput.MultiOutputRegressor(
                svm.SVR(C=self.hyperparameters["C"])
            )

        self.model.fit(x, y)
        return self

    def predict(self, x):
        try:
            x = np.array(x).reshape(1, -1)
            return self.model.predict(x).reshape(-1).tolist()
        except exceptions.NotFittedError:
            return []

    def serialize(self):
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, b):
        return pickle.loads(b)

    def _update_hp(self, **kwargs):
        changed = False
        for key, value in kwargs.items():
            if key in self.hyperparameters:
                self.hyperparameters[key] = float(value)
                changed = True
        return changed


@aimm.plugins.model
class Linear(aimm.plugins.Model):
    def __init__(self, **kwargs):
        self.hyperparameters = {}
        self._update_hp(**kwargs)
        self._linear = LinearRegression()

    def fit(self, x, y):
        self._linear = self._linear.fit(x, y)
        return self

    def predict(self, x, **kwargs):
        return self._linear.predict(x).reshape(-1).tolist()

    def serialize(self):
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, b):
        return pickle.loads(b)

    def _update_hp(self, **kwargs):
        changed = False
        for key, value in kwargs.items():
            if key in self.hyperparameters:
                self.hyperparameters[key] = float(value)
                changed = True
        return changed


@aimm.plugins.model
class Constant(aimm.plugins.Model):
    def __init__(self, **kwargs):
        self.hyperparameters = {}
        self._update_hp(**kwargs)
        self._linear = LinearRegression()

    def fit(self, x, y, **kwargs):
        if self._update_hp(**kwargs):
            self._linear = LinearRegression()

        self._linear.fit(x, y)

        return self

    def predict(self, x):
        return self._linear.predict(x)

    def serialize(self):
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, b):
        return pickle.loads(b)

    def _update_hp(self, **kwargs):
        changed = False
        for key, value in kwargs.items():
            if key in self.hyperparameters:
                self.hyperparameters[key] = float(value)
                changed = True
        return changed
