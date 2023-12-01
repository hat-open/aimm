from sklearn import multioutput, svm, exceptions
import aimm.plugins
import numpy as np
import pickle
import pandas as pd
from sklearn import preprocessing
from sklearn.linear_model import LinearRegression
import random


class GenericPredictionModel(aimm.plugins.Model):
    def __init__(self, **kwargs):
        self.scale_ = -1
        self.mean_ = -1
        self.model = None
        self.hyperparameters = {}

    def _scale(self, x):
        min_max_scaler = preprocessing.StandardScaler()

        self.mean_ = np.mean(x, axis=0)
        self.scale_ = np.std(x, axis=0)

        return pd.DataFrame(min_max_scaler.fit_transform(x))

    def predict(self, x):
        x = pd.DataFrame((x - self.mean_) / self.scale_)
        series = pd.Series(self.model.predict(x))
        rez = series.map({1: 0, -1: 1}).values.tolist()
        x = pd.DataFrame(x * self.scale_ + self.mean_)
        x["result"] = rez
        return x.values.tolist()

    def _update_hp(self, **kwargs):
        changed = False
        for key, value in kwargs.items():
            if key in self.hyperparameters:
                self.hyperparameters[key] = float(value)
                changed = True
        return changed

    def fit(self, x, y, **kwargs):
        self.model.fit(self._scale(x))
        return self

    def serialize(self):
        return pickle.dumps(self)

    @classmethod
    def deserialize(self, b):
        return pickle.loads(b)


@aimm.plugins.model
class MultiOutputSVR(aimm.plugins.Model):
    def __init__(self, **kwargs):
        self.hyperparameters = {}

        if not self._update_hp(**kwargs):
            self.hyperparameters = {"C": 2000}

        self._model = multioutput.MultiOutputRegressor(
            svm.SVR(C=self.hyperparameters["C"])
        )

    def fit(self, x, y, **kwargs):
        if self._update_hp(**kwargs):
            self.model = multioutput.MultiOutputRegressor(
                svm.SVR(C=self.hyperparameters["C"])
            )

        self._model.fit(x, y)
        return self

    def _update_hp(self, **kwargs):
        changed = False
        for key, value in kwargs.items():
            if key in self.hyperparameters:
                self.hyperparameters[key] = float(value)
                changed = True
        return changed

    def predict(self, x):
        try:
            x = np.array(x).reshape(1, -1)
            return self._model.predict(x).reshape(-1).tolist()
        except exceptions.NotFittedError:
            return []

    def serialize(self):
        return pickle.dumps(self)

    @classmethod
    def deserialize(self, b):
        return pickle.loads(b)


@aimm.plugins.model
class linear(aimm.plugins.Model):
    def __init__(self, **kwargs):
        self.hyperparameters = {}

        self._update_hp(**kwargs)

        self._linear = LinearRegression()

    def fit(self, x, y):
        self._linear = self._linear.fit(x, y)
        return self

    def _update_hp(self, **kwargs):
        changed = False
        for key, value in kwargs.items():
            if key in self.hyperparameters:
                self.hyperparameters[key] = float(value)
                changed = True
        return changed

    def predict(self, X, **kwargs):
        return self._linear.predict(X).reshape(-1).tolist()


@aimm.plugins.model
class constant(aimm.plugins.Model):
    def __init__(self, **kwargs):
        self.hyperparameters = {}

        self._update_hp(**kwargs)

        self._linear = LinearRegression()

    def _update_hp(self, **kwargs):
        changed = False
        for key, value in kwargs.items():
            if key in self.hyperparameters:
                self.hyperparameters[key] = float(value)
                changed = True
        return changed

    def fit(self, x, y, **kwargs):
        if self._update_hp(**kwargs):
            self._linear = LinearRegression()

        # self._linear.fit(x, y)

        return self

    def predict(self, X):
        # return self._linear.predict(X)

        return [random.randint(1, 15)] * len(X)

    def serialize(self):
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, b):
        return pickle.loads(b)
