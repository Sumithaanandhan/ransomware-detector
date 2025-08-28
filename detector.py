# detector.py
import warnings
warnings.filterwarnings("ignore", category=UserWarning)   # sklearn warnings
warnings.filterwarnings("ignore", category=FutureWarning)
import argparse, time, os
from collections import deque
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import pandas as pd  # for passing named columns to the model


try:
    import joblib
except:
    joblib = None

EVENT_KEYS = ("created","modified","deleted","moved")

class SlidingWindowCounter:
    def __init__(self, window_seconds=60):
        self.window = window_seconds
        self.events = {k: deque() for k in EVENT_KEYS}

    def add(self, event_key, ts):
        if event_key not in self.events:
            return
        dq = self.events[event_key]
        dq.append(ts)
        cutoff = ts - self.window
        while dq and dq[0] < cutoff:
            dq.popleft()

    def counts(self, now):
        cutoff = now - self.window
        for k in EVENT_KEYS:
            dq = self.events[k]
            while dq and dq[0] < cutoff:
                dq.popleft()
        return {k: len(self.events[k]) for k in EVENT_KEYS}

class FileMonitor(FileSystemEventHandler):
    def __init__(self, model=None, threshold=None, window_seconds=60, cooldown=5):
        self.counter = SlidingWindowCounter(window_seconds)
        self.model = model
        self.threshold = threshold or {"deleted":2, "moved":2}
        self.cooldown = cooldown
        self._last_alert = 0

    def _maybe_alert(self, features):
        now = time.time()
        rule_flag = any(features[k] >= self.threshold.get(k, float("inf")) for k in EVENT_KEYS)
        ml_flag = False

        if self.model is not None:
            try:
                # IMPORTANT: match model.py training order exactly:
                # X = data[["modified","moved","deleted","created"]]
                X = pd.DataFrame([{
                    "modified": features["modified"],
                    "moved": features["moved"],
                    "deleted": features["deleted"],
                    "created": features["created"]
                }])
                ml_flag = (int(self.model.predict(X)[0]) == 1)
            except Exception as e:
                print("Model prediction error:", e)

        if (rule_flag or ml_flag) and (now - self._last_alert > self.cooldown):
            self._last_alert = now
            reasons = []
            if rule_flag: reasons.append("rule")
            if ml_flag: reasons.append("model")
            print("⚠️  ALERT:", " & ".join(reasons), features)

    def _handle(self, event, kind):
        now = time.time()
        self.counter.add(kind, now)
        features = self.counter.counts(now)
        self._maybe_alert(features)

    def on_created(self, event):  self._handle(event, "created")
    def on_modified(self, event): self._handle(event, "modified")
    def on_deleted(self, event):  self._handle(event, "deleted")
    def on_moved(self, event):    self._handle(event, "moved")

def load_model(path):
    if path and joblib and os.path.exists(path):
        return joblib.load(path)
    return None

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="Folder to monitor")
    ap.add_argument("--model", default="data/model.joblib")
    ap.add_argument("--window", type=int, default=60)
    args = ap.parse_args()

    model = load_model(args.model)
    handler = FileMonitor(model=model, window_seconds=args.window)
    observer = Observer()
    observer.schedule(handler, args.path, recursive=True)
    observer.start()
    print(f"Monitoring {args.path}. Using model: {bool(model)}. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()