### Challenges
# Meal review vs Place review
# Images can be of places or meal
# Price of meal vs price of visit
# Swipe model for meal vs place
# Same meals at the same place may be posted -> need for meal aggregation

### Constraints
# We only have a few weeks - simplify where possible
# Keep user experience simple - don't overwhelm with too many options/fields

### Suggestions/Conclusions/Decisions
# Exclusively meal-based reviews only. (for now, for simplicity)
#   No place-specific fields in reviews, like "outdoor seating", "price of visit"
#   Images are mainly for meals, buts complimentary images of places stored at meal level are welcome.
#   Rating is regarded as the of 'whole experience': meal + place
# MealReview is a Meal-at-a-Place. We distinguish by the combined specific meal + specific place experience.
#  Users swipe on MealReviews (meal-at-a-place) not Places.
#   So not "Peperoni Pizza" in general, but "Peperoni Pizza at Joe's Pizzeria".
# No meal aggregation in the first version.
#    Implement later if time permits.
#    For now feature MealReviews as meals.


----------------------
(Base)
- created_at: datetime
- updated_at: datetime
- id: uuid
---------------------

User
- email
- hashed_password
- first_name
- last_name
- image_path

MealReview
- User: 1
- Place: 1
- meal_name
- rating 1...5 int
- text
- images: (0..5 strings (paths to images)) via associative table
- waiting_time_minutes: int
- price: float
- is_vegan: Enum("no", "not specified", "yes")
- is_halal
- is_vegetarian
- is_spicy
_ is_gluten_free
- is_dairy_free
- is_nut_free

Place
- lat: float
- lng: float
- name
- address
- images: (0..5 strings (paths to images)) via associative table


DATA:

Swipe:
- User: 1
- MealReview: 1 (in the Future should be AggregatedMeal)
- liked: bool
- session_id: uuid








FUTURE:

AggregatedMeal
- common_name

Place:
- opening_hours: (opening hours object -> start/end for each weekday + holidays)
- cuisine_type: infer from meal reviews with AI


ARCHIVE/NOT USING:
PlaceReview
- FullReview: 1
- is_outdoor_seating
- is_wifi
- is_pet_friendly
- has_power_outlets
- is_quiet
