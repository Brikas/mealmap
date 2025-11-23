Here is the technical specification for the MealMap Recommendation Heuristic.

***

# Recommendation Engine Specification: "MealMap Match v2"

## 1. Overview
This system implements a **Content-Based Filtering** algorithm using Explicit Feature Vectors. It decouples the "Objective Truth" of a meal (aggregated from crowdsourced reviews) from the "Subjective Taste" of a user (learned via EMA).

**Core Philosophy:**
*   **Write-Heavy, Read-Light:** Vectors are pre-computed asynchronously. Feed generation is a computationally cheap similarity search.
*   **Vector Space:** Interactions are mapped to normalized vectors (-1.0 to 1.0).
*   **Dominance Prevention:** Dietary constraints (hard filters) outweigh soft preferences (price/wait time).

## 2. Data Models & Storage

### 2.1 Enums
**Cuisines:**
*   **European:** `italian`, `french`, `spanish`, `greek`, `british`
*   **Asian:** `chinese`, `japanese`, `korean`, `thai`, `vietnamese`, `indian`, `filipino`
*   **American:** `american`, `mexican`
*   **Middle Eastern/African:** `mediterranean`, `african`
*   **Other:** `fusion`, `cafe`, `bakery`, `barbecue`, `seafood`, `vegetarian_vegan`, `other`, `unspecified`

**TriState (Review Inputs):**
*   `yes` (+1.0), `no` (-1.0), `unspecified` (0.0)

### 2.2 Computed Entities
Storage uses **PostgreSQL JSONB** to allow sparse vector storage and easy schema iteration.

**1. ComputedMealFeatures (The Truth)**
*   **Scope:** 1-to-1 with `Meal`.
*   **Update Trigger:** Background job upon new `MealReview`.
*   **Schema:**
    *   `tag_vector` (JSONB): `{"is_spicy": float, "is_vegan": float, ...}` (Range -1.0 to 1.0)
    *   `cuisine_vector` (JSONB): `{"italian": float, ...}` (Normalized distribution)
    *   `avg_price` (Float): Scalar.
    *   `avg_wait_time` (Float): Scalar.
    *   `review_count` (Int): Confidence metric.

**2. ComputedUserPreferences (The Taste)**
*   **Scope:** 1-to-1 with `User`.
*   **Update Trigger:** Real-time upon `Swipe` or `MealReview`.
*   **Schema:**
    *   Each preference field stores a tuple: `{ "val": float, "count": int }`.
    *   `tag_prefs` (JSONB): e.g., `{"is_spicy": {"val": 0.8, "count": 12}}`
    *   `cuisine_prefs` (JSONB)
    *   `price_bin_prefs` (JSONB): Mapped to price buckets (`r0`...`rN`).
    *   `wait_bin_prefs` (JSONB): Mapped to wait time buckets.

---

## 3. Algorithm: "The Truth" (Meal Feature Aggregation)
*Objective: Determine what a meal actually IS based on noisy user data.*

**Logic:**
1.  **Tag Aggregation:**
    *   Sum inputs: `Yes` = +1, `No` = -1, `Unspecified` = 0.
    *   Calculate Average: $\frac{\sum Inputs}{TotalReviews}$.
    *   *Result:* A continuous value between -1.0 (Confirmed No) and 1.0 (Confirmed Yes).
2.  **Cuisine Aggregation:**
    *   If explicitly tagged in reviews/places, calculate the distribution (e.g., 90% users say Italian, 10% say Fusion).
3.  **Scalar Aggregation:**
    *   Simple arithmetic mean for `price` and `waiting_time`.

---

## 4. Algorithm: "The Taste" (User Preference Learning)
*Objective: Update user vectors based on interactions using Exponential Moving Average (EMA) and Cold-Start Acceleration.*

### 4.1 Inputs & Signal Strength
Define the "Target Signal" ($T$) for the update:
*   **Swipe Like:** $1.0$
*   **Swipe Dislike:** $-0.8$ (Asymmetric penalty)
*   **Review (Positive > 2 stars):** $2.5$ (High confidence)
*   **Review (Negative < 2 stars):** $-2.5$

### 4.2 Time Decay (Interaction Weight)
Apply decay to the input signal based on the age of the interaction ($t_{days}$) to prioritize recency.
$$W_{time} = 2^{-(t_{days} / \text{HALF\_LIFE})}$$
*Parameter:* `RECENCY_HALF_LIFE_DAYS = 90`

### 4.3 Cold-Start Acceleration
Calculate a multiplier based on the user's specific interaction count ($N$) for that specific feature.
$$Multiplier_{accel} = 1 + (M_{max} \cdot e^{-k \cdot N})$$
*   $M_{max} = 2.5$ (Max boost)
*   $k = 0.2$ (Decay rate)
*   *Effect:* 1st interaction has ~3.5x impact; 10th interaction has ~1.3x impact.

### 4.4 The Update Rule (Delta Rule)
For every feature $f$ present in the Meal's computed vector (where Meal Strength $|S_m| > 0.2$):

1.  **Calculate Effective Signal:** $Signal = T \cdot W_{time} \cdot S_m$
    *   *Note:* If User Likes (1.0) a Non-Vegan Meal (-1.0), the signal is -1.0 (Dislikes Vegan).
2.  **Apply Delta Update:**
    $$Val_{new} = Val_{old} + \alpha \cdot Multiplier_{accel} \cdot (Signal - Val_{old})$$
    *   $\alpha$ (Learning Rate) = $0.15$
3.  **Update Count:** $Count_{new} = Count_{old} + 1$
4.  **Clamp:** Ensure result is within $[-1.0, 1.0]$.

---

## 5. Algorithm: "The Match" (Feed Scoring)
*Objective: Calculate similarity score between User ($U$) and Candidate Meal ($M$).*

### 5.1 Weight Distribution (Fairness)
To prevent feature dominance, the final score is a weighted sum of sub-scores.
*   **Dietary Tags ($W_{tags} = 0.50$):** Primary constraint.
*   **Cuisine ($W_{cuisine} = 0.30$):** Primary flavor preference.
*   **Price ($W_{price} = 0.10$):** Secondary optimization.
*   **Wait Time ($W_{wait} = 0.10$):** Secondary optimization.

### 5.2 Soft Binning (Scalars to Vectors)
To compare Price and Wait Time (Scalars) against User Preferences (Vectors), convert Meal Scalars into "Soft Vectors" using Gaussian smearing.
*   **Breakpoints:** `[0, 5000, 10000, 15000, 20000, 30000, 50000]`
*   **Logic:**
    *   Identify target bin $r_i$.
    *   Assign $1.0$ to $r_i$.
    *   Assign $0.25$ to neighbors $r_{i-1}$ and $r_{i+1}$.
    *   *Benefit:* Eliminates hard boundary cutoff effects.

### 5.3 Similarity Calculation
For each feature group (Tags, Cuisine, Price, Wait):
1.  **Calculate Cosine Similarity:**
    $$Sim(U, M) = \frac{U \cdot M}{||U|| \cdot ||M||}$$
    *   *Rationale:* Normalizes for vector magnitude. A user with 1000 interactions shouldn't dominate a user with 10. A meal with 50 tags shouldn't dominate a meal with 5.
2.  **Aggregate:**
    $$Score_{final} = \sum (Sim_{group} \times W_{group})$$

---

## 6. Parameters & Constants Reference

| Parameter | Value | Description |
| :--- | :--- | :--- |
| `WEIGHT_TAGS` | **0.50** | Importance of dietary features |
| `WEIGHT_CUISINE` | **0.30** | Importance of cuisine type |
| `WEIGHT_PRICE` | **0.10** | Importance of price optimization |
| `WEIGHT_WAIT` | **0.10** | Importance of waiting time optimization |
| `LEARNING_RATE` ($\alpha$) | **0.15** | Base EMA update rate |
| `ACCEL_MAX` | **2.5** | Max multiplier for cold-start |
| `ACCEL_DECAY` | **0.2** | Exponential decay for acceleration |
| `RECENCY_HALF_LIFE` | **90 days** | Time decay for input signals |
| `PRICE_BINS` | `[0, 5k, 10k, 15k, 20k, 30k, 50k]` | Upper bounds for price buckets |
