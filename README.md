# dating-marketplace-simulator

A simple, interactive simulation of a dating app marketplace using Python and Streamlit that demonstrates the impact of various design choices on user experience and platform efficiency.

## general information

Dating apps create very unequal markets as a few percent of all users see most of the activity. Most users do little better than this and some users may never be seen or interacted with at all.

This application will allow us to explore such questions as:

• how does forcing users to swipe more deliberately affect overall activity? 
• would an elo-based rating system produce higher-quality matches? 
• would a "women go First" messaging Policy result in fewer shallow matches? 
• do Profile boosters help or damage the ecosystem? 
• are anti-ghosting nudge mechanisms effective in keeping conversations going longer?

We want to model these design options to evaluate them based upon the same Metrics we care about in our real-world apps; i.e., total number of matches generated, match rates, conversation initiation rates, ghost rates, average conversation duration, churn rates and how equally distributed matches are among all users (i.e. Gini coefficients).

## key features

### interactive dashboard
Streamlit is used to build an interactive dashboard which allows us to:
- select the number of users.
- choose the length of each simulation.
- toggle on/off marketplace interventions (Policy experiments).
- run simulations from the left-hand menu bar.
- view key performance indicators (KPI) across multiple categories and display plots showing trends over time.

### experiments in design options
There are four intervention types implemented into the simulator at present:
1. **daily swipe limit**
Limits how many right swipes a user may execute every 24 hours.

2. **dynamic visibility ratings based upon elo scores**
This assigns users dynamic levels of visibility in the candidate queue depending on their relative level of attractiveness to other users.

3. **Ladies First messaging rule**
Similar to bumble's functionality; simulates a scenario where both parties have a limited amount of time to send one another messages. If none are exchanged, the potential connection expires.

4. **Profile boosters**
Increases the visibility of a certain portion of users when determining who should appear in a candidates list.

5. **nudges to prevent ghosting**
Raises the probability that inactive conversations remain active for longer periods of time.

### kpis and plots
These are displayed in two ways on the dashboard:
- as numbers representing Metrics including:
+ total number of successful connections established during each simulation.
+ match rate = number of successful matches / total swipes made by all users.
+ conversation initiation rate = number of conversations started / total successful matches.
+ average length of each conversation = summed time spent on all conversations / count of all conversations.
+ churn rate = proportion of users who have never established a successful connection after one or more sessions using the app.
+ right swipe rate = number of right swipes executed by all users / total number of swipes executed by all users.
+ ghost rate = number of failed connections due to no response from either party / total number of successful matches.
+ count of successful conversations = number of completed conversations during the last session / total number of successful matches.
+ gini coefficient for distribution of success = measures equality among all users in terms of their success at establishing connections.