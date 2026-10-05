"""Feature construction for the options you are currently torn between (used by the app)."""
import math
import pandas as pd

# Main station (Hbf) coordinates; double-check on a map if you need more precision
HBF = {
    "Bochum": (51.4786, 7.2236), "Dortmund": (51.5178, 7.4593),
    "Duisburg": (51.4297, 6.7753), "Essen": (51.4513, 7.0143),
    "Dusseldorf": (51.2201, 6.7942), "Cologne": (50.9430, 6.9589),
}

def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))

def local_minutes(lat, lon, city):
    """Rough minutes from the city's Hbf to the place (ESTIMATE).
    Up to 1.5 km of real street distance: walk at 4.5 km/h.
    Farther: 8 min waiting + tram/bus/U-Bahn at ~15 km/h on average."""
    d = haversine_km(*HBF[city], lat, lon) * 1.3  # 1.3 = detour factor
    return round(d / 4.5 * 60) if d <= 1.5 else round(8 + d / 15 * 60)

def build_rows(cands, travel, rain):
    """cands: list of dicts with keys name, city, is_activity, lat, lon, price, rating,
    outdoor, friend_fit, is_open.
    travel: DataFrame indexed by city with columns t_me, t_friend (regional-train minutes, Hbf to Hbf)."""
    rows = []
    for c in cands:
        local = local_minutes(c["lat"], c["lon"], c["city"])
        t_me = int(travel.loc[c["city"], "t_me"]) + local
        t_friend = int(travel.loc[c["city"], "t_friend"]) + local
        rows.append(dict(
            choice_id=0, option=c["name"], city=c["city"],
            t_me=t_me, t_friend=t_friend, t_max=max(t_me, t_friend), t_diff=abs(t_me - t_friend),
            price=float(c["price"]), rating=float(c["rating"]), friend_fit=int(c["friend_fit"]),
            is_activity=int(c["is_activity"]), outdoor=int(c["outdoor"]),
            rain_outdoor=int(rain) * int(c["outdoor"]),
            is_open=int(c["is_open"]), chosen=0))
    return pd.DataFrame(rows)
