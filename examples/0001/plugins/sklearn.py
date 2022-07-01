from aimm import plugins
import sklearn.svm
import sklearn.datasets
import pickle


@plugins.data_access('iris_inputs')
def iris_inputs():
    return sklearn.datasets.load_iris(return_X_y=True)[0]


@plugins.data_access('iris_outputs')
def iris_outputs():
    return sklearn.datasets.load_iris(return_X_y=True)[1]


@plugins.model
class SVC(plugins.Model):

    def __init__(self, gamma=0.001, C=100.):
        self._svc = sklearn.svm.SVC(gamma=gamma, C=C)

    def fit(self, X, y):
        self._svc = self._svc.fit(X, y)
        return self

    def predict(self, X):
        return self._svc.predict(X)

    def serialize(self):
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, instance_bytes):
        return pickle.loads(instance_bytes)
