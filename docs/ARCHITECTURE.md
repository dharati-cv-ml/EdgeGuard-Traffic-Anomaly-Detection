# EdgeGuard Desktop — architecture

 ```text
 CSV import / synthetic dataset
          |
          v
 Data validation and feature transformation
          |
          v
 Deterministic training -> JSON model file
          |
          v
 Batch inference -> classification / score
          |
          +--> Tkinter desktop UI -> results table + charts + CSV export
          |
          +--> CLI evaluation -> JSON metrics
 ```

 Model code is plain Python for reproducible training without NumPy/SciPy DLLs.
 The desktop app is **not a web server** and does not require localhost.
 Automated tests run headlessly in GitHub Actions; desktop UI needs a Windows display.


## Desktop analytics layer
`edgeguard.desktop` implements an offline Tkinter two-tab GUI. After model training and batch scoring, scores and decisions are summarized by a pure-Python histogram and decision counts. The record explorer lists all rows, supports filters, and shows selected-record feature deviations relative to the training median/MAD scales. All chart widgets are native Tkinter Canvas, so Matplotlib, NumPy, SciPy, FastAPI, and network access are unnecessary.
