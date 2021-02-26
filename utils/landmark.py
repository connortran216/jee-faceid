import os
import json
import math
import numpy as np
from utils.keydb import KeyDB


class Metric:
    def __init__(self):
        self.ratio_epsilon = 0.1
        self.cosin_epsilon = 0.1

    @staticmethod
    def dist(X, Y):
        return math.sqrt((X[0] - Y[0]) ** 2 + (X[1] - Y[1]) ** 2)

    @staticmethod
    def cos(a, b, c):
        return float(a**2 + b**2 - c**2)/(a*b)


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


class FacialLandmark(Metric):
    def __init__(self, a, b, c, d, e):
        super(FacialLandmark, self).__init__()

        self.a, self.b, self.c = a, b, c
        self.d, self.e = d, e

        self.ab = Metric.dist(self.a, self.b)
        self.ac = Metric.dist(self.a, self.c)
        self.bc = Metric.dist(self.b, self.c)
        self.cd = Metric.dist(self.c, self.d)
        self.ce = Metric.dist(self.c, self.e)
        self.de = Metric.dist(self.d, self.e)
        self.ad = Metric.dist(self.a, self.d)
        self.be = Metric.dist(self.b, self.e)

        self.r1 = float(self.ac / self.ce)
        self.r2 = float(self.bc / self.cd)
        self.r3 = float(self.ab / self.de)

        """
        A---------B
         \       /
          \     /
           \   /
             C
           /   \
          /     \
         /       \
        D---------E
        """

        self.cos_bac = Metric.cos(self.ab, self.ac, self.bc)
        self.cos_abc = Metric.cos(self.ab, self.bc, self.ac)
        self.cos_acb = Metric.cos(self.ac, self.bc, self.ab)

        self.cos_dce = Metric.cos(self.cd, self.ce, self.de)
        self.cos_cde = Metric.cos(self.de, self.cd, self.ce)
        self.cos_ced = Metric.cos(self.ce, self.de, self.cd)

        self.cos_acd = Metric.cos(self.ac, self.cd, self.ad)
        self.cos_bce = Metric.cos(self.bc, self.ce, self.be)

    def __eq__(self, other):
        if abs(self.r1 - other.r1) > self.ratio_epsilon: return False
        if abs(self.r2 - other.r2) > self.ratio_epsilon: return False
        if abs(self.r3 - other.r3) > self.ratio_epsilon: return False

        if abs(self.cos_bac - other.cos_bac) > self.cosin_epsilon: return False
        if abs(self.cos_abc - other.cos_abc) > self.cosin_epsilon: return False
        if abs(self.cos_acb - other.cos_acb) > self.cosin_epsilon: return False

        if abs(self.cos_dce - other.cos_dce) > self.cosin_epsilon: return False
        if abs(self.cos_cde - other.cos_cde) > self.cosin_epsilon: return False
        if abs(self.cos_ced - other.cos_ced) > self.cosin_epsilon: return False

        if abs(self.cos_acd - other.cos_acd) > self.cosin_epsilon: return False
        if abs(self.cos_bce - other.cos_bce) > self.cosin_epsilon: return False

        return True

    def __str__(self):
        return f'r1: {self.r1}, r2: {self.r2}, r3: {self.r3}, acd: {self.cos_acd}, acb: {self.cos_acb}'

    def __dict__(self):
        return {
            'a': self.a.tolist() if not type(self.a) == type(list()) else self.a,
            'b': self.b.tolist() if not type(self.b) == type(list()) else self.b,
            'c': self.c.tolist() if not type(self.c) == type(list()) else self.c,
            'd': self.d.tolist() if not type(self.d) == type(list()) else self.d,
            'e': self.e.tolist() if not type(self.e) == type(list()) else self.e
        }


class FacialLandmarkWarehouse:
    def __init__(self):
        super().__init__()
        
        self.keydb_connector = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_REGISTER_DB', 2)
        )

    def add(self, session, other):
        self.keydb_connector.rpush(session, json.dumps(other.__dict__()))

    def __len__(self, session):
        return self.keydb_connector.llen(session)

    def contains(self, session, obj):
        if not self.keydb_connector.exists(session):
            return False

        for idx in range(self.keydb_connector.llen(session)):
            _obj = self.keydb_connector.lindex(session, idx)
            _obj = json.loads(_obj)
            fobj = FacialLandmark(_obj['a'], _obj['b'], _obj['c'], _obj['d'], _obj['e'])
            if obj == fobj:
                return True
        
        return False

