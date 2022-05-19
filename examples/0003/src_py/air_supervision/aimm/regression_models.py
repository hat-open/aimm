from sklearn import multioutput, svm, exceptions
import aimm.plugins
import numpy
import pickle
from sklearn.linear_model import LinearRegression


@aimm.plugins.model
class MultiOutputSVR(aimm.plugins.Model):

    def __init__(self):
        self._model = multioutput.MultiOutputRegressor(
            svm.SVR(C=2000))

    def fit(self, x, y):
        self._model.fit(x, y)
        return self

    def predict(self, x):
        try:
            x = numpy.array(x).reshape(1, -1)
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

    def __init__(self):
        self._linear = LinearRegression()

    def fit(self, x, y):
        self._linear = self._linear.fit(x, y)
        return self

    def predict(self, X):
        return self._linear.predict(X).reshape(-1).tolist()



    def serialize(self):
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, b):
        return pickle.loads(b)


@aimm.plugins.model
class constant(aimm.plugins.Model):

    def __init__(self):
        self._linear = LinearRegression()

    def fit(self, X, y):
        self._linear = self._linear.fit(X, y)
        return self

    def predict(self, X):
        # return self._linear.predict(X)

        return [800] * len(X)


    def serialize(self):
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, b):
        return pickle.loads(b)

