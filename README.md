# Rhine-Ruhr Picker

Learn what **you** actually care about when you can't decide where to eat or what to do with a friend in the Rhine-Ruhr area (Bochum, Dortmund, Duisburg, Essen, Düsseldorf, Cologne), travelling by regional train with a Deutschlandticket.

You log the places you were torn between and the one you picked. A **conditional logit** model (softmax over the options of each choice) learns the weight of each factor: travel time for you, travel time for your friend, the longer of the two trips, price, rating, whether your friend would like it, rain + outdoor, and so on. After ~30 logged choices it predicts which option you will pick.

The defaults assume you travel from **Bochum** and your friend from **Cologne**. Change `city_travel.csv` if your starting points differ.

## Files
| File | Purpose |
|---|---|
| `city_travel.csv` | Regional-train minutes, Hbf to Hbf, for you (`t_me`) and your friend (`t_friend`). **You must edit it (Step 2).** |
| `fetch_places.py` | Downloads real places from OpenStreetMap into `places.csv` |
| `places_sample.csv` | Fake sample places, used only until `places.csv` exists |
| `app.py` | Streamlit app to log your choices into `my_choices.csv` |
| `features.py`, `model.py` | Feature construction and the model (no need to edit) |
| `train.py` | Prints weights and cross-validated accuracy |
| `generate_synthetic.py` | Makes `synthetic_choices.csv` from a fake person with known weights, to check the code recovers them |

## Step 1: Install (once)
Install Python 3.10+ (on Windows, tick "Add Python to PATH"), then in a terminal inside this folder:
```
pip install -r requirements.txt
```

## Step 2: Fill in `city_travel.csv` (once, ~15 min)
The numbers shipped in the file are **rough estimates, not real timetables**. For each city, look up on bahn.de or in DB Navigator:
- `t_me`: minutes from your home Hbf (default Bochum) to that city's Hbf
- `t_friend`: minutes from your friend's Hbf (default Cologne) to that city's Hbf

Pick a typical departure time (e.g. Saturday 11:00) and **enable the local/regional-transport-only option** so ICE/IC trains are excluded, since the Deutschlandticket does not cover them. Check that no ICE/IC appears in the result. Keep the column names and the city names (`Dusseldorf`, `Cologne` without special characters).

## Step 3: Fetch real places (once, a few minutes, needs Internet)
```
python fetch_places.py
```
This writes `places.csv` with about 80 food and 80 activity places per city (those with the most info on OpenStreetMap). Use `--top 40` for a shorter list. If it fails or the server is busy, wait a few minutes and rerun.

Then open `places.csv` in a spreadsheet and:
- delete places you would never go to (a shorter list is faster to search)
- optionally fill in `rating` (OpenStreetMap has none). Blank means 4.0 in the app, and you can edit it per choice
- `price` is a rough default per kind of place (EUR), also editable in the app

## Step 4: Use the app whenever you are torn
```
streamlit run app.py
```
1. Tick "Rainy" if it is raining.
2. Pick 2-5 places you are torn between.
3. For each one, check price and rating, rate "Would your friend like it? (1-5)", tick outdoor / open.
4. Select what you **actually** choose and press "Save choice".

Everything is appended to `my_choices.csv` automatically; you never create that file yourself. Clicked the wrong thing? Use "Delete last choice" in the second tab.

## Step 5: Look at the results
- After **10 choices**: the "Data & weights" tab shows a weight chart.
- After **30 choices**: the "Choose" tab starts predicting your pick. Check whether it is right.
- Or from the command line: `python train.py` (uses `my_choices.csv`)

## Tips for useful data
- Log while you are **really torn**, before deciding, not afterwards.
- Record what you actually picked, not what you think you should pick.
- Rate `friend_fit` by honest gut feeling.
- Skip choices that were forced (e.g. only one place was open).

## Verify the code with synthetic data
```
python generate_synthetic.py
python train.py synthetic_choices.csv
```
The output compares the learned weights with the true ones used to generate the data. Never mix `synthetic_choices.csv` with your real `my_choices.csv`.

## Limitations
- Travel time inside a city is estimated from straight-line distance, which is good enough for comparing places but not exact.
- Not modelled yet: last train home, number of changes, post-trip satisfaction.
- The model describes your own habits; with few choices, correlated features (`t_me`, `t_friend`, `t_max`, `t_diff`) share weight between them, so read the overall trend rather than single numbers.
- Opening hours are not parsed from OpenStreetMap: you tick "open" yourself.
