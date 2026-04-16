from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd


def _gaussian_pdf(x: np.ndarray, mean: float, var: float) -> np.ndarray:
    var = max(float(var), 1e-8)
    coef = 1.0 / np.sqrt(2.0 * np.pi * var)
    return coef * np.exp(-0.5 * ((x - mean) ** 2) / var)


def fit_two_state_gaussian_hmm(
    x: np.ndarray,
    n_iter: int = 30,
) -> dict[str, np.ndarray]:
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or x.size < 20:
        mu = np.array([np.nanmean(x), np.nanmean(x)], dtype=float)
        var = np.array([np.nanvar(x) + 1e-6, np.nanvar(x) + 1e-6], dtype=float)
        A = np.array([[0.95, 0.05], [0.05, 0.95]], dtype=float)
        pi = np.array([0.5, 0.5], dtype=float)
        return {"mu": mu, "var": var, "A": A, "pi": pi, "filtered": np.tile(pi, (x.size, 1))}

    q1, q2 = np.nanpercentile(x, [30, 70])
    mu = np.array([q1, q2], dtype=float)
    var = np.array([np.nanvar(x) + 1e-6, np.nanvar(x) + 1e-6], dtype=float)
    A = np.array([[0.95, 0.05], [0.05, 0.95]], dtype=float)
    pi = np.array([0.5, 0.5], dtype=float)

    T = x.size
    for _ in range(n_iter):
        B = np.column_stack([_gaussian_pdf(x, mu[k], var[k]) for k in range(2)]) + 1e-12

        alpha = np.zeros((T, 2), dtype=float)
        c = np.zeros(T, dtype=float)
        alpha[0] = pi * B[0]
        c[0] = alpha[0].sum()
        alpha[0] /= c[0]
        for t in range(1, T):
            alpha[t] = (alpha[t - 1] @ A) * B[t]
            c[t] = alpha[t].sum()
            alpha[t] /= c[t]

        beta = np.zeros((T, 2), dtype=float)
        beta[-1] = 1.0
        for t in range(T - 2, -1, -1):
            beta[t] = (A * B[t + 1] * beta[t + 1]).sum(axis=1)
            beta[t] /= max(c[t + 1], 1e-12)

        gamma = alpha * beta
        gamma /= gamma.sum(axis=1, keepdims=True)

        xi = np.zeros((T - 1, 2, 2), dtype=float)
        for t in range(T - 1):
            numer = np.outer(alpha[t], beta[t + 1] * B[t + 1]) * A
            denom = max(numer.sum(), 1e-12)
            xi[t] = numer / denom

        pi = gamma[0]
        A = xi.sum(axis=0)
        A /= A.sum(axis=1, keepdims=True)

        for k in range(2):
            w = gamma[:, k]
            denom = max(w.sum(), 1e-12)
            mu[k] = float((w * x).sum() / denom)
            var[k] = float((w * (x - mu[k]) ** 2).sum() / denom) + 1e-8

    return {"mu": mu, "var": var, "A": A, "pi": pi, "filtered": gamma}


@dataclass
class RidgeModel:
    mean_: np.ndarray
    std_: np.ndarray
    beta_: np.ndarray

    def predict(self, X: np.ndarray) -> np.ndarray:
        Xs = (X - self.mean_) / self.std_
        Xb = np.column_stack([np.ones(Xs.shape[0]), Xs])
        return Xb @ self.beta_


def fit_ridge_closed_form(X: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> RidgeModel:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    mean_ = np.nanmean(X, axis=0)
    std_ = np.nanstd(X, axis=0)
    std_[std_ == 0.0] = 1.0
    Xs = (X - mean_) / std_
    Xb = np.column_stack([np.ones(Xs.shape[0]), Xs])
    I = np.eye(Xb.shape[1], dtype=float)
    I[0, 0] = 0.0
    beta = np.linalg.pinv(Xb.T @ Xb + alpha * I) @ (Xb.T @ y)
    return RidgeModel(mean_=mean_, std_=std_, beta_=beta)


class TabularQLearner:
    def __init__(self, alpha: float = 0.1, gamma: float = 0.9, epsilon: float = 0.0) -> None:
        self.alpha = float(alpha)
        self.gamma = float(gamma)
        self.epsilon = float(epsilon)
        self.q: Dict[Tuple[int, int], float] = {}

    def get(self, state: int, action: int) -> float:
        return self.q.get((int(state), int(action)), 0.0)

    def update(self, state: int, action: int, reward: float, next_state: int) -> None:
        key = (int(state), int(action))
        old = self.q.get(key, 0.0)
        best_next = max(self.get(next_state, 0), self.get(next_state, 1))
        target = reward + self.gamma * best_next
        self.q[key] = old + self.alpha * (target - old)

    def best_action(self, state: int) -> int:
        q0 = self.get(state, 0)
        q1 = self.get(state, 1)
        return 1 if q1 > q0 else 0
