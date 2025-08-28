# model.py
import warnings
warnings.filterwarnings("ignore", category=UserWarning)   # sklearn warnings
warnings.filterwarnings("ignore", category=FutureWarning)
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import joblib, os

WINDOW = "60S"

def load_log(path):
    df = pd.read_csv(path, names=["event", "path", "timestamp"])
    df["ts"] = pd.to_datetime(df["timestamp"], unit="s")
    return df

def extract_features(df):
    if df.empty:
        return pd.DataFrame(columns=["created","modified","deleted","moved"])
    df = df.set_index("ts")
    counts = (
        df.groupby("event")
          .resample(WINDOW)
          .size()
          .unstack(level=0)
          .fillna(0)
    )
    for c in ["created", "modified", "deleted", "moved"]:
        if c not in counts.columns:
            counts[c] = 0
    counts = counts[["created","modified","deleted","moved"]]
    counts = counts.reset_index()
    return counts

def build_dataset(normal_csv, ransom_csv):
    dn = load_log(normal_csv) if os.path.exists(normal_csv) else pd.DataFrame()
    dr = load_log(ransom_csv) if os.path.exists(ransom_csv) else pd.DataFrame()

    fn = extract_features(dn); fn["label"]=0
    fr = extract_features(dr); fr["label"]=1
    data = pd.concat([fn, fr], ignore_index=True).sample(frac=1, random_state=42)
    return data

def train_and_save(data, out_csv="data/all_behaviors.csv", model_path="data/model.joblib"):
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    data.to_csv(out_csv, index=False)

    X = data[["created","modified","deleted","moved"]]
    y = data["label"]
    if len(data) < 10:
        print("Not enough data to train. Collect more logs.")
        return

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    clf = RandomForestClassifier(n_estimators=200, class_weight="balanced", random_state=42, n_jobs=-1)
    clf.fit(Xtr, ytr)

    ypred = clf.predict(Xte)
    print("Confusion matrix:\n", confusion_matrix(yte, ypred))
    print("\nReport:\n", classification_report(yte, ypred, digits=3))

    joblib.dump(clf, model_path)
    print(f"Saved model to {model_path} and dataset to {out_csv}")

if __name__ == "__main__":
    data = build_dataset("data/normal_logs.csv", "data/ransomware_logs.csv")
    train_and_save(data)