# dating-marketplace-simulator

An interactive simulation of a dating app marketplace built with Python and Streamlit.

This project models how user behavior, match formation, conversations, ghosting, and churn change under different product policies. The app lets you run simulations, toggle marketplace interventions, and view outcome metrics through a dashboard.

## Overview

Dating apps are highly unequal marketplaces. A small number of users receive a large share of attention, while many users get few matches and churn quickly.

This simulator explores questions like:

- What happens if users are forced to swipe more intentionally?
- Does an Elo-style ranking system improve match quality?
- Does a “ladies first” messaging rule reduce low-effort matches?
- Do profile boosts help or distort the system?
- Can anti-ghosting nudges keep conversations alive longer?

The goal is to simulate these product decisions and measure their effect on:
- total matches
- match rate
- conversation rate
- ghost rate
- average conversation length
- churn rate
- inequality in match distribution

## Features

### Interactive dashboard
Built with Streamlit, the app provides a UI to:
- choose number of users
- choose simulation length
- toggle marketplace policies
- run simulations from the sidebar
- view KPI summaries and charts

### Policy experiments
The simulator currently supports:

- **Daily Swipe Cap**  
  Limits how many right swipes a user can make per day.

- **Elo Rating System**  
  Assigns users dynamic visibility scores and prioritizes profiles with similar ratings.

- **Ladies First**  
  Simulates a Bumble-style rule where matches expire if no message is sent within a time window.

- **Profile Boost**  
  Gives a percentage of users more visibility in candidate queues.

- **Anti-Ghosting Nudge**  
  Boosts the chance a quiet conversation survives after inactivity.

### Metrics and visualizations
The dashboard displays:
- total matches
- match rate
- conversation rate
- average conversation length
- churn rate
- right swipe rate
- ghost rate
- number of “successful” conversations
- Gini coefficient of match inequality

It also includes charts for:
- match distribution
- active users per day
- new matches per day
- conversation outcomes
- metrics by attractiveness tier

## Project Structure

```text
dating-marketplace-simulator/
├── app.py
├── requirements.txt
├── .gitignore
├── data/
│   ├── conversations.csv
│   ├── matches.csv
│   ├── swipe_log.csv
│   ├── users.csv
│   └── users_with_churn.csv
├── notebooks/
└── src/
    ├── conversation_engine.py
    ├── policy_engine.py
    ├── swipe_engine.py
    └── user_generator.py