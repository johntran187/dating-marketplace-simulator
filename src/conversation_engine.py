import numpy as np
import pandas as pd
from user_generator import generate_users
from swipe_engine import run_simulation, find_matches

np.random.seed(42)

# tuning numbers — adjust these to change how the simulation feels
MESSAGE_PROBABILITY_BASE  = 0.15   # base chance a match leads to someone messaging first
                                   # real apps: only ~10-20% of matches ever get a first message
GHOST_PROBABILITY         = 0.65   # when a convo dies, 65% of the time it's one-sided ghosting
                                   # real data: ghosting is the #1 way dating app convos end (~50-70%)
CONVERSATION_SUCCESS_DAYS = 10     # a convo that survives this many days counts as a success

FRUSTRATION_NO_MATCH      = 0.008  # frustration added per right swipe that got no match back
                                   # at ~90 right swipes/month, this adds ~0.70 just from being ignored
FRUSTRATION_NO_MESSAGE    = 0.35   # frustration added when a match goes silent without a message
                                   # a few silent matches quickly push a user toward quitting
FRUSTRATION_GHOSTED       = 0.45   # frustration added when the user gets ghosted mid-conversation
                                   # getting ghosted after a real conversation is the biggest churn driver
CHURN_THRESHOLD           = 0.7    # real apps lose 20-30% of users per month
                                   # lowered to 0.7 so regular users who get no results churn out


def initiate_conversations(matches, users_df):
    # go through every match and decide if anyone actually sent the first message
    # more attractive matches are more exciting so they're more likely to get a message
    user_attractiveness = users_df.set_index('user_id')['attractiveness']
    conversations = []

    for _, match in matches.iterrows():
        user_a_attract = user_attractiveness[match['user_a']]
        user_b_attract = user_attractiveness[match['user_b']]
        avg_attract    = (user_a_attract + user_b_attract) / 2

        # bump up the message probability if both users are attractive
        excitement_boost = (avg_attract - 5) * 0.05
        prob = np.clip(MESSAGE_PROBABILITY_BASE + excitement_boost, 0.05, 0.90)

        if np.random.random() < prob:
            conversations.append({
                'match_id':        match.name,
                'user_a':          match['user_a'],
                'user_b':          match['user_b'],
                'start_day':       match['match_day'],
                'last_active_day': match['match_day'],
                'length_days':     0,
                'status':          'active',   # can be: active, ghosted, faded, or success
                'ghosted_by':      None,
            })

    result = pd.DataFrame(conversations)
    print(f"Matches that led to conversations: {len(result):,} ({len(result)/len(matches):.1%} of matches)")
    return result


def survival_probability(days_active):
    # how likely is a conversation to survive one more day?
    # starts at 70% — most convos die in the first 1-3 days (realistic)
    # floors at 65% so convos that make it past day 1 have a stable ongoing chance
    # this means ~70% of all convos die within 3 days, but survivors can reach success
    base  = 0.70
    decay = 0.06 * days_active
    floor = 0.65
    return max(floor, base - decay)


def advance_conversations(conversations_df, current_day, success_days=None):
    # move every active conversation forward by one day
    # each convo either survives, gets ghosted, fades out, or hits the success threshold
    # success_days can be passed in as a smaller number for shorter simulations
    if success_days is None:
        success_days = CONVERSATION_SUCCESS_DAYS

    ended_events = []

    for idx, convo in conversations_df[conversations_df['status'] == 'active'].iterrows():
        # skip convos that haven't started yet on this day
        if current_day < convo['start_day']:
            continue

        days_alive = current_day - convo['start_day']

        # if the convo has been going long enough, mark it as a success
        if days_alive >= success_days:
            conversations_df.at[idx, 'status']     = 'success'
            conversations_df.at[idx, 'length_days'] = days_alive
            continue

        prob_survive = survival_probability(days_alive)

        if np.random.random() < prob_survive:
            # convo lives another day — update its last active day
            conversations_df.at[idx, 'last_active_day'] = current_day
            conversations_df.at[idx, 'length_days']      = days_alive
        else:
            # convo ends — decide if it was ghosting or a mutual fade
            if np.random.random() < GHOST_PROBABILITY:
                # one person stops responding
                ghoster = np.random.choice([convo['user_a'], convo['user_b']])
                ghosted = convo['user_b'] if ghoster == convo['user_a'] else convo['user_a']
                conversations_df.at[idx, 'status']     = 'ghosted'
                conversations_df.at[idx, 'ghosted_by'] = ghoster
                conversations_df.at[idx, 'length_days'] = days_alive
                ended_events.append({
                    'type':   'ghosted',
                    'victim': ghosted,
                    'day':    current_day
                })
            else:
                # both people lose interest at the same time
                conversations_df.at[idx, 'status']     = 'faded'
                conversations_df.at[idx, 'length_days'] = days_alive
                ended_events.append({
                    'type':   'faded',
                    'user_a': convo['user_a'],
                    'user_b': convo['user_b'],
                    'day':    current_day
                })

    return conversations_df, ended_events


def initialize_frustration(users_df):
    # give every user a frustration score starting at zero
    return {uid: 0.0 for uid in users_df['user_id']}


def update_frustration_from_swipes(frustration, swipe_log, matches):
    # add a little frustration for every right swipe that never turned into a match
    # this models the feeling of putting yourself out there and getting nothing back
    right_swipes = swipe_log[swipe_log['direction'] == 1]

    # build a lookup of all matched pairs so we can check quickly
    matched_pairs = set()
    for _, m in matches.iterrows():
        matched_pairs.add((m['user_a'], m['user_b']))
        matched_pairs.add((m['user_b'], m['user_a']))  # add both directions

    # if the right swipe didn't lead to a match, tick up that user's frustration
    for _, swipe in right_swipes.iterrows():
        pair = (swipe['swiper_id'], swipe['candidate_id'])
        if pair not in matched_pairs:
            uid = swipe['swiper_id']
            if uid in frustration:
                frustration[uid] += FRUSTRATION_NO_MATCH

    return frustration


def update_frustration_from_conversations(frustration, ended_events, silent_match_users):
    # add frustration for getting ghosted or matching with someone who never messaged
    for event in ended_events:
        if event['type'] == 'ghosted':
            uid = event['victim']
            if uid in frustration:
                frustration[uid] += FRUSTRATION_GHOSTED

    # users who matched but never got a single message
    for uid in silent_match_users:
        if uid in frustration:
            frustration[uid] += FRUSTRATION_NO_MESSAGE

    return frustration


def get_churned_users(frustration):
    # return the set of users whose frustration has hit the quitting threshold
    return {uid for uid, score in frustration.items() if score >= CHURN_THRESHOLD}


def run_full_simulation(users_df, swipe_log, matches):
    # tie together the conversation and churn systems on top of the swipe data
    print("Starting conversation & churn simulation...")

    # decide which matches actually turned into conversations
    conversations_df = initiate_conversations(matches, users_df)

    # find users who matched but never got a message — they'll gain frustration
    matched_user_ids    = set(matches['user_a']) | set(matches['user_b'])
    conversing_user_ids = set(conversations_df['user_a']) | set(conversations_df['user_b'])
    silent_match_users  = matched_user_ids - conversing_user_ids

    # start everyone at zero frustration, then add from swipe misses
    frustration = initialize_frustration(users_df)
    frustration = update_frustration_from_swipes(frustration, swipe_log, matches)

    # step through every day and update each conversation's status
    all_ended_events = []
    if len(conversations_df) > 0:
        sim_days = int(matches['match_day'].max()) + 7  # run a week past the last match
        for day in range(sim_days):
            conversations_df, ended_events = advance_conversations(conversations_df, day)
            all_ended_events.extend(ended_events)

    # add frustration from conversation outcomes (ghosting, silent matches)
    frustration = update_frustration_from_conversations(
        frustration, all_ended_events, silent_match_users
    )

    # anyone who crossed the frustration threshold has churned
    churned = get_churned_users(frustration)
    print(f"Users who churned: {len(churned):,} ({len(churned)/len(users_df):.1%} of all users)")

    return conversations_df, frustration, churned


# only runs when you execute this file directly
if __name__ == '__main__':
    print("=== Dating Marketplace Simulator — Full Run ===\n")

    print("[1/3] Generating users...")
    users_df = generate_users()

    print("\n[2/3] Running swipe simulation...")
    swipe_log = run_simulation(users_df)
    matches   = find_matches(swipe_log)

    print("\n[3/3] Running conversation & churn layer...")
    conversations_df, frustration, churned = run_full_simulation(users_df, swipe_log, matches)

    total_convos = len(conversations_df)
    successes    = (conversations_df['status'] == 'success').sum()
    ghosted      = (conversations_df['status'] == 'ghosted').sum()
    faded        = (conversations_df['status'] == 'faded').sum()
    avg_length   = conversations_df['length_days'].mean()

    print(f"\n=== Final Simulation Stats ===")
    print(f"Total matches:           {len(matches):,}")
    print(f"Matches → conversation:  {total_convos:,}  ({total_convos/len(matches):.1%})")
    print(f"Conversation successes:  {successes:,}  ({successes/total_convos:.1%} of conversations)")
    print(f"Ghosted:                 {ghosted:,}  ({ghosted/total_convos:.1%})")
    print(f"Mutual fades:            {faded:,}  ({faded/total_convos:.1%})")
    print(f"Avg conversation length: {avg_length:.1f} days")
    print(f"Churned users:           {len(churned):,}  ({len(churned)/len(users_df):.1%})")

    # split churn by attractiveness tier to confirm less attractive users quit more
    users_df['churned'] = users_df['user_id'].isin(churned)
    users_df['attract_tier'] = pd.cut(
        users_df['attractiveness'],
        bins=[0, 4, 7, 10],
        labels=['low (1-4)', 'mid (4-7)', 'high (7-10)']
    )
    churn_by_tier = users_df.groupby('attract_tier', observed=True)['churned'].mean().round(3)
    print(f"\nChurn rate by attractiveness tier:")
    print(churn_by_tier.to_string())

    conversations_df.to_csv('data/conversations.csv', index=False)
    users_df.to_csv('data/users_with_churn.csv', index=False)
    print("\nSaved conversations.csv and users_with_churn.csv to data/")
