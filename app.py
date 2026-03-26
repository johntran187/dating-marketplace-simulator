import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from policy_engine import run_with_policy, default_policy_config

# this must be the very first streamlit call in the file
st.set_page_config(
    page_title="Dating Marketplace Simulator",
    page_icon=None,
    layout="wide"
)

# all the controls live in the sidebar on the left
st.sidebar.title("Dating Simulator")
st.sidebar.header("Simulation Settings")

# sliders to control how big and how long the simulation runs
n_users = st.sidebar.slider("Number of users",    500,  5000, 1000, 500)
n_days  = st.sidebar.slider("Simulation days",    7,    30,   14,   7)

st.sidebar.divider()
st.sidebar.header("Policy Toggles")

# swipe cap: checkbox turns it on, slider sets the daily limit
cap_on  = st.sidebar.checkbox("Daily Swipe Cap",
    help="Limits how many right swipes a user can make per day. Forces more intentional swiping — like Hinge. Hypothesis: fewer matches overall, but higher quality engagement and less frustration.")
cap_n   = st.sidebar.slider("Max right swipes/day", 5, 50, 25, disabled=not cap_on)

st.sidebar.divider()

# elo: checkbox turns it on, slider controls how close two users' ratings need to be
elo_on         = st.sidebar.checkbox("Elo Rating System",
    help="Assigns each user a dynamic rating based on how others swipe on them. Users are then shown profiles with similar ratings. Hypothesis: creates more compatible matches, but lower-rated users may see fewer profiles and churn faster.")
elo_strictness = st.sidebar.slider("Elo strictness (points)", 50, 400, 200, disabled=not elo_on)

st.sidebar.divider()

# ladies first: checkbox turns it on, slider sets how many days women have to message first
lf_on   = st.sidebar.checkbox("Ladies First (Bumble model)",
    help="After a match, only women can send the first message. If no message is sent within the window, the match expires. Hypothesis: reduces low-effort messages but may lower the overall conversation rate.")
lf_days = st.sidebar.slider("Message window (days)", 1, 3, 1, disabled=not lf_on)

st.sidebar.divider()

# boost: checkbox turns it on, slider sets what percentage of users get boosted
boost_on  = st.sidebar.checkbox("Profile Boost",
    help="A random percentage of users get 3x more visibility for the day — their profiles appear in more queues. Simulates a paid boost feature. Hypothesis: increases matches for boosted users but may feel artificial.")
boost_pct = st.sidebar.slider("% of users boosted", 1, 20, 5, disabled=not boost_on)

st.sidebar.divider()

# anti-ghosting nudge: checkbox turns it on, slider sets how many quiet days trigger a nudge
nudge_on   = st.sidebar.checkbox("Anti-Ghosting Nudge",
    help="If a conversation goes quiet for too many days, the app sends a nudge that increases the chance of a reply. Hypothesis: reduces ghosting and extends average conversation length, but forced replies may be lower quality.")
nudge_days = st.sidebar.slider("Silence before nudge (days)", 1, 5, 2, disabled=not nudge_on)

st.sidebar.divider()

# the big run button — clicking this kicks off the simulation
run_button = st.sidebar.button(
    "▶  Run Simulation",
    type="primary",
    use_container_width=True
)

# build the policy config dict from whatever the sidebar controls are set to
policy = {
    **default_policy_config(),
    'swipe_cap_enabled':        cap_on,
    'max_right_swipes_per_day': cap_n,
    'elo_enabled':              elo_on,
    'elo_strictness':           elo_strictness,
    'ladies_first_enabled':     lf_on,
    'message_window_days':      lf_days,
    'boost_enabled':            boost_on,
    'boost_percentage':         boost_pct / 100,
    'nudge_enabled':            nudge_on,
    'nudge_inactive_days':      nudge_days,
}

# session state keeps the results alive when the user tweaks a slider without re-running
if 'results' not in st.session_state:
    st.session_state.results = None

# when run is clicked, run the simulation and store the results
if run_button:
    with st.spinner("Running simulation... this takes about 15-30 seconds"):
        st.session_state.results = run_with_policy(policy, n_users=n_users, n_days=n_days)

# main page title
st.title("Dating Marketplace Simulator")
st.caption("Simulate a dating app. Toggle policies. See what changes.")

# if no simulation has been run yet, show a message and stop rendering
if st.session_state.results is None:
    st.info("Configure your settings in the sidebar and click **Run Simulation** to begin.")
    st.stop()

# shorthand so we don't have to type st.session_state.results every time
r = st.session_state.results

# the top row of big kpi numbers
st.header("Summary Metrics")
st.caption(f"**{n_users:,} users** · **{n_days} days** · Seed 42")

# first row: matches, match rate, conversation rate, avg convo length, churn rate
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Matches",     f"{r['total_matches']:,}")
col2.metric("Match Rate",        f"{r['match_rate']:.1%}")
col3.metric("Conversation Rate", f"{r['conv_rate']:.1%}",
    help="The percentage of matches where at least one person sent a first message. "
         "Real dating apps see 10–20% of matches get a message. Most matches are never acted on.")
col4.metric("Avg Convo Length",  f"{r['avg_conv_length']:.1f} days")
col5.metric("Churn Rate",        f"{r['churn_rate']:.1%}",
    help="The percentage of users who got frustrated and quit the app. "
         "Frustration builds up from unmatched right swipes, silent matches, and getting ghosted. "
         "Real apps lose 20–30% of their users every month.")

# second row: right swipe rate, ghost rate, successes, churned count, gini inequality score
col1b, col2b, col3b, col4b, col5b = st.columns(5)
col1b.metric("Right Swipe Rate", f"{r['right_swipe_rate']:.1%}")
col2b.metric("Ghost Rate",       f"{r['ghost_rate']:.1%}",
    help="Of all the conversations that ended, the percentage where one person just "
         "stopped responding instead of both people mutually losing interest. "
         "Real world ghosting accounts for 50–70% of dead conversations.")
col3b.metric("Successes",        f"{r['successes']:,}",
    help="The number of conversations that lasted 7 or more days. "
         "This is used as a signal that two people genuinely connected and likely moved "
         "the conversation off the app. Most users never reach this in a given month.")
col4b.metric("Churned Users",    f"{r['churned_users']:,}")
col5b.metric("Gini Coefficient", f"{r['gini']:.3f}",
    help="A score from 0 to 1 that measures how unfairly matches are spread across users. "
         "Think of it like wealth inequality but for matches. "
         "A score near 0 means everyone gets roughly the same number of matches. "
         "A score near 1 means a tiny group of users is collecting almost all the matches "
         "while most people get very few or none. "
         "Dating apps are one of the most unequal environments studied. "
         "Real world research puts this around 0.54 for women and 0.76 for men.")

st.divider()

# charts row 1: match distribution and active users over time
left, right = st.columns(2)

with left:
    st.subheader("Match Distribution")
    st.caption("Most users get few matches. A small group gets many — that's the power law.")
    fig_dist = px.histogram(
        r['match_counts'],
        nbins=40,
        labels={'value': 'Matches received', 'count': 'Number of users'},
        color_discrete_sequence=['#e8434a']
    )
    fig_dist.update_layout(showlegend=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig_dist, use_container_width=True)

with right:
    st.subheader("Active Users Per Day")
    st.caption("Grows as more users join during the simulation window.")
    fig_active = px.line(
        r['daily_df'], x='day', y='active_users',
        labels={'day': 'Day', 'active_users': 'Active users'},
        color_discrete_sequence=['#4a90e8']
    )
    fig_active.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig_active, use_container_width=True)

st.divider()

# charts row 2: daily new matches and conversation outcome breakdown
left2, right2 = st.columns(2)

with left2:
    st.subheader("New Matches Per Day")
    st.caption("Shows when matching activity peaks across the simulation.")
    fig_matches = px.bar(
        r['daily_df'], x='day', y='new_matches',
        labels={'day': 'Day', 'new_matches': 'New matches'},
        color_discrete_sequence=['#50c878']
    )
    fig_matches.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig_matches, use_container_width=True)

with right2:
    st.subheader("Conversation Outcomes")
    st.caption("What happened to conversations that started? Success, ghosted, or faded?")
    if len(r['conversations_df']) > 0:
        status_counts = r['conversations_df']['status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig_status = px.pie(
            status_counts, names='Status', values='Count',
            color_discrete_sequence=px.colors.qualitative.Set2,
            hole=0.35
        )
        fig_status.update_layout(margin=dict(t=10, b=10))
        st.plotly_chart(fig_status, use_container_width=True)
    else:
        st.info("No conversations to display.")

st.divider()

# table showing how match and churn rates differ by attractiveness tier
st.subheader("Metrics by Attractiveness Tier")
st.caption("Low-attractiveness users get fewer matches and churn more — does a policy change that?")

tier_df = (
    r['users_df']
    .groupby('attract_tier', observed=True)
    .agg(
        users       = ('user_id',     'count'),
        avg_matches = ('match_count', 'mean'),
        churn_rate  = ('churned',     'mean'),
    )
    .round(3)
    .reset_index()
)
tier_df.columns = ['Tier', 'Users', 'Avg Matches', 'Churn Rate']
st.dataframe(tier_df, use_container_width=True, hide_index=True)

st.divider()
st.caption("Dating Marketplace Simulator · Built with Python + Streamlit · John Tran Portfolio Project")
