### Summary

When calling `scipy.linalg.solve(A, b)` on batches of near-singular covariance matrices in our signal-processing pipeline, `numpy` and `scipy` intermittently emit `LinAlgWarning: Ill-conditioned matrix` and produce unstable residuals across runs unless Tikhonov (`L2`) regularization is applied.

### Steps to Reproduce

```python
import numpy as np
import scipy.linalg
import pandas as pd

rng = np.random.default_rng(42)
base = rng.standard_normal((64, 64))
# Construct a nearly rank-deficient symmetric matrix
A = base @ base.T
A[:, -1] = A[:, 0] + 1e-12 * rng.standard_normal(64)
b = rng.standard_normal(64)

x_unreg = scipy.linalg.solve(A, b)
residual_unreg = float(np.linalg.norm(A @ x_unreg - b))

# Compare with Tikhonov regularization (lambda = 1e-6)
x_reg = scipy.linalg.solve(A + 1e-6 * np.eye(64), b)
residual_reg = float(np.linalg.norm(A @ x_reg - b))

df = pd.DataFrame([
    {"solver": "unregularized", "residual_l2": residual_unreg, "cond": float(np.linalg.cond(A))},
    {"solver": "tikhonov_1e-6", "residual_l2": residual_reg, "cond": float(np.linalg.cond(A + 1e-6 * np.eye(64)))},
])
print(df.to_string(index=False))
```

### Expected Triage Action

Please run the reproducer in the scientific Python sandbox and report the condition numbers and L2 residuals for both solvers.
