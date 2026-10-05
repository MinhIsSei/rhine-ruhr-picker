"""Build places.csv for the six cities.
Asian food/drink places come from the Google Places API (New): popular, with ratings.
Activities (museums, parks, cinemas, ...) come from OpenStreetMap (Overpass API, no key needed).
Setup:  set the environment variable GOOGLE_PLACES_KEY (never put the key in code).
Usage:  python fetch_places.py                  (top 60 food + 80 activity places per city)
        python fetch_places.py --max-calls 40   (hard cap on Google API calls, default 150)
        python fetch_places.py --dry-run        (only print how many Google calls would be made)
Output: places.csv (the previous one is saved as places.csv.bak)."""
import argparse, csv, json, os, shutil, sys, time, urllib.error, urllib.parse, urllib.request

CITIES = {"Bochum": "Bochum", "Dortmund": "Dortmund", "Duisburg": "Duisburg",
          "Essen": "Essen", "Dusseldorf": "Düsseldorf", "Cologne": "Köln"}  # key -> OSM/Google name
URL = "https://overpass-api.de/api/interpreter"
QUERY = """[out:json][timeout:180];
area["boundary"="administrative"]["admin_level"="6"]["name"="{name}"]->.a;
(
  nwr(area.a)["amenity"~"^(cinema|theatre|arts_centre)$"]["name"];
  nwr(area.a)["tourism"~"^(museum|zoo|aquarium|gallery|attraction|viewpoint|theme_park)$"]["name"];
  nwr(area.a)["leisure"~"^(park|garden|bowling_alley|escape_game|miniature_golf|water_park|ice_rink)$"]["name"];
);
out center tags;"""

# --- Google Places (New): text search per cuisine/drink query ---
GOOGLE_URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = ("places.id,places.displayName,places.location,places.rating,places.userRatingCount,"
          "places.priceLevel,places.primaryType,places.businessStatus,nextPageToken")
FOOD_QUERIES = ["Asian restaurant", "sushi", "ramen", "Chinese restaurant", "Vietnamese restaurant",
                "Thai restaurant", "Korean restaurant", "Indian restaurant", "bubble tea", "Asian cafe"]
WALK_QUERIES = ["riverside promenade", "walk along the river", "park", "walking trail", "lake walk"]
PAGES = 2            # 20 results per page
MIN_REVIEWS = 20     # drop places nobody has reviewed
GOOGLE_PRICE = {"PRICE_LEVEL_FREE": 0, "PRICE_LEVEL_INEXPENSIVE": 8, "PRICE_LEVEL_MODERATE": 15,
                "PRICE_LEVEL_EXPENSIVE": 30, "PRICE_LEVEL_VERY_EXPENSIVE": 50}

OUTDOOR_TOURISM = {"zoo", "viewpoint", "theme_park", "attraction"}
OUTDOOR_LEISURE = {"park", "garden", "miniature_golf"}
# Default price guess (EUR) per kind; editable later in places.csv or in the app
PRICE = {"restaurant": 15, "cafe": 8, "fast_food": 8, "biergarten": 15, "ice_cream": 4,
         "museum": 8, "zoo": 20, "aquarium": 20, "theme_park": 30, "cinema": 12,
         "theatre": 20, "bowling_alley": 10, "escape_game": 25, "water_park": 15,
         "ice_rink": 8, "gallery": 5, "arts_centre": 8}
RICH_KEYS = ["website", "phone", "opening_hours", "wheelchair", "addr:street", "email", "description"]
calls = 0
CACHE_DIR = ".cache"  # raw API answers; re-runs reuse them, so retries never cost extra Google calls

def cached(name, producer):
    path = os.path.join(CACHE_DIR, name + ".json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    data = producer()
    os.makedirs(CACHE_DIR, exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return data

def fetch(city_key, retries=4):
    data = urllib.parse.urlencode({"data": QUERY.format(name=CITIES[city_key])}).encode()
    for i in range(retries):
        try:
            req = urllib.request.Request(URL, data=data, headers={"User-Agent": "rhine-ruhr-picker"})
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.load(r)["elements"]
        except Exception as e:
            print(f"  error ({e}), retrying in {20 * (i + 1)}s...", file=sys.stderr)
            time.sleep(20 * (i + 1))
    raise RuntimeError(f"Could not fetch {city_key} from Overpass")

def parse(elements, city_key, top):
    seen, items = set(), []
    for el in elements:
        t = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if not t.get("name") or lat is None:
            continue
        kind = t.get("amenity") if t.get("amenity") else (t.get("tourism") or t.get("leisure"))
        key = (t["name"].lower(), round(lat, 3), round(lon, 3))
        if key in seen:
            continue
        seen.add(key)
        items.append(dict(
            name=t["name"], city=city_key, is_activity=1,
            kind=kind, lat=round(lat, 5), lon=round(lon, 5), price=PRICE.get(kind, 0), rating="",
            outdoor=int(t.get("tourism") in OUTDOOR_TOURISM or t.get("leisure") in OUTDOOR_LEISURE),
            _score=sum(k in t for k in RICH_KEYS)))
    out = sorted(items, key=lambda x: -x["_score"])[:top]  # most info on OSM = usually real, active venues
    for x in out:
        del x["_score"]
    return out

def google_search(key, query, max_calls):
    """Yield places for one text query (up to PAGES pages); stops when the call budget is used up."""
    global calls
    token = None
    for _ in range(PAGES):
        if calls >= max_calls:
            print("  call limit reached, stopping", file=sys.stderr)
            return
        body = {"textQuery": query, "pageSize": 20, "languageCode": "en"}
        if token:
            body["pageToken"] = token
        req = urllib.request.Request(GOOGLE_URL, data=json.dumps(body).encode(), headers={
            "Content-Type": "application/json", "X-Goog-Api-Key": key, "X-Goog-FieldMask": FIELDS})
        for attempt in range(6):  # flaky SSL on some networks: retry network errors, not API errors
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    res = json.load(r)
                break
            except urllib.error.HTTPError as e:
                raise SystemExit(f"Google API error {e.code}: {e.read().decode()[:300]}")
            except (urllib.error.URLError, OSError) as e:
                print(f"  network error ({e}), retry {attempt + 1}/6", file=sys.stderr)
                time.sleep(3 * (attempt + 1))
        else:
            raise SystemExit("Google API unreachable after 6 tries")
        calls += 1
        yield from res.get("places", [])
        token = res.get("nextPageToken")
        if not token:
            return

def food_kind(primary):
    p = primary or ""
    if "ice_cream" in p: return "ice_cream"
    if "fast_food" in p: return "fast_food"
    if any(w in p for w in ("cafe", "coffee", "tea", "bakery", "dessert")): return "cafe"
    return "restaurant"

def walk_kind(primary):
    p = primary or ""
    if "park" in p or "garden" in p: return "park"
    if "hiking" in p or "trail" in p: return "trail"
    return "attraction"

def fetch_walks(key, city_key, top, max_calls):
    """Outdoor walking spots (riverside promenades, parks, trails) from Google: free, outdoor, rated."""
    found = {}
    for q in WALK_QUERIES:
        places = cached(f"google_walk_{city_key}_{q.replace(' ', '_')}",
                        lambda: list(google_search(key, f"{q} in {CITIES[city_key]}, Germany", max_calls)))
        for p in places:
            if p.get("businessStatus", "OPERATIONAL") == "OPERATIONAL" and p.get("userRatingCount", 0) >= MIN_REVIEWS:
                found[p["id"]] = p
    rows = [dict(name=p["displayName"]["text"], city=city_key, is_activity=1, kind=walk_kind(p.get("primaryType")),
                 lat=round(p["location"]["latitude"], 5), lon=round(p["location"]["longitude"], 5), price=0,
                 rating=p.get("rating", ""), outdoor=1, _pop=p.get("userRatingCount", 0)) for p in found.values()]
    rows.sort(key=lambda x: -x["_pop"])
    for x in rows:
        del x["_pop"]
    return rows[:top]

def fetch_food(key, city_key, top, max_calls):
    found = {}
    for q in FOOD_QUERIES:
        places = cached(f"google_{city_key}_{q.replace(' ', '_')}",
                        lambda: list(google_search(key, f"{q} in {CITIES[city_key]}, Germany", max_calls)))
        for p in places:
            if p.get("businessStatus", "OPERATIONAL") != "OPERATIONAL" or p.get("userRatingCount", 0) < MIN_REVIEWS:
                continue
            found[p["id"]] = p
    rows = []
    for p in found.values():
        kind = food_kind(p.get("primaryType"))
        rows.append(dict(
            name=p["displayName"]["text"], city=city_key, is_activity=0, kind=kind,
            lat=round(p["location"]["latitude"], 5), lon=round(p["location"]["longitude"], 5),
            price=GOOGLE_PRICE.get(p.get("priceLevel"), PRICE[kind]), rating=p.get("rating", ""), outdoor=0,
            _pop=p.get("userRatingCount", 0)))
    rows.sort(key=lambda x: -x["_pop"])  # most reviewed = most popular
    for x in rows:
        del x["_pop"]
    return rows[:top]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=60, help="max Asian food/drink places per city")
    ap.add_argument("--top-walks", type=int, default=15, help="max Google outdoor walking spots per city")
    ap.add_argument("--top-activities", type=int, default=80, help="max activity places per city")
    ap.add_argument("--max-calls", type=int, default=150, help="hard cap on Google API calls")
    ap.add_argument("--keep-activities", action="store_true", help="skip Overpass, reuse activities from the current places.csv")
    ap.add_argument("--dry-run", action="store_true", help="print the max number of Google calls and exit")
    args = ap.parse_args()
    worst = len(CITIES) * (len(FOOD_QUERIES) + len(WALK_QUERIES)) * PAGES
    if args.dry_run:
        raise SystemExit(f"Up to {worst} Google calls (cap: {args.max_calls})")
    key = os.environ.get("GOOGLE_PLACES_KEY")
    if not key:
        raise SystemExit("Set the GOOGLE_PLACES_KEY environment variable first.")
    old = list(csv.DictReader(open("places.csv", encoding="utf-8"))) if os.path.exists("places.csv") else []
    rows = []
    for k in CITIES:
        print(f"Fetching {k} ... (Google calls so far: {calls})")
        rows += fetch_food(key, k, args.top, args.max_calls)
        try:
            if args.keep_activities:
                raise RuntimeError("--keep-activities")
            rows += parse(cached(f"osm_{k}", lambda: fetch(k)), k, args.top_activities)
        except RuntimeError as e:  # Overpass is often overloaded: keep this city's old activities
            keep = [r for r in old if r["city"] == k and r["is_activity"] == "1"]
            print(f"  {e}: keeping {len(keep)} activities from the existing places.csv", file=sys.stderr)
            rows += keep
        rows += fetch_walks(key, k, args.top_walks, args.max_calls)
        time.sleep(5)  # be polite to the Overpass servers
    seen, uniq = set(), []  # --keep-activities reloads old rows, so drop repeats
    for r in rows:
        if (r["name"].lower(), r["city"]) not in seen:
            seen.add((r["name"].lower(), r["city"]))
            uniq.append(r)
    rows = uniq
    cols = ["name", "city", "is_activity", "kind", "lat", "lon", "price", "rating", "outdoor"]
    if os.path.exists("places.csv"):
        shutil.copy("places.csv", "places.csv.bak")
    with open("places.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"Done: {len(rows)} places, {calls} Google calls -> places.csv")
