Logic for algo

ComputedUserPreferences
ComputedMealFeatures

Algorthym parameters
- feedback_weight_swipe: 0.1
- feedback_weight_review: 0.4

- feedback_acceleration_multiplier_swipe: 2.5
- feedback_acceleration_multiplier_review: 2.5
- feedback_acceleration_property_count_threshold_swipe: 3
- feedback_acceleration_property_count_threshold_review: 2

- review_neutral_stars_threshold: 2
    - [1...5], below threshold is negative, above positive. Equal neutral (no feedback score). threshold %diff serves as a dampener to the feedback_weight_review

- recency_decay_swipe_count: 100
- recency_decay_review_count: 20
- recency_decay_reciew_time_days: 180
- recency_decay_(some param for controlling the linearity of the curve): ...

- parameters_price_range_breakpoints: [0, 5000, 10 000, 15 000, 20 000, 30 000, 50 000]

ALgorhythm concepts
- For each meal, place properties
    - Properties included
        - tags
        - cousine (for each type, separate column, a complete list of possible values provided by enum)
        - price (price ranges from the setting)
            - use column names for range index, not actual ranges
                - so r1 (0 - 5000), r2 (5001 - 10 000) etc.
                - harcode up to r10
                - on the last r, don't to 50 000+, the algorhythm does not consider anything above the final price range. Treat them as price unspecified.
        - ...
    - For each property also consider the count of considerations
    - a prefference column for each property
        - -1 to 1. 0 neutral, -1 maximum dislike, 1 maximum like

- For each user, get all of their swipes.
    - Look at the swipe outcome
        - outcomes
            - if "liked" true -> positive
            - liked false -> negative
    - Look at the meal they swiped, consider their properties
        - increment pref for the preffecene column by feedback_weight_swipe. Positively or negatively based on swipe outcome
        - increment consideration count
        - unspecified are ignored, consideration count not incremented
        - 

- look for all user reviews
    - use review_neutral_stars_threshold to determine if positive or negative
    - increment pref just like in swipes, but using configuratin constants for the reviews instead. The consideration counts are shared between the two (for now)

- decay
    - consider count (for swipes and reviews) and time_days (for reviews) and decay they influence.

- acceleration
    - keep counts for each parameter (or individual parameter range, or indivudal string/enum value)
    - if consideration count for a particular parameter is below threshold, accelerate considerations of these for the parameter.
 

- ComputedMealPrefferences
    - direct mapping from userpreffence columns to meal prefferene columns
        - but with no counts
    - -1 to 1
    - instead of incrementing, do an average of reviews
        - for tags, -1 is all truthy "no", 0 is 50% truthy "no" and 1 is all truthy "yes", where 75% truthy "yes" would imply an 0.5.
    - for price, just get the meal price (static value), and for the put 1 and for all others put 0 (or -1 not sure)

- mapping once prefs are computed
    - see how much they match 
        - if user is 0 and meal is 0, it would not add any score. 0's do not add. 
        - (some algo to fairely see how well they match)
    - each meal gets a score in the end

- random exploration
    - (some concept for enabling random exploration)
    - Potentially
        - x% chance to get a meal at random
        - y% chance to get a recommendation where each parameter has an z% chance to not be considered in the evaluation.
        - p% chance for any parameter to be not considered in an evaluation.
