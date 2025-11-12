def get_img_index():
    return {
        "generic-pizza": [
            "img_local/generic-pizza-1.jpg",
            "img_local/generic-pizza-2.jpg",
            "img_local/generic-pizza-3.jpg",
        ],
        "generic-burger": [
            "img_local/generic-burger-1.jpg",
            "img_local/generic-burger-2.jpg",
        ],
        "generic-cafe": [
            "img_local/generic-cafe-1.jpg",
            "img_local/generic-cafe-2.jpg",
        ],
        "generic-chicken": [
            "img_local/generic-chicken-1.jpg",
            "img_local/generic-chicken-2.jpg",
        ],
        "generic-korean-bbq": [
            "img_local/generic-korean-bbq-1.jpg",
            "img_local/generic-korean-bbq-2.jpg",
        ],

    }

def get_places():
    """
    AI GENERATED TEST DATA FOR PLACES
    """
    img_index = get_img_index()

    return [
        {
            "name": "KAIST Duck Pond Cafe",
            "address": "291 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3714,
            "longitude": 127.3650,
            "test_id": "kaist-duck-pond-cafe",
            "images": img_index["generic-cafe"],
        },
        {
            "name": "Bon Juk Korean Restaurant",
            "address": "193 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3685,
            "longitude": 127.3590,
            "test_id": "bon-juk-restaurant",
        },
        {
            "name": "Subway KAIST Station",
            "address": "335 Gwahak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3742,
            "longitude": 127.3688,
            "test_id": "subway-kaist",
        },
        {
            "name": "Mom's Touch Chicken",
            "address": "217 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3695,
            "longitude": 127.3605,
            "test_id": "moms-touch-chicken",
            "images": img_index["generic-chicken"],
        },
        {
            "name": "Gongcha Bubble Tea",
            "address": "201 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3690,
            "longitude": 127.3598,
            "test_id": "gongcha-bubbletea",
        },
        {
            "name": "Caffe Bene KAIST",
            "address": "291 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3720,
            "longitude": 127.3655,
            "test_id": "caffe-bene-kaist",
        },
        {
            "name": "Kyochon Chicken",
            "address": "225 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3700,
            "longitude": 127.3612,
            "test_id": "kyochon-chicken",
        },
        {
            "name": "Paris Baguette KAIST",
            "address": "195 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3688,
            "longitude": 127.3593,
            "test_id": "paris-baguette-kaist",
        },
        {
            "name": "BBQ Chicken Daehak",
            "address": "209 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3693,
            "longitude": 127.3602,
            "test_id": "bbq-chicken-daehak",
        },
        {
            "name": "Burger King KAIST",
            "address": "305 Gwahak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3730,
            "longitude": 127.3670,
            "test_id": "burger-king-kaist",
            "images": img_index["generic-burger"],
        },
        {
            "name": "Twosome Place Coffee",
            "address": "213 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3698,
            "longitude": 127.3608,
            "test_id": "twosome-place",
        },
        {
            "name": "Pizza School",
            "address": "189 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3682,
            "longitude": 127.3585,
            "test_id": "pizza-school",
            "images": img_index["generic-pizza"],
        },
        {
            "name": "Starbucks KAIST Campus",
            "address": "291 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3716,
            "longitude": 127.3652,
            "test_id": "starbucks-kaist",
        },
        {
            "name": "Korean BBQ House Samgyeopsal",
            "address": "221 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3702,
            "longitude": 127.3615,
            "test_id": "samgyeopsal-house",
            "images": img_index["generic-korean-bbq"],
        },
        {
            "name": "Angel-in-us Coffee",
            "address": "197 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3686,
            "longitude": 127.3595,
            "test_id": "angelinus-coffee",
        },
        {
            "name": "Lotteria Fast Food",
            "address": "205 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3692,
            "longitude": 127.3600,
            "test_id": "lotteria-fastfood",
        },
        {
            "name": "Kimbap Heaven",
            "address": "185 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3680,
            "longitude": 127.3582,
            "test_id": "kimbap-heaven",
        },
        {
            "name": "Tom N Toms Coffee",
            "address": "229 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3705,
            "longitude": 127.3618,
            "test_id": "tom-n-toms",
        },
        {
            "name": "Ediya Coffee Shop",
            "address": "191 Daehak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3684,
            "longitude": 127.3588,
            "test_id": "ediya-coffee",
        },
        {
            "name": "Domino's Pizza KAIST",
            "address": "311 Gwahak-ro, Yuseong-gu, Daejeon",
            "latitude": 36.3735,
            "longitude": 127.3675,
            "test_id": "dominos-pizza-kaist",
        },
    ]
