import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter

import test_utils as tu

def extra_get_reviews_test_queries(users):
    return [
        {
            "action_caller": tu.get_user_from_email("elias@t.com", users),
            "description": "All reviews by specific user (Anna)",
            "params": {
                "user_id": tu.get_user_from_email("anna@t.com", users)["id"],
                "sort_by": "rating",
                "sort_order": "desc",
            }
        },
        {
            "action_caller": tu.get_user_from_email("david@t.com", users),
            "description": "High-rated (4-5 stars) affordable meals (under 10,000 won)",
            "params": {
                "min_rating": 4,
                "max_price": 10000,
                "sort_by": "price",
                "sort_order": "asc",
            }
        },
        {
            "action_caller": tu.get_user_from_email("george@t.com", users),
            "description": "Vegan options sorted by rating",
            "params": {
                "is_vegan": "yes",
                "sort_by": "rating",
                "sort_order": "desc",
            }
        },
        {
            "action_caller": tu.get_user_from_email("airidas.brikas@gmail.com", users),
            "description": "Spicy food with short wait times",
            "params": {
                "is_spicy": "yes",
                "max_waiting_time": 15,
                "sort_by": "waiting_time_minutes",
                "sort_order": "asc",
            }
        },
        {
            "action_caller": tu.get_user_from_email("rares@t.com", users),
            "description": "Search for 'chicken' meals with rating 4+",
            "params": {
                "meal_name": "chicken",
                "min_rating": 4,
                "sort_by": "rating",
                "sort_order": "desc",
            }
        },
        {
            "action_caller": tu.get_user_from_email("elias@t.com", users),
            "description": "Vegetarian options near campus",
            "params": {
                "lat": 36.373,
                "lng": 127.367,
                "radius_m": 3000,
                "is_vegetarian": "yes",
                "sort_by": "distance",
                "sort_order": "asc",
            }
        },
    ]

def analyze_review_statistics(reviews, places):
    """
    Comprehensive review statistics analysis with distribution graphs
    """
    # Create DataFrame for analysis
    df_reviews = pd.DataFrame([
        {
            "action_caller_email": r["action_caller"]["email"],
            "place_test_id": r["place_test_id"],
            **r["fields"]
        }
        for r in reviews
    ])

    # Set style for better-looking graphs
    sns.set_style("whitegrid")
    plt.rcParams['figure.figsize'] = (15, 10)

    # Create subplots
    fig, axes = plt.subplots(3, 2, figsize=(15, 12))
    fig.suptitle('Review Statistics Overview', fontsize=16, fontweight='bold')

    # 1. Reviews per user distribution
    user_emails = [r["action_caller"]["email"] for r in reviews]
    user_counts = Counter(user_emails)
    user_review_counts = list(user_counts.values())

    axes[0, 0].hist(user_review_counts, bins=max(user_review_counts), edgecolor='black', alpha=0.7)
    axes[0, 0].set_title('Reviews Per User Distribution')
    axes[0, 0].set_xlabel('Number of Reviews')
    axes[0, 0].set_ylabel('Number of Users')
    axes[0, 0].axvline(np.mean(user_review_counts), color='r', linestyle='--', label=f'Mean: {np.mean(user_review_counts):.1f}')
    axes[0, 0].legend()

    # 2. Reviews per place distribution
    place_counts = Counter([r["place_test_id"] for r in reviews])
    place_review_counts = list(place_counts.values())

    axes[0, 1].hist(place_review_counts, bins=max(place_review_counts), edgecolor='black', alpha=0.7, color='orange')
    axes[0, 1].set_title('Reviews Per Place Distribution')
    axes[0, 1].set_xlabel('Number of Reviews')
    axes[0, 1].set_ylabel('Number of Places')
    axes[0, 1].axvline(np.mean(place_review_counts), color='r', linestyle='--', label=f'Mean: {np.mean(place_review_counts):.1f}')
    axes[0, 1].legend()

    # 3. Rating distribution
    ratings = [r["fields"]["rating"] for r in reviews]
    rating_counts = Counter(ratings)

    axes[1, 0].bar(rating_counts.keys(), rating_counts.values(), edgecolor='black', alpha=0.7, color='green')
    axes[1, 0].set_title('Rating Distribution')
    axes[1, 0].set_xlabel('Rating (Stars)')
    axes[1, 0].set_ylabel('Number of Reviews')
    axes[1, 0].set_xticks([1, 2, 3, 4, 5])
    for rating, count in rating_counts.items():
        pct = (count / len(reviews)) * 100
        axes[1, 0].text(rating, count, f'{pct:.1f}%', ha='center', va='bottom')

    # 4. Price distribution
    prices = [r["fields"]["price"] for r in reviews if r["fields"].get("price") is not None]
    if prices:
        axes[1, 1].hist(prices, bins=20, edgecolor='black', alpha=0.7, color='purple')
        axes[1, 1].set_title('Price Distribution (KRW)')
        axes[1, 1].set_xlabel('Price')
        axes[1, 1].set_ylabel('Number of Reviews')
        axes[1, 1].axvline(np.mean(prices), color='r', linestyle='--', label=f'Mean: ₩{np.mean(prices):.0f}')
        axes[1, 1].axvline(np.median(prices), color='b', linestyle='--', label=f'Median: ₩{np.median(prices):.0f}')
        axes[1, 1].legend()
    else:
        axes[1, 1].text(0.5, 0.5, 'No price data', ha='center', va='center')
        axes[1, 1].set_title('Price Distribution (KRW)')

    # 5. Waiting time distribution
    wait_times = [r["fields"]["waiting_time_minutes"] for r in reviews if r["fields"].get("waiting_time_minutes") is not None]
    if wait_times:
        axes[2, 0].hist(wait_times, bins=15, edgecolor='black', alpha=0.7, color='red')
        axes[2, 0].set_title('Waiting Time Distribution (minutes)')
        axes[2, 0].set_xlabel('Waiting Time (min)')
        axes[2, 0].set_ylabel('Number of Reviews')
        axes[2, 0].axvline(np.mean(wait_times), color='b', linestyle='--', label=f'Mean: {np.mean(wait_times):.1f} min')
        axes[2, 0].legend()
    else:
        axes[2, 0].text(0.5, 0.5, 'No waiting time data', ha='center', va='center')
        axes[2, 0].set_title('Waiting Time Distribution')

    # 6. Dietary tags distribution
    tag_fields = ["is_vegan", "is_halal", "is_vegetarian", "is_spicy",
                  "is_gluten_free", "is_dairy_free", "is_nut_free"]

    tag_yes_percentages = []
    tag_labels = []
    for tag in tag_fields:
        tag_values = [r["fields"][tag] for r in reviews]
        yes_count = tag_values.count("yes")
        pct = (yes_count / len(reviews)) * 100
        tag_yes_percentages.append(pct)
        tag_labels.append(tag.replace('is_', '').replace('_', ' ').title())

    axes[2, 1].barh(tag_labels, tag_yes_percentages, edgecolor='black', alpha=0.7, color='teal')
    axes[2, 1].set_title('Dietary Tags - "Yes" Percentage')
    axes[2, 1].set_xlabel('Percentage (%)')
    axes[2, 1].set_xlim(0, 100)
    for i, (label, pct) in enumerate(zip(tag_labels, tag_yes_percentages)):
        axes[2, 1].text(pct + 2, i, f'{pct:.1f}%', va='center')

    plt.tight_layout()
    plt.show()

    # Print summary statistics
    print("=" * 60)
    print("REVIEW STATISTICS SUMMARY")
    print("=" * 60)
    print(f"Total reviews: {len(reviews)}")
    print(f"Unique places: {df_reviews['place_test_id'].nunique()}")
    print(f"Unique users: {len(user_counts)}")
    print(f"Reviews with images: {sum(1 for r in reviews if r.get('images'))}")
    print(f"\nAverage rating: {np.mean(ratings):.2f} stars")
    print(f"Average reviews per user: {np.mean(user_review_counts):.1f}")
    print(f"Average reviews per place: {np.mean(place_review_counts):.1f}")

    # Top contributors
    print(f"\nTop 3 reviewers:")
    for email, count in sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
        print(f"  {email}: {count} reviews")

    # Top reviewed places
    print(f"\nTop 3 reviewed places:")
    for place_id, count in sorted(place_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
        place_name = next((p["name"] for p in places if p["test_id"] == place_id), place_id)
        print(f"  {place_name}: {count} reviews")

    # Places without reviews
    places_without_reviews = [p for p in places if p["test_id"] not in place_counts]
    if places_without_reviews:
        print(f"\nPlaces without reviews ({len(places_without_reviews)}):")
        for place in places_without_reviews[:5]:  # Show first 5
            print(f"  - {place['name']}")
        if len(places_without_reviews) > 5:
            print(f"  ... and {len(places_without_reviews) - 5} more")

    # Optional fields coverage
    print(f"\nOptional field coverage:")
    print(f"  Text: {sum(1 for r in reviews if r['fields'].get('text'))}/{len(reviews)} ({sum(1 for r in reviews if r['fields'].get('text'))/len(reviews)*100:.1f}%)")
    print(f"  Price: {len(prices)}/{len(reviews)} ({len(prices)/len(reviews)*100:.1f}%)")
    print(f"  Waiting time: {len(wait_times)}/{len(reviews)} ({len(wait_times)/len(reviews)*100:.1f}%)")
    print(f"  Images: {sum(1 for r in reviews if r.get('images'))}/{len(reviews)} ({sum(1 for r in reviews if r.get('images'))/len(reviews)*100:.1f}%)")

    print("=" * 60)
