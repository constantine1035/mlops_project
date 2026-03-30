import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
import joblib


def load_dataset() -> tuple[pd.DataFrame, pd.Series]:
    """
    Load the classic Wine dataset from scikit‑learn and build a binary
    classification target. The original dataset contains three classes
    (0, 1, 2). Для демонстрации положительным классом считается класс 2,
    остальные метки составляют отрицательный класс.
    Returns a tuple (X, y) where X is a DataFrame of features and y is a
    Series of binary targets.
    """
    from sklearn.datasets import load_wine

    data = load_wine(as_frame=True)
    df = data.frame.copy()
    # Target is positive if class == 2 (the third class)
    df["target"] = (df["target"] == 2).astype(int)
    X = df.drop(columns=["target"])
    y = df["target"]
    return X, y


def train_model() -> float:
    """
    Train a logistic regression classifier on the wine dataset and
    persist the model and scaler to disk. Returns the validation accuracy.
    """
    X, y = load_dataset()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X_train_scaled, y_train)
    y_pred = clf.predict(X_test_scaled)
    acc = accuracy_score(y_test, y_pred)
    # Directory to store model artifacts; can be overridden via environment variable
    model_dir = os.environ.get("MODEL_DIR", "model")
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump({"model": clf, "scaler": scaler}, os.path.join(model_dir, "model.joblib"))
    with open(os.path.join(model_dir, "metrics.txt"), "w", encoding="utf-8") as f:
        f.write(f"accuracy: {acc}\n")
    return acc


if __name__ == "__main__":
    accuracy = train_model()
    print(f"Model trained. Validation accuracy: {accuracy:.4f}")