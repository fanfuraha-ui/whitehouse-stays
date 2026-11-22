# Whitehouse Stays

*Stay • Relax • Feel at Home*

Website for Whitehouse Stays serviced apartments (Migori, Kisumu – Makasembo, Kisumu).
Single-file site, same format as the Nibbana Garden and Tulips Garden websites. Photos are served as WebP with JPEG fallback.
Guests choose a branch, dates and apartment, and the form opens WhatsApp with the booking message ready to send.

## What is in this repo
- `index.html` holds everything (HTML, CSS, JS). Edit the `CONFIG` object at the bottom of the script for phones, branches, apartments, prices, photos and the video.
- `images/` holds the photos and the video. `images/makasembo/` has the Kisumu – Makasembo gallery.
- `django-version/` is the earlier booking-system version (needs a server). It is not needed to host the website.

## Put it online
**GitHub Pages:** Settings, Pages, deploy from branch `main`, folder `/ (root)`.

**Any hosting provider (cPanel):** upload `index.html` and the `images` folder into `public_html`.

## To fill in
- Prices: set `price: "Ksh 3,500 / night"` on each apartment in `CONFIG` (empty means no price is shown).
- Photos for the Migori and Kisumu branches: set `photo:` on each branch in `CONFIG`.
- Directions for the Kisumu branch: set `map:`.
