"""Create SYNTHETIC data from a fake person with known weights, to verify the code works.
The Hbf-to-Hbf train times below are rough ESTIMATES; real data should use city_travel.csv."""
import json
import numpy as np
import pandas as pd

rng = np.random.default_rng(0)
CITIES = ["Bochum", "Dortmund", "Duisburg", "Essen", "Dusseldorf", "Cologne"]
T_ME     = dict(Bochum=0, Dortmund=20, Duisburg=30, Essen=15, Dusseldorf=45, Cologne=75)
T_FRIEND = dict(Bochum=75, Dortmund=90, Duisburg=55, Essen=65, Dusseldorf=35, Cologne=0)

places = []
for city in CITIES:
    for i in range(6):
        act = int(i >= 3)  # 0 = food, 1 = activity
        places.append(dict(
            name=f"{'Food' if act == 0 else 'Activity'}_{city}_{i}", city=city, is_activity=act,
            price=float(rng.choice([0, 10, 15, 25, 40, 60, 80]) if act else rng.choice([8, 12, 18, 25, 35])),
            rating=round(float(rng.uniform(3.6, 4.8)), 1),
            outdoor=int(act == 1 and rng.random() < 0.5), walk=int(rng.integers(5, 25))))

W = dict(t_me=-0.03, t_friend=-0.025, t_max=-0.04, t_diff=-0.02, price=-0.03, rating=1.2,
         friend_fit=0.7, is_activity=0.0, outdoor=0.0, rain_outdoor=-1.5, is_open=3.0)
json.dump(W, open("true_weights.json", "w"), indent=1)

rows = []
for cid in range(1, 81):
    k = int(rng.integers(2, 5))
    rain = int(rng.random() < 0.4)
    feats = []
    for ci in rng.choice(len(places), size=k, replace=False):
        p = places[ci]
        tm = T_ME[p["city"]] + p["walk"]
        tf = T_FRIEND[p["city"]] + p["walk"]
        f = dict(choice_id=cid, option=p["name"], city=p["city"], t_me=tm, t_friend=tf,
                 t_max=max(tm, tf), t_diff=abs(tm - tf), price=p["price"], rating=p["rating"],
                 friend_fit=int(rng.integers(1, 6)), is_activity=p["is_activity"], outdoor=p["outdoor"],
                 rain_outdoor=rain * p["outdoor"], is_open=int(rng.random() < 0.9))
        f["u"] = sum(W[c] * f[c] for c in W) + rng.gumbel()
        feats.append(f)
    best = int(np.argmax([f["u"] for f in feats]))
    for j, f in enumerate(feats):
        f["chosen"] = int(j == best)
        del f["u"]
        rows.append(f)
pd.DataFrame(rows).to_csv("synthetic_choices.csv", index=False)
print(f"Wrote synthetic_choices.csv: {len(rows)} rows, {rows[-1]['choice_id']} choices")
