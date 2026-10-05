"""Usage: python train.py [csv_path]   (default: my_choices.csv)"""
import json, os, sys
import numpy as np
from model import load, fit, cross_validate

path = sys.argv[1] if len(sys.argv) > 1 else "my_choices.csv"
groups, names, mean, std = load(path)
print(f"{len(groups)} choices, {len(names)} features\n")
if len(groups) < 30:
    print("Warning: with fewer than ~30 choices the weights are still very noisy.\n")

acc, base = cross_validate(groups)
print(f"Cross-validated top-1 accuracy: {acc:.0%}  (random guessing: {base:.0%})\n")

w = fit(groups)
# Only for the synthetic file: compare with the weights used to generate it
true = {}
if os.path.basename(path) == "synthetic_choices.csv" and os.path.exists("true_weights.json"):
    true = json.load(open("true_weights.json"))
print("Weights (standardized, comparable across features; positive = you like it more):")
for i in np.argsort(-np.abs(w)):
    note = ""
    if names[i] in true:
        note = f"   | true weight x std: {true[names[i]] * std[names[i]]:+.2f}"
    print(f"  {names[i]:<22}{w[i]:+.2f}{note}")
np.save("weights.npy", w)
