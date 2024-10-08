from sklearn import exceptions
import aimm.plugins
import numpy as np
import pickle


import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn import preprocessing
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.svm import OneClassSVM


class GenericAnomalyModel(aimm.plugins.Model):
    def __init__(self, **kwargs):
        self.scale_ = -1
        self.mean_ = -1
        self.model = None
        self.hyperparameters = {}

    def predict(self, x):
        x = pd.DataFrame((x - self.mean_) / self.scale_)
        series = pd.Series(self.model.predict(x))
        return series.map({1: 0, -1: 1}).values.tolist()

    def fit(self, x, y, **kwargs):
        self.model.fit(self._scale(x))
        return self

    def serialize(self):
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, b):
        return pickle.loads(b)

    def _scale(self, x):
        min_max_scaler = preprocessing.StandardScaler()

        self.mean_ = np.mean(x, axis=0)
        self.scale_ = np.std(x, axis=0)

        return pd.DataFrame(min_max_scaler.fit_transform(x))

    def _update_hp(self, **kwargs):
        changed = False
        for key, value in kwargs.items():
            if key in self.hyperparameters:
                self.hyperparameters[key] = float(value)
                changed = True
        return changed


@aimm.plugins.model
class Forest(GenericAnomalyModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not self._update_hp(**kwargs):
            self.hyperparameters = {"contamination": 0.01}

        self.model = IsolationForest(
            contamination=self.hyperparameters["contamination"]
        )

    def fit(self, x, y, **kwargs):
        if self._update_hp(**kwargs):
            self.model = IsolationForest(
                contamination=self.hyperparameters["contamination"]
            )

        return super().fit(x, y, **kwargs)


@aimm.plugins.model
class SVM(GenericAnomalyModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not self._update_hp(**kwargs):
            self.hyperparameters = {"contamination": 0.05}

        self.model = OneClassSVM(
            nu=0.95 * self.hyperparameters["contamination"]
        )
        # nu=0.95 * outliers_fraction  + 0.05

    def fit(self, x, y, **kwargs):
        if self._update_hp(**kwargs):
            self.model = OneClassSVM(
                nu=0.95 * self.hyperparameters["contamination"]
            )

        return super().fit(x, y, **kwargs)


@aimm.plugins.model
class Cluster(GenericAnomalyModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def fit(self, x, y, **kwargs):
        data = x[["value", "hours", "daylight", "DayOfTheWeek", "WeekDay"]]

        outliers_fraction = 0.01

        min_max_scaler = preprocessing.StandardScaler()
        np_scaled = min_max_scaler.fit_transform(data)
        data = pd.DataFrame(np_scaled)
        # reduce to 2 important features
        pca = PCA(n_components=2)
        data = pca.fit_transform(data)
        # standardize these 2 new features
        min_max_scaler = preprocessing.StandardScaler()
        np_scaled = min_max_scaler.fit_transform(data)
        data = pd.DataFrame(np_scaled)

        # calculate with different number of centroids to see the loss plot
        # (elbow method)
        n_cluster = range(1, 20)
        kmeans = [KMeans(n_clusters=i).fit(data) for i in n_cluster]

        # Not clear for me, I choose 15 centroids arbitrarily and add these
        # data to the central dataframe
        x["cluster"] = kmeans[14].predict(data)
        x["principal_feature1"] = data[0]
        x["principal_feature2"] = data[1]

        # return Series of distance between each point and his distance with
        # the closest centroid
        def get_distance_by_point(data, model):
            result = pd.Series()
            for i in range(0, len(data)):
                Xa = np.array(data.loc[i])
                Xb = model.cluster_centers_[model.labels_[i] - 1]
                result.at[i] = np.linalg.norm(Xa - Xb)
            return result

        # get the distance between each point and its nearest centroid. The
        # biggest distances are considered as anomaly
        distance = get_distance_by_point(data, kmeans[14])
        number_of_outliers = int(outliers_fraction * len(distance))
        threshold = distance.nlargest(number_of_outliers).min()
        # anomaly21 contain the anomaly result of method
        # 2.1 Cluster (0:normal, 1:anomaly)
        x["anomaly21"] = int(distance >= threshold)

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
    def deserialize(self, b):
        return pickle.loads(b)
