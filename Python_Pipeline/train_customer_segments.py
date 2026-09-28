"""Authoritative clean-RFM KMeans pipeline with cluster profiling."""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "phase1-v1"
OUT = ROOT / "Models" / "integrated"
VERSION = "rfm-kmeans-v4"


def features(rfm):
    return pd.DataFrame({"Recency_Days": np.log1p(rfm.Recency_Days.clip(lower=0)),
                         "Frequency": np.log1p(rfm.Frequency.clip(lower=0)),
                         "Monetary": np.log1p(rfm.Monetary.clip(lower=0))})


def business_labels(profiles):
    remaining = set(profiles.index)
    at_risk = profiles.Recency_Days.idxmax()
    remaining.remove(at_risk)
    high_value = profiles.loc[list(remaining)].Monetary.idxmax()
    remaining.remove(high_value)
    labels = {int(at_risk): "At Risk", int(high_value): "High Value"}
    if remaining:
        occasional = profiles.loc[list(remaining)].Frequency.idxmin()
        labels[int(occasional)] = "Occasional"
        remaining.remove(occasional)
    for cluster in remaining:
        # Frequency alone would call a 152-day absent cluster "Engaged".
        recency = profiles.loc[cluster, "Recency_Days"]
        if recency > 90:
            labels[int(cluster)] = "Cooling"
        elif profiles.loc[cluster, "Frequency"] >= profiles.Frequency.median():
            labels[int(cluster)] = "Engaged"
        else:
            labels[int(cluster)] = "Developing"
    return labels


def train():
    OUT.mkdir(parents=True, exist_ok=True)
    rfm = pd.read_parquet(DATA / "customer_rfm.parquet")
    values = features(rfm)
    scaler = StandardScaler().fit(values)
    scaled = scaler.transform(values)
    sample_index = np.random.default_rng(42).choice(len(rfm), size=min(4000, len(rfm)), replace=False)
    candidates = []
    for k in range(3, 7):
        trial = KMeans(n_clusters=k, random_state=42, n_init=10).fit(scaled)
        score = silhouette_score(scaled[sample_index], trial.labels_[sample_index])
        candidates.append((k, score, trial))
    k, silhouette, model = max(candidates, key=lambda entry: entry[1])
    rfm["Cluster"] = model.labels_
    profiles = rfm.groupby("Cluster").agg(Size=("Customer_ID", "size"),
        Recency_Days=("Recency_Days", "mean"), Frequency=("Frequency", "mean"),
        Monetary=("Monetary", "mean"))
    labels = business_labels(profiles)
    rfm["Segment"] = rfm.Cluster.map(labels)
    rfm.to_parquet(DATA / "customer_segments.parquet", index=False)
    profiles["Segment"] = profiles.index.map(labels)
    profiles.to_csv(DATA / "customer_cluster_profiles.csv")
    joblib.dump({"model": model, "scaler": scaler, "labels": labels, "version": VERSION,
                 "dataset_version": "phase1-v1-clean-v3", "features": list(values.columns)},
                OUT / "customer_rfm_kmeans.joblib")
    metrics = {"version": VERSION, "dataset_version": "phase1-v1-clean-v3", "customers": len(rfm),
               "selected_k": k, "silhouette_sample_size": len(sample_index), "silhouette": silhouette,
               "candidates": [{"k": candidate, "silhouette": score} for candidate, score, _ in candidates],
               "profiles": json.loads(profiles.reset_index().to_json(orient="records"))}
    (OUT / "customer_segment_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({key: metrics[key] for key in ("customers", "selected_k", "silhouette")}, indent=2))


if __name__ == "__main__":
    train()
