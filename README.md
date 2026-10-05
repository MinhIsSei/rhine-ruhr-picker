# Rhine-Ruhr Picker

A Streamlit app that learns what **I** care about when I can't decide where to eat or what to do with a friend in the Rhine-Ruhr area (Bochum, Dortmund, Duisburg, Essen, Düsseldorf, Cologne), travelling by regional train with a Deutschlandticket.

I log the places I was torn between and the one I picked. A **conditional logit** model (softmax over the options of each choice) learns the weight of each factor, then predicts which option I will pick next.

**Live demo:** https://rhine-ruhr-picker.streamlit.app/


[Choose tab](docs/choose.png)
[Weights](docs/weights.png)


## What it does
- Compares 2-5 places side by side with estimated travel time for me and for my friend, price, rating, outdoor / rain and opening status.
- Fits the model on my own logged choices and shows predicted pick probabilities (from 10 choices; flagged as an early guess until 30).
- Shows the learned weights and a cross-validated accuracy against random guessing (from 20 choices).
- Works on a phone: deployed on Streamlit Community Cloud, with choices stored in a private GitHub repo so they survive restarts.

## How it works
- **Model** (`model.py`): conditional logit with L2 regularisation, fitted with `scipy.optimize` (L-BFGS-B). Features are standardised; city is one-hot encoded. Accuracy is estimated with k-fold cross-validation (top-1 accuracy vs. `1 / number of options`).
- **Features** (`features.py`): travel time = regional-train minutes (Hbf to Hbf, from `city_travel.csv`) + an estimate of the local trip from straight-line distance. Also the longer of both trips and the difference between them, price, rating, "would my friend like it" (1-5), outdoor, rain x outdoor, is open.
- **Data** (`fetch_places.py`): Asian restaurants and cafes come from the **Google Places API (New)** (ratings, popularity); museums, parks, cinemas and other activities come from **OpenStreetMap** (Overpass API). Raw API answers are cached in `.cache/`, so re-runs cost no extra API calls, and the script has a hard cap on Google calls.
- **Storage** (`storage.py`): optional. If a `[github]` secret is configured, the choice log (and `places.csv`) is read from and written to a private GitHub repo through the contents API. Without it, everything stays in local files.
- **Synthetic check** (`generate_synthetic.py`, `train.py`): simulates a person with known weights and checks that the code recovers them.

## Files
| File | Purpose |
|---|---|
| `app.py` | Streamlit app to log choices and see predictions and weights |
| `features.py`, `model.py` | Feature construction and the conditional logit model |
| `storage.py` | Optional persistence in a private GitHub repo (for cloud deployment) |
| `fetch_places.py` | Builds `places.csv` from Google Places and OpenStreetMap |
| `city_travel.csv` | Regional-train minutes, Hbf to Hbf, for me (`t_me`) and my friend (`t_friend`) |
| `places_sample.csv` | Fake sample places, used when `places.csv` does not exist |
| `train.py` | Prints weights and cross-validated accuracy from the command line |
| `generate_synthetic.py` | Creates `synthetic_choices.csv` from a fake person with known weights |

`places.csv` and `my_choices.csv` are **not** in this repository (third-party data terms and personal data). You create them yourself, see below.

## Run it locally
Python 3.10+ is required.
```
pip install -r requirements.txt
python -m streamlit run app.py
```
Without `places.csv` the app shows the fake sample places, which is enough to try the interface.

### 1. Set your starting points (`city_travel.csv`)
The numbers shipped in the file are **rough estimates, not real timetables**. The defaults assume I travel from **Bochum** and my friend from **Cologne**. For each city, look up on bahn.de or in DB Navigator:
- `t_me`: minutes from your home Hbf to that city's Hbf
- `t_friend`: minutes from your friend's Hbf to that city's Hbf

Use a typical departure time and the **local/regional-transport-only** option (the Deutschlandticket does not cover ICE/IC). Keep the column names and city names (`Dusseldorf`, `Cologne` without special characters).

### 2. Fetch real places (optional)
Create a Google Maps Platform API key with **Places API (New)** enabled (restrict the key to that API and set a budget alert), then set it as an environment variable. Never put the key in code.
```
setx GOOGLE_PLACES_KEY "your-key"        # Windows, then reopen the terminal
python fetch_places.py --dry-run         # shows the maximum number of Google calls
python fetch_places.py                   # writes places.csv (previous one saved as places.csv.bak)
```
Useful options: `--top` (Asian food/drink places per city, default 60), `--top-walks` (outdoor walking spots per city), `--top-activities`, `--max-calls` (hard cap on Google calls), `--keep-activities` (skip Overpass, which is often overloaded, and reuse the activities already in `places.csv`).

Then open `places.csv` and delete places you would never go to. `price` is a rough default per kind of place and can be edited in the app.

### 3. Use the app whenever you are torn
1. Tick "Rainy" if it is raining.
2. Pick 2-5 places you are torn between.
3. For each one, check price and rating, rate "Would your friend like it? (1-5)", tick outdoor / open.
4. Select what you **actually** choose and press "Save choice".

Everything is appended to `my_choices.csv`. Clicked the wrong thing? Use "Delete last choice" in the second tab. From the command line: `python train.py`.

### Tips for useful data
- Log while you are **really torn**, before deciding, not afterwards.
- Record what you actually picked, not what you think you should pick.
- Rate `friend_fit` by honest gut feeling.
- Skip choices that were forced (e.g. only one place was open).

## Deploy on Streamlit Community Cloud
1. Push this repository to GitHub.
2. Create a **private** repository for your data (e.g. `rhine-ruhr-data`) containing `my_choices.csv` and, optionally, your `places.csv`.
3. Create a fine-grained token limited to that data repo with **Contents: read and write**.
4. In Streamlit Cloud, deploy `app.py` and add this to **Secrets**:
   ```
   [github]
   token = "github_pat_..."
   repo = "your-name/rhine-ruhr-data"
   ```

## Verify the code with synthetic data
```
python generate_synthetic.py
python train.py synthetic_choices.csv
```
The output compares the learned weights with the true ones used to generate the data. Never mix `synthetic_choices.csv` with your real `my_choices.csv`.

## Limitations
- Travel time inside a city is estimated from straight-line distance: good enough for comparing places, not exact.
- Not modelled yet: last train home, number of changes, post-trip satisfaction.
- The model describes one person's habits. With few choices, correlated features (`t_me`, `t_friend`, `t_max`, `t_diff`) share weight between them, so read the overall trend rather than single numbers.
- Opening hours are not parsed: you tick "open" yourself.
- The "Asian food" focus is a personal choice, set by the queries in `fetch_places.py`; change `FOOD_QUERIES` to fetch other kinds of places.

## Data sources
- Places and ratings: Google Places API (not redistributed in this repository).
- Activities: © OpenStreetMap contributors, available under the Open Database License (ODbL).
