"""Built-in photos and video for branches, served from /static/.

These are the defaults shown until staff upload their own pictures in /admin/:
a photo uploaded there (branch hero image or unit type photo) always takes priority.
Gallery items are listed in tour order: outside first, then living areas, kitchen, bedrooms.
"""

_MKS = "img/branches/kisumu-makasembo/"


def _photo(name, caption, w, h):
    return {
        "full": f"{_MKS}{name}.jpg",
        "thumb": f"{_MKS}{name}-sm.jpg",
        "caption": caption,
        "w": w,
        "h": h,
        "tall": h > w,
    }


BRANCH_MEDIA = {
    "kisumu-makasembo": {
        "cover": f"{_MKS}01-estate-entrance.jpg",
        "card": f"{_MKS}04-lounge-sm.jpg",
        # Shown on each apartment row, keyed by number of bedrooms.
        "units": {
            1: f"{_MKS}07-bedroom-sm.jpg",
            2: f"{_MKS}08-bedroom-blue-sm.jpg",
            3: f"{_MKS}09-bedroom-king-sm.jpg",
        },
        "gallery": [
            _photo("01-estate-entrance", "Makasembo Estate entrance", 640, 478),
            _photo("02-grounds-parking", "Estate grounds and parking", 640, 380),
            _photo("03-living-room", "Living room", 640, 478),
            _photo("04-lounge", "Lounge", 640, 478),
            _photo("05-kitchen-bar", "Kitchen and breakfast bar", 480, 640),
            _photo("06-kitchen", "Kitchen", 640, 369),
            _photo("07-bedroom", "Bedroom", 640, 478),
            _photo("08-bedroom-blue", "Bedroom", 640, 389),
            _photo("09-bedroom-king", "Bedroom", 480, 640),
            _photo("10-bedroom-double", "Bedroom", 480, 640),
        ],
        "video": {
            "src": f"{_MKS}apartment-tour.mp4",
            "poster": f"{_MKS}apartment-tour-poster.jpg",
        },
    },
}


def media_for(slug):
    return BRANCH_MEDIA.get(slug, {})
