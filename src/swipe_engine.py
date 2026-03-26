import numpy as np
import pandas as pd
from user_generator import generate_users

np.random.seed(42)

# simulation settings
SIMULATION_DAYS = 30
QUEUE_SIZE      = 100  # how many profiles each active user sees per day
                       # raised from 40 — real tinder/hinge users scroll 100-200+ profiles/day
                       # more exposure = more mutual matches = realistic 2-4% match rate
RIGHT_SWIPE     = 1
LEFT_SWIPE      = 0


def sigmoid(x):
    # converts any number into a probability between 0 and 1
    # negative numbers come out close to 0, positive numbers come out close to 1
    return 1 / (1 + np.exp(-x))


def get_active_users(users_df, day):
    # only include users who have joined by today
    # then each user rolls against their activity level to decide if they open the app
    joined    = users_df[users_df['join_day'] <= day]
    rolls     = np.random.random(size=len(joined))
    is_active = rolls < joined['activity_level'].values
    return joined[is_active].copy()


def build_candidate_queue(swiper, all_users, already_swiped_ids, day):
    # build a list of profiles this user can swipe on today
    # filter out: people not yet joined, themselves, already seen, wrong gender, wrong age
    pool = all_users[all_users['join_day'] <= day].copy()

    # remove the swiper from their own queue
    pool = pool[pool['user_id'] != swiper['user_id']]

    # remove anyone this user has already swiped on before
    pool = pool[~pool['user_id'].isin(already_swiped_ids)]

    # only show profiles that match this user's gender preference
    gender_pref = swiper['gender_pref']
    pool = pool[pool['gender'].isin(gender_pref)]

    # only show profiles within this user's age preference
    pool = pool[
        (pool['age'] >= swiper['min_age_pref']) &
        (pool['age'] <= swiper['max_age_pref'])
    ]

    if len(pool) == 0:
        return pool

    # randomly pick up to QUEUE_SIZE profiles from what's left
    n = min(QUEUE_SIZE, len(pool))
    return pool.sample(n=n)


def swipe_probability(swiper, candidate, swipe_number_in_session):
    # calculate how likely this user is to swipe right on this candidate
    # main factor: how attractive is the candidate compared to how picky the swiper is
    # bonus factor: the further into the session, the slightly less picky the swiper gets
    # we subtract 1.5 from the raw score to push the overall right swipe rate down to ~20-30%
    # (real tinder data: men ~14%, women ~46%, blended average ~25-30%)
    pickiness_threshold = swiper['pickiness'] * 10
    attractiveness_gap  = candidate['attractiveness'] - pickiness_threshold
    fatigue_bonus       = 0.02 * swipe_number_in_session

    raw_score   = attractiveness_gap + fatigue_bonus - 2.0
    # increased bias from -1.5 to -2.0 to compensate for the larger queue size
    # keeps right swipe rate near the real-world blended average of ~25%
    probability = sigmoid(raw_score)

    return probability


def simulate_day(users_df, day, swiped_history):
    # run one full day of swiping for all active users
    # swiped_history carries over between days so nobody sees the same profile twice
    daily_swipes = []
    active_users = get_active_users(users_df, day)

    for _, swiper in active_users.iterrows():
        swiper_id      = swiper['user_id']
        already_swiped = swiped_history.get(swiper_id, set())

        queue = build_candidate_queue(swiper, users_df, already_swiped, day)

        if len(queue) == 0:
            continue  # no profiles available for this user today, skip them

        for swipe_num, (_, candidate) in enumerate(queue.iterrows()):
            prob      = swipe_probability(swiper, candidate, swipe_num)
            direction = RIGHT_SWIPE if np.random.random() < prob else LEFT_SWIPE

            # log this swipe
            daily_swipes.append({
                'day':          day,
                'swiper_id':    swiper_id,
                'candidate_id': candidate['user_id'],
                'direction':    direction,
                'probability':  round(prob, 3),
            })

            # remember this profile so it won't show up again
            already_swiped.add(candidate['user_id'])

        swiped_history[swiper_id] = already_swiped

    return daily_swipes


def run_simulation(users_df, days=SIMULATION_DAYS):
    # loop through every day and collect all swipes into one big list
    # swiped_history lives outside the loop so it builds up across all 30 days
    all_swipes     = []
    swiped_history = {}

    for day in range(days):
        if day % 5 == 0:
            print(f"  Simulating day {day}...")  # progress update every 5 days

        daily_swipes = simulate_day(users_df, day, swiped_history)
        all_swipes.extend(daily_swipes)

    swipe_log = pd.DataFrame(all_swipes)
    print(f"Simulation complete. Total swipes: {len(swipe_log):,}")
    return swipe_log


def find_matches(swipe_log):
    # a match happens when user a swiped right on user b AND user b swiped right on user a
    # we find these by joining the right-swipes table against itself, flipped
    rights = swipe_log[swipe_log['direction'] == RIGHT_SWIPE][['swiper_id', 'candidate_id', 'day']]

    # merge the table with itself swapped — rows that join are mutual right swipes
    matches = rights.merge(
        rights,
        left_on=['swiper_id',    'candidate_id'],
        right_on=['candidate_id', 'swiper_id'],
        suffixes=('_a', '_b')
    )

    # each match shows up twice (a→b and b→a) — keep only one copy of each pair
    matches = matches[matches['swiper_id_a'] < matches['swiper_id_b']].copy()

    # the match is official on whichever day the second person swiped
    matches['match_day'] = matches[['day_a', 'day_b']].max(axis=1)

    matches = matches[['swiper_id_a', 'swiper_id_b', 'match_day']].copy()
    matches.columns = ['user_a', 'user_b', 'match_day']
    matches = matches.reset_index(drop=True)

    print(f"Total matches found: {len(matches):,}")
    return matches


# only runs when you execute this file directly
if __name__ == '__main__':
    print("Generating users...")
    users_df = generate_users()

    print(f"\nRunning {SIMULATION_DAYS}-day simulation...")
    swipe_log = run_simulation(users_df)

    print("\nFinding matches...")
    matches = find_matches(swipe_log)

    total_swipes     = len(swipe_log)
    right_swipes     = (swipe_log['direction'] == RIGHT_SWIPE).sum()
    right_swipe_rate = right_swipes / total_swipes

    print(f"\n--- Simulation Stats ---")
    print(f"Total swipes:       {total_swipes:,}")
    print(f"Right swipes:       {right_swipes:,}")
    print(f"Right swipe rate:   {right_swipe_rate:.1%}")
    print(f"Total matches:      {len(matches):,}")
    print(f"Match rate:         {len(matches) / right_swipes:.1%} of right swipes led to a match")

    swipe_log.to_csv('data/swipe_log.csv', index=False)
    matches.to_csv('data/matches.csv', index=False)
    print("\nSaved swipe_log.csv and matches.csv to data/")
