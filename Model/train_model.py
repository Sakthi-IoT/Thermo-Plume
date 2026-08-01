"""
THERMO-PLUME — Layer 1.5, Step 2: Train the TinyML Model
============================================================

WHAT THIS FILE DOES (in plain words):
--------------------------------------
This reads the training_data.csv file (made by generate_dataset.py) and
trains a small Decision Tree to predict air quality state from sensor
readings.

WHY A DECISION TREE (and not a big neural network)?
-----------------------------------------------------
The problem statement asks for "TinyML" running on a microcontroller
with less than 100mW of power and very little memory. A Decision Tree
is a perfect fit for this:
  - It's just a series of yes/no questions (e.g. "is CO2 > 900?")
  - It takes almost no memory to store (a few KB, sometimes even bytes)
  - It runs in microseconds — no matrix multiplication, no GPU needed
  - It can be converted DIRECTLY into plain C if/else code, which is
    exactly the format an ESP32 firmware would use

We deliberately LIMIT the tree's depth (max_depth) — a deeper tree
would be more "accurate" on paper but too big/slow for a real
microcontroller. This tradeoff (smaller = more deployable, even if
slightly less accurate) is exactly the kind of engineering decision
the problem statement is testing for.

HOW TO USE THIS FILE:
----------------------
    python3 train_model.py

This will:
  1. Load training_data.csv
  2. Split it into training data and testing data
  3. Train the decision tree
  4. Print accuracy and a report of how well it did per class
  5. Save the trained model to model.joblib
"""

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import joblib


# The sensor readings we'll use as INPUT features for the model.
# Note: voc_reported is the BUGGY sensor value (see edge_node.py) —
# we deliberately train on the buggy value here, WITHOUT calibration,
# so that later (Layer 3) we can prove the Calibration Agent improves
# real-world accuracy. This script is the "before calibration" baseline.
FEATURE_COLUMNS = ["pm25", "pm10", "co2", "humidity", "temperature", "voc_reported"]
LABEL_COLUMN = "label"


def train():
    # --- Step 1: load the dataset ---
    df = pd.read_csv("training_data.csv")
    print(f"Loaded {len(df)} rows from training_data.csv")

    X = df[FEATURE_COLUMNS]   # the inputs (sensor readings)
    y = df[LABEL_COLUMN]      # the correct answers (NORMAL / RISING_RISK / STAGNATION_PREDICTED)

    # --- Step 2: split into training data and testing data ---
    # We train on 80% of the data, and test on the other 20% the model
    # has NEVER seen, to check it actually learned patterns (not just
    # memorized the training data).
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Training on {len(X_train)} rows, testing on {len(X_test)} rows")

    # --- Step 3: train the model ---
    # max_depth=6 keeps this SMALL on purpose — this is our "TinyML" constraint.
    model = DecisionTreeClassifier(max_depth=6, random_state=42)
    model.fit(X_train, y_train)

    # --- Step 4: evaluate how good it is ---
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print(f"\nAccuracy on unseen test data: {acc * 100:.2f}%")
    print("\nDetailed report (per class):")
    print(classification_report(y_test, y_pred))

    print("Confusion matrix (rows = actual, columns = predicted):")
    labels_order = ["NORMAL", "RISING_RISK", "STAGNATION_PREDICTED"]
    cm = confusion_matrix(y_test, y_pred, labels=labels_order)
    print(f"{'':>22}", "  ".join(f"{l[:10]:>10}" for l in labels_order))
    for i, row in enumerate(cm):
        print(f"{labels_order[i]:>22}", "  ".join(f"{v:>10}" for v in row))

    # --- Step 5: check how "tiny" this model actually is ---
    print(f"\nTree depth: {model.get_depth()}")
    print(f"Number of decision nodes: {model.tree_.node_count}")

    # --- Step 6: save the trained model to a file ---
    joblib.dump(model, "model.joblib")
    print("\nSaved trained model to model.joblib")

    return model


if __name__ == "__main__":
    train()
