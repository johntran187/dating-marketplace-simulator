import numpy as np
import pandas as pd
from user_generator import generate_users
from swipe_engine import find_matches
from conversation_engine import (
    initiate_conversations, advance_conversations,
    initialize_frustration, update_frustration_from_swipes,
    update_frustration_from_conversations, get_churned_users
)

np.random.seed(42)


# all policy settings live here — everything is off by default
def default_policy_config():
    return {
        'swipe_cap_enabled':        False,
        'max_right_swipes_per_day': 25,

        'elo_enabled':    False,
        'elo_strictness': 200,

        'ladies_first_enabled': False,
        'message_window_days':  1,

        'boost_enabled':     False,
        'boost_percentage':  0.05,
        'boost_multiplier':  3,

        'nudge_enabled':        False,
        'nudge_inactive_days':  2,
        'nudge_survival_boost': 0.20,
    }


# give every user a starting elo score of 1500 (the chess default)
def initialize_elo(users_df):
    return {uid: 1500 for uid in users_df['user_id']}


# update the candidate's elo score based on whether the swiper liked them or not
# a right swipe counts as a "win" for the candidate, a left swipe counts as a "loss"
def update_elo(elo_scores, swiper_id, candidate_id, direction, k=16):
    from swipe_engine import RIGHT_SWIPE
    swiper_elo    = elo_scores.get(swiper_id,    1500)
    candidate_elo = elo_scores.get(candidate_id, 1500)
    expected      = 1 / (1 + 10 ** ((swiper_elo - candidate_elo) / 400))
    actual        = 1.0 if direction == RIGHT_SWIPE else 0.0
    elo_scores[candidate_id] = candidate_elo + k * (actual - expected)
    return elo_scores


# pick a random set of users to be boosted today based on the boost percentage
def get_boosted_users(users_df, policy):
    n_boosted = max(1, int(len(users_df) * policy['boost_percentage']))
    boosted   = users_df.sample(n=n_boosted)['user_id'].tolist()
    return set(boosted)


# add boosted profiles to the front of someone's queue so they get seen more
def inject_boosted_profiles(queue, boosted_today, users_df, already_swiped, swiper, day):
    from swipe_engine import QUEUE_SIZE
    boosted_candidates = users_df[
        users_df['user_id'].isin(boosted_today) &
        ~users_df['user_id'].isin(already_swiped) &
        (users_df['user_id'] != swiper['user_id'])
    ]
    if len(boosted_candidates) == 0:
        return queue
    n_to_add     = min(3, len(boosted_candidates))
    boost_sample = boosted_candidates.sample(n=n_to_add)
    # merge boosted profiles in and cut back down to the normal queue size
    combined     = pd.concat([boost_sample, queue]).drop_duplicates(subset='user_id')
    return combined.head(QUEUE_SIZE)


# run one full day of swiping with all the active policies applied
def simulate_day_with_policies(users_df, day, swiped_history, elo_scores, policy):
    from swipe_engine import (
        get_active_users, build_candidate_queue,
        swipe_probability, RIGHT_SWIPE, LEFT_SWIPE, QUEUE_SIZE
    )

    daily_swipes  = []
    active_users  = get_active_users(users_df, day)
    boosted_today = get_boosted_users(users_df, policy) if policy['boost_enabled'] else set()

    for _, swiper in active_users.iterrows():
        swiper_id         = swiper['user_id']
        already_swiped    = swiped_history.get(swiper_id, set())
        right_swipe_count = 0

        queue = build_candidate_queue(swiper, users_df, already_swiped, day)

        # elo policy: only show profiles with a similar elo rating
        if policy['elo_enabled'] and len(queue) > 0:
            swiper_elo = elo_scores.get(swiper_id, 1500)
            queue = queue[
                abs(queue['user_id'].map(elo_scores).fillna(1500) - swiper_elo)
                <= policy['elo_strictness']
            ]

        # boost policy: inject a few boosted profiles into the queue
        if policy['boost_enabled'] and len(boosted_today) > 0:
            queue = inject_boosted_profiles(queue, boosted_today, users_df,
                                            already_swiped, swiper, day)

        if len(queue) == 0:
            continue

        for swipe_num, (_, candidate) in enumerate(queue.iterrows()):
            # swipe cap policy: force a left swipe once the daily right swipe limit is hit
            if policy['swipe_cap_enabled'] and right_swipe_count >= policy['max_right_swipes_per_day']:
                direction = LEFT_SWIPE
            else:
                prob      = swipe_probability(swiper, candidate, swipe_num)
                direction = RIGHT_SWIPE if np.random.random() < prob else LEFT_SWIPE

            if direction == RIGHT_SWIPE:
                right_swipe_count += 1

            daily_swipes.append({
                'day':          day,
                'swiper_id':    swiper_id,
                'candidate_id': candidate['user_id'],
                'direction':    direction,
                'probability':  round(swipe_probability(swiper, candidate, swipe_num), 3),
            })

            already_swiped.add(candidate['user_id'])

            # elo policy: update the candidate's score after each swipe
            if policy['elo_enabled']:
                elo_scores = update_elo(elo_scores, swiper_id, candidate['user_id'], direction)

        swiped_history[swiper_id] = already_swiped

    return daily_swipes


# ladies first policy: expire matches where no message was sent within the time window
def apply_ladies_first(matches, conversations_df, policy):
    if not policy['ladies_first_enabled'] or len(conversations_df) == 0:
        return conversations_df

    valid_convos = []
    n_expired    = 0

    for _, convo in conversations_df.iterrows():
        user_a = convo['user_a']
        user_b = convo['user_b']

        # find the match row for this conversation
        match_row = matches[
            ((matches['user_a'] == user_a) & (matches['user_b'] == user_b)) |
            ((matches['user_a'] == user_b) & (matches['user_b'] == user_a))
        ]

        if len(match_row) == 0:
            valid_convos.append(convo)
            continue

        match_day = match_row.iloc[0]['match_day']
        convo_day = convo['start_day']

        # if the first message came too late, the match has expired
        if convo_day - match_day > policy['message_window_days']:
            n_expired += 1
        else:
            valid_convos.append(convo)

    if n_expired > 0:
        print(f"  Ladies First: {n_expired} matches expired (no message within window)")

    if len(valid_convos) == 0:
        return pd.DataFrame()

    return pd.DataFrame(valid_convos).reset_index(drop=True)


# nudge policy: same as advance_conversations but gives quiet convos a survival boost
def advance_conversations_with_nudge(conversations_df, current_day, policy, success_days=None):
    from conversation_engine import survival_probability, GHOST_PROBABILITY, CONVERSATION_SUCCESS_DAYS

    if success_days is None:
        success_days = CONVERSATION_SUCCESS_DAYS

    ended_events = []

    for idx, convo in conversations_df[conversations_df['status'] == 'active'].iterrows():
        if current_day < convo['start_day']:
            continue

        days_alive    = current_day - convo['start_day']
        days_inactive = current_day - convo['last_active_day']

        if days_alive >= success_days:
            conversations_df.at[idx, 'status']     = 'success'
            conversations_df.at[idx, 'length_days'] = days_alive
            continue

        base_prob = survival_probability(days_alive)

        # if the convo has gone quiet long enough, boost its survival chance (the nudge)
        if days_inactive >= policy['nudge_inactive_days']:
            prob_survive = min(0.95, base_prob + policy['nudge_survival_boost'])
        else:
            prob_survive = base_prob

        if np.random.random() < prob_survive:
            conversations_df.at[idx, 'last_active_day'] = current_day
            conversations_df.at[idx, 'length_days']      = days_alive
        else:
            # convo ends — decide if it was ghosting or a mutual fade
            if np.random.random() < GHOST_PROBABILITY:
                ghoster = np.random.choice([convo['user_a'], convo['user_b']])
                ghosted = convo['user_b'] if ghoster == convo['user_a'] else convo['user_a']
                conversations_df.at[idx, 'status']     = 'ghosted'
                conversations_df.at[idx, 'ghosted_by'] = ghoster
                conversations_df.at[idx, 'length_days'] = days_alive
                ended_events.append({'type': 'ghosted', 'victim': ghosted, 'day': current_day})
            else:
                conversations_df.at[idx, 'status']     = 'faded'
                conversations_df.at[idx, 'length_days'] = days_alive
                ended_events.append({'type': 'faded', 'user_a': convo['user_a'],
                                     'user_b': convo['user_b'], 'day': current_day})

    return conversations_df, ended_events


# measure how unequal the match distribution is
# 0 means everyone gets the same number of matches, 1 means one person gets them all
def gini_coefficient(values):
    arr = np.array(sorted(values), dtype=float)
    n   = len(arr)
    if n == 0 or arr.sum() == 0:
        return 0.0
    index = np.arange(1, n + 1)
    return (2 * (index * arr).sum()) / (n * arr.sum()) - (n + 1) / n


# run the full simulation end-to-end with whatever policies are turned on
def run_with_policy(policy=None, n_users=5000, n_days=30):
    if policy is None:
        policy = default_policy_config()

    # reset the random seed so every scenario is compared on equal footing
    np.random.seed(42)

    users_df       = generate_users(n_users)
    elo_scores     = initialize_elo(users_df) if policy['elo_enabled'] else {}
    swiped_history = {}
    all_swipes     = []
    daily_stats    = []  # stores per-day numbers for the time-series charts

    for day in range(n_days):
        daily = simulate_day_with_policies(users_df, day, swiped_history, elo_scores, policy)
        all_swipes.extend(daily)

        # capture how many users were active and how many right swipes happened today
        day_df   = pd.DataFrame(daily)
        n_active = len(set(r['swiper_id'] for r in daily)) if daily else 0
        n_right  = (day_df['direction'] == 1).sum() if len(day_df) > 0 else 0
        daily_stats.append({'day': day, 'active_users': n_active, 'right_swipes': int(n_right)})

    swipe_log = pd.DataFrame(all_swipes)
    matches   = find_matches(swipe_log)

    conversations_df = initiate_conversations(matches, users_df)

    # ladies first policy: remove matches where nobody messaged in time
    if policy['ladies_first_enabled'] and len(conversations_df) > 0:
        conversations_df = apply_ladies_first(matches, conversations_df, policy)

    # scale success threshold to the simulation length so short runs still produce successes
    # at 30 days = 7 days needed, at 14 days = 4 days needed, at 7 days = 3 days needed
    # lowered from 0.4x to 0.25x — a 7-day sustained convo is a realistic "success" signal
    success_days = min(7, max(3, int(n_days * 0.25)))

    all_ended_events = []
    if len(conversations_df) > 0 and len(matches) > 0:
        sim_days = int(matches['match_day'].max()) + 7
        for day in range(sim_days):
            if policy['nudge_enabled']:
                conversations_df, ended = advance_conversations_with_nudge(
                    conversations_df, day, policy, success_days=success_days
                )
            else:
                conversations_df, ended = advance_conversations(
                    conversations_df, day, success_days=success_days
                )
            all_ended_events.extend(ended)

    # figure out who matched but never got a single message
    matched_ids    = set(matches['user_a']) | set(matches['user_b']) if len(matches) > 0 else set()
    conversing_ids = set(conversations_df['user_a']) | set(conversations_df['user_b']) if len(conversations_df) > 0 else set()
    silent_users   = matched_ids - conversing_ids

    frustration = initialize_frustration(users_df)
    frustration = update_frustration_from_swipes(frustration, swipe_log, matches)
    frustration = update_frustration_from_conversations(frustration, all_ended_events, silent_users)

    # scale the churn threshold down for shorter simulations
    # the base threshold of 1.0 was tuned for 30 days — at 14 days it should be ~0.47
    from conversation_engine import CHURN_THRESHOLD
    scaled_threshold = CHURN_THRESHOLD * (n_days / 30)
    churned = {uid for uid, score in frustration.items() if score >= scaled_threshold}

    # calculate all the summary numbers
    total_swipes  = len(swipe_log)
    right_swipes  = (swipe_log['direction'] == 1).sum() if total_swipes > 0 else 0
    total_matches = len(matches)
    total_convos  = len(conversations_df)
    successes     = (conversations_df['status'] == 'success').sum() if total_convos > 0 else 0
    ghosted       = (conversations_df['status'] == 'ghosted').sum() if total_convos > 0 else 0
    avg_length    = conversations_df['length_days'].mean() if total_convos > 0 else 0

    # count how many matches each user got (used for the distribution chart and gini score)
    if len(matches) > 0:
        all_matched  = pd.concat([matches['user_a'], matches['user_b']])
        match_counts = all_matched.value_counts().reindex(users_df['user_id'], fill_value=0)
    else:
        match_counts = pd.Series(0, index=users_df['user_id'])

    # add churn, match count, and attractiveness tier columns to the users table
    users_df = users_df.copy()
    users_df['churned']      = users_df['user_id'].isin(churned)
    users_df['match_count']  = users_df['user_id'].map(match_counts).fillna(0)
    users_df['attract_tier'] = pd.cut(
        users_df['attractiveness'],
        bins=[0, 4, 7, 10],
        labels=['Low (1-4)', 'Mid (4-7)', 'High (7-10)']
    )

    # merge daily match counts into the daily stats table for the bar chart
    if len(matches) > 0:
        match_by_day = matches.groupby('match_day').size().reset_index(name='new_matches')
        daily_df     = pd.DataFrame(daily_stats).merge(match_by_day, left_on='day',
                                                        right_on='match_day', how='left')
        daily_df['new_matches'] = daily_df['new_matches'].fillna(0).astype(int)
    else:
        daily_df = pd.DataFrame(daily_stats)
        daily_df['new_matches'] = 0

    # return everything the dashboard needs — summary numbers plus the raw data for charts
    return {
        'total_swipes':     total_swipes,
        'right_swipes':     int(right_swipes),
        'right_swipe_rate': right_swipes / total_swipes if total_swipes > 0 else 0,
        'total_matches':    total_matches,
        'match_rate':       total_matches / right_swipes if right_swipes > 0 else 0,
        'conversations':    total_convos,
        'conv_rate':        total_convos / total_matches if total_matches > 0 else 0,
        'successes':        int(successes),
        'ghost_rate':       ghosted / total_convos if total_convos > 0 else 0,
        'avg_conv_length':  round(avg_length, 2),
        'churned_users':    len(churned),
        'churn_rate':       len(churned) / len(users_df),
        'gini':             round(gini_coefficient(match_counts.values), 3),
        'match_counts':     match_counts,
        'daily_df':         daily_df,
        'users_df':         users_df,
        'conversations_df': conversations_df,
    }


# run multiple policy scenarios side by side and print a comparison table
def compare_policies(policy_configs: dict):
    results = {}
    for name, policy in policy_configs.items():
        print(f"\nRunning scenario: '{name}'...")
        results[name] = run_with_policy(policy)

    metrics = [
        ('Total swipes',     'total_swipes',     ',d'),
        ('Right swipe rate', 'right_swipe_rate', '.1%'),
        ('Total matches',    'total_matches',    ',d'),
        ('Match rate',       'match_rate',       '.1%'),
        ('Conversations',    'conversations',    ',d'),
        ('Conv rate',        'conv_rate',        '.1%'),
        ('Successes',        'successes',        ',d'),
        ('Ghost rate',       'ghost_rate',       '.1%'),
        ('Avg conv length',  'avg_conv_length',  '.1f'),
        ('Churn rate',       'churn_rate',       '.1%'),
    ]

    names  = list(results.keys())
    col_w  = 18
    header = f"{'Metric':<22}" + "".join(f"{n:>{col_w}}" for n in names)
    divider = "=" * len(header)

    print(f"\n{divider}")
    print(header)
    print(divider)
    for label, key, fmt in metrics:
        row = f"{label:<22}"
        for name in names:
            val = results[name][key]
            row += f"{format(val, fmt):>{col_w}}"
        print(row)
    print(divider)

    return results


# only runs when you execute this file directly — runs four scenarios and prints a comparison
if __name__ == '__main__':
    print("=== Policy Intervention Comparison ===")

    scenarios = {
        'Baseline':       default_policy_config(),
        'Swipe Cap (25)': {**default_policy_config(), 'swipe_cap_enabled': True,
                           'max_right_swipes_per_day': 25},
        'Elo System':     {**default_policy_config(), 'elo_enabled': True},
        'Nudge':          {**default_policy_config(), 'nudge_enabled': True},
    }

    results = compare_policies(scenarios)
