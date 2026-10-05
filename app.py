import os
import pandas as pd
import streamlit as st
import model
import storage
from features import build_rows

LOG = "my_choices.csv"
MIN_TO_SUGGEST = 10   # suggestions start here; treated as low-confidence until MIN_CONFIDENT
MIN_CONFIDENT = 30

st.set_page_config(page_title="Rhine-Ruhr Picker", layout="wide")

@st.cache_data
def load_places():
    path = "places.csv" if os.path.exists("places.csv") else "places_sample.csv"
    df = pd.read_csv(path).fillna({"rating": 0, "price": 0, "kind": ""})
    return df.reset_index(drop=True), path

@st.cache_data
def load_travel():
    return pd.read_csv("city_travel.csv").set_index("city")

@st.cache_resource
def fit_cached(mtime):
    groups, names, mean, std = model.load(LOG)
    return groups, names, mean, std, model.fit(groups)

if "synced" not in st.session_state:  # on Streamlit Cloud: load the saved choices from the private data repo
    storage.pull(LOG)
    if not os.path.exists("places.csv"):  # not in the public repo: fetch it from the private data repo
        storage.pull("places.csv")
        load_places.clear()
    st.session_state["synced"] = True

def n_choices():
    return pd.read_csv(LOG)["choice_id"].nunique() if os.path.exists(LOG) else 0

def save_choice(rows):
    pick = st.session_state["pick"]
    rows = rows.copy()
    rows["choice_id"] = n_choices() + 1
    rows["chosen"] = (rows["option"] == pick).astype(int)
    rows.to_csv(LOG, mode="a", header=not os.path.exists(LOG), index=False)
    storage.push(LOG)
    st.session_state["sel"] = []
    st.session_state["saved_msg"] = f"Saved choice #{rows['choice_id'].iloc[0]}: {pick}"

places, places_path = load_places()
travel = load_travel()
tab1, tab2 = st.tabs(["Choose", "Data & weights"])

with tab1:
    if places_path == "places_sample.csv":
        st.warning("Using the sample list (places_sample.csv). Run fetch_places.py to get real places.")
    if "saved_msg" in st.session_state:
        st.success(st.session_state.pop("saved_msg"))
    rain = st.checkbox("Rainy / bad weather")
    label = lambda i: f"{places.name[i]} · {places.city[i]} · {'activity' if places.is_activity[i] else 'food'}"
    sel = st.multiselect("Pick 2-5 places you are torn between (type to search)", list(places.index),
                         format_func=label, max_selections=5, key="sel")
    if len(sel) >= 2:
        cands = []
        for i in sel:
            r = places.loc[i]
            st.markdown(f"**{r['name']}**: {r.city} ({'activity' if r.is_activity else 'food'})")
            c1, c2, c3, c4, c5 = st.columns(5)
            price = c1.number_input("Price (EUR)", 0.0, 500.0, float(r.price), key=f"price{i}")
            rating = c2.number_input("Rating", 0.0, 5.0, float(r.rating) or 4.0, 0.1, key=f"rating{i}")
            friend_fit = c3.slider("Would your friend like it? (1-5)", 1, 5, 3, key=f"fit{i}")
            outdoor = c4.checkbox("Outdoor", bool(r.outdoor), key=f"out{i}")
            is_open = c5.checkbox("Open when you go", True, key=f"open{i}")
            cands.append(dict(name=r["name"], city=r.city, is_activity=r.is_activity, lat=r.lat, lon=r.lon,
                              price=price, rating=rating, friend_fit=friend_fit,
                              outdoor=outdoor, is_open=is_open))
        rows = build_rows(cands, travel, rain)
        if rows["option"].duplicated().any():
            st.error("Two places have the same name; remove one of them.")
            st.stop()
        st.dataframe(rows[["option", "t_me", "t_friend", "t_max", "t_diff"]].rename(columns={
            "t_me": "min from you", "t_friend": "min from friend",
            "t_max": "longest trip", "t_diff": "difference"}), hide_index=True)
        if n_choices() >= MIN_TO_SUGGEST:
            groups, names, mean, std, w = fit_cached(os.path.getmtime(LOG))
            p = model.predict(w, model.featurize(rows, names, mean, std))
            st.info("The model thinks you will pick: " + " · ".join(
                f"{n} ({x:.0%})" for n, x in sorted(zip(rows.option, p), key=lambda t: -t[1])))
            if n_choices() < MIN_CONFIDENT:
                st.caption(f"Early guess: only {n_choices()} choices so far, so it is still noisy "
                           f"(more reliable after {MIN_CONFIDENT}).")
        else:
            st.caption(f"The model starts suggesting after {MIN_TO_SUGGEST} choices (you have {n_choices()}).")
        st.radio("What I actually choose:", list(rows.option), key="pick", index=None)
        st.button("Save choice", on_click=save_choice, args=(rows,),
                  disabled=st.session_state.get("pick") is None)

with tab2:
    n = n_choices()
    st.write(f"**{n}** choices recorded in `{LOG}`.")
    if n:
        if st.button("Delete last choice (if you clicked by mistake)"):
            df = pd.read_csv(LOG)
            df = df[df.choice_id != df.choice_id.max()]
            df.to_csv(LOG, index=False) if len(df) else os.remove(LOG)
            storage.push(LOG)
            st.rerun()
        st.download_button("Download CSV", open(LOG, "rb").read(), LOG)
    if n >= 10:
        groups, names, mean, std, w = fit_cached(os.path.getmtime(LOG))
        st.subheader("Weights (standardized; positive = you like it more)")
        st.bar_chart(pd.Series(w, index=names).sort_values())
        if n >= 20:
            acc, base = model.cross_validate(groups)
            st.write(f"Cross-validated accuracy: **{acc:.0%}** (random guessing: {base:.0%})")
        if n < MIN_CONFIDENT:
            st.caption("Below ~30 choices the weights are still very noisy.")
    else:
        st.caption("At least 10 choices are needed before weights are shown.")
