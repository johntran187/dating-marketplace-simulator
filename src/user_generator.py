import numpy as np
import pandas as pd

# lock in the random starting point so we get the same users every run
np.random.seed(42)

# change this one number if you want more or fewer users in the simulation
N_USERS = 5000

# each city has a weight (how likely a user lives there) and a density (how spread out it is)
CITIES = {
    'New York':     {'weight': 0.20, 'density': 'high'},
    'Los Angeles':  {'weight': 0.18, 'density': 'high'},
    'Chicago':      {'weight': 0.12, 'density': 'high'},
    'Houston':      {'weight': 0.10, 'density': 'medium'},
    'Phoenix':      {'weight': 0.08, 'density': 'medium'},
    'Philadelphia': {'weight': 0.08, 'density': 'medium'},
    'San Antonio':  {'weight': 0.08, 'density': 'low'},
    'Austin':       {'weight': 0.08, 'density': 'low'},
    'Seattle':      {'weight': 0.08, 'density': 'medium'},
}

# how far users are willing to travel, based on how dense their city is
# dense cities = short distances, spread-out cities = longer distances
MAX_DISTANCE_BY_DENSITY = {
    'high':   (5,  25),
    'medium': (10, 40),
    'low':    (20, 60),
}


def generate_gender(n):
    # pick a gender for each user — weighted so 60% are male, 35% female, 5% non-binary
    # this reflects the real skew seen on dating apps
    return np.random.choice(
        ['male', 'female', 'non-binary'],
        size=n,
        p=[0.60, 0.35, 0.05]
    )


def generate_age(n):
    # generate ages using a bell curve centered at 28 — most users are young adults
    # clip anything outside 18-55 so we don't get impossible ages
    ages = np.random.normal(loc=28, scale=7, size=n)
    ages = np.clip(ages, 18, 55)
    return ages.astype(int)


def generate_city_and_distance(n):
    # assign each user a city based on the weights above
    # then pick a random max travel distance based on how dense that city is
    city_names   = list(CITIES.keys())
    city_weights = [CITIES[c]['weight'] for c in city_names]

    cities = np.random.choice(city_names, size=n, p=city_weights)

    max_distances = []
    for city in cities:
        density       = CITIES[city]['density']
        low, high     = MAX_DISTANCE_BY_DENSITY[density]
        distance      = np.random.randint(low, high + 1)
        max_distances.append(distance)

    return cities, np.array(max_distances)


def generate_attractiveness(n):
    # score each user on a 1-10 scale using a bell curve centered at 5
    # most people are average, very few are at the extremes
    scores = np.random.normal(loc=5.0, scale=1.5, size=n)
    scores = np.clip(scores, 1.0, 10.0)
    return np.round(scores, 1)


def generate_pickiness(attractiveness_scores):
    # more attractive users tend to be pickier because they have more options
    # we add a little random noise so it's not a perfect rule — some attractive people are easygoing
    noise     = np.random.normal(loc=0, scale=0.15, size=len(attractiveness_scores))
    pickiness = (attractiveness_scores / 10.0) + noise
    pickiness = np.clip(pickiness, 0.0, 1.0)
    return np.round(pickiness, 2)


def generate_activity_level(n):
    # most users are casual — they open the app occasionally
    # a small number are obsessively active (power law / pareto distribution)
    # squeeze the raw values into a 0-1 range so they're usable as probabilities
    raw      = np.random.pareto(a=2.0, size=n)
    activity = raw / (raw + 3.0)
    activity = np.clip(activity, 0.01, 1.0)
    return np.round(activity, 2)


def generate_age_preferences(ages):
    # give each user a range of ages they're willing to date
    # the window is centered near their own age with a small random shift
    min_prefs = []
    max_prefs = []

    for age in ages:
        spread   = np.random.randint(5, 15)   # how wide the age window is
        offset   = np.random.randint(-3, 4)   # slight shift older or younger

        mid      = age + offset
        min_pref = max(18, mid - spread // 2)  # never go below 18
        max_pref = min(65, mid + spread // 2)  # never go above 65

        min_prefs.append(min_pref)
        max_prefs.append(max_pref)

    return np.array(min_prefs), np.array(max_prefs)


def generate_gender_pref(genders):
    # decide who each user wants to date, based on realistic orientation rates
    # non-binary users are open to everyone
    prefs = []
    for gender in genders:
        roll = np.random.random()  # random number between 0 and 1

        if gender == 'male':
            if roll < 0.90:
                prefs.append(['female'])
            elif roll < 0.96:
                prefs.append(['male'])
            else:
                prefs.append(['female', 'male', 'non-binary'])

        elif gender == 'female':
            if roll < 0.85:
                prefs.append(['male'])
            elif roll < 0.93:
                prefs.append(['female'])
            else:
                prefs.append(['male', 'female', 'non-binary'])

        else:
            prefs.append(['male', 'female', 'non-binary'])

    return prefs


def generate_join_day(n, simulation_days=30):
    # spread users across the simulation window — not everyone joins on day 1
    return np.random.randint(0, simulation_days, size=n)


def generate_users(n=N_USERS):
    print(f"Generating {n} users...")

    # generate each attribute separately
    user_ids  = np.arange(1, n + 1)
    genders   = generate_gender(n)
    ages      = generate_age(n)

    cities, max_distances = generate_city_and_distance(n)

    attractiveness = generate_attractiveness(n)
    pickiness      = generate_pickiness(attractiveness)
    activity_level = generate_activity_level(n)

    min_age_pref, max_age_pref = generate_age_preferences(ages)
    gender_pref = generate_gender_pref(genders)
    join_day    = generate_join_day(n)

    # pack everything into one table — one row per user, one column per attribute
    df = pd.DataFrame({
        'user_id':        user_ids,
        'gender':         genders,
        'age':            ages,
        'city':           cities,
        'attractiveness': attractiveness,
        'activity_level': activity_level,
        'pickiness':      pickiness,
        'min_age_pref':   min_age_pref,
        'max_age_pref':   max_age_pref,
        'gender_pref':    gender_pref,
        'max_distance':   max_distances,
        'join_day':       join_day,
    })

    print(f"Done! DataFrame shape: {df.shape}")
    return df


# only runs when you execute this file directly — not when another file imports it
if __name__ == '__main__':
    df = generate_users()

    print("\n--- First 5 rows ---")
    print(df.head())

    print("\n--- Summary statistics ---")
    print(df[['age', 'attractiveness', 'activity_level', 'pickiness']].describe())

    print("\n--- Gender split ---")
    print(df['gender'].value_counts(normalize=True).round(2))

    print("\n--- City distribution ---")
    print(df['city'].value_counts())

    df.to_csv('data/users.csv', index=False)
    print("\nSaved to data/users.csv")
