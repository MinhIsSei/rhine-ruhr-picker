"""Conditional logit (softmax over the options of each choice) fitted with scipy."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ID_COLS = ["choice_id", "option", "chosen"]

def load(path):
    """Read the CSV -> (groups, feature_names, mean, std).
    Every column except choice_id/option/chosen is a feature; text columns (e.g. city) become one-hot."""
    df = pd.read_csv(path)
    X = pd.get_dummies(df.drop(columns=ID_COLS), dtype=float).astype(float)
    mean, std = X.mean(), X.std().replace(0, 1).fillna(1)
    Xn = ((X - mean) / std).to_numpy()
    groups = []
    for _, idx in df.groupby("choice_id").indices.items():
        chosen = df["chosen"].to_numpy()[idx]
        assert chosen.sum() == 1, "Each choice_id must have exactly one row with chosen=1"
        groups.append((Xn[idx], int(np.argmax(chosen))))
    return groups, list(X.columns), mean, std

def _nll(w, groups, l2):
    loss, grad = l2 * w @ w, 2 * l2 * w
    for X, c in groups:
        s = X @ w
        s -= s.max()
        p = np.exp(s)
        p /= p.sum()
        loss -= np.log(p[c] + 1e-12)
        grad += X.T @ p - X[c]
    return loss, grad

def fit(groups, l2=0.5):
    d = groups[0][0].shape[1]
    return minimize(_nll, np.zeros(d), args=(groups, l2), jac=True, method="L-BFGS-B").x

def predict(w, X):
    s = X @ w
    s -= s.max()
    p = np.exp(s)
    return p / p.sum()

def cross_validate(groups, folds=5, l2=0.5, seed=0):
    """Returns (top-1 accuracy, random-guess baseline)."""
    idx = np.random.default_rng(seed).permutation(len(groups))
    hit, base = [], []
    for f in range(folds):
        test = set(idx[f::folds])
        train = [g for i, g in enumerate(groups) if i not in test]
        w = fit(train, l2)
        for i in test:
            X, c = groups[i]
            hit.append(int(np.argmax(predict(w, X)) == c))
            base.append(1 / len(X))
    return float(np.mean(hit)), float(np.mean(base))

def featurize(df, names, mean, std):
    """Turn new options into a feature matrix, normalized exactly like the training data."""
    X = pd.get_dummies(df.drop(columns=[c for c in ID_COLS if c in df.columns]), dtype=float).astype(float)
    X = X.reindex(columns=names, fill_value=0.0)
    return ((X - mean[names]) / std[names]).to_numpy()
