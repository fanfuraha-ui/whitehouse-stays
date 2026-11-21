# Whitehouse Airbnb — Direct Booking Website

*Stay • Relax • Feel at Home*

Direct-booking site for Whitehouse Airbnb's three branches (Migori, Kisumu – Makasembo, Kisumu).
Guests pick a branch, dates and a 1/2/3-bedroom type, pay with M-Pesa or card via Paystack,
and get an instant confirmation plus a branded PDF invoice. Staff run everything from `/admin/`.

## Stack
- Django 5 + PostgreSQL 16 (double bookings blocked by a database `ExclusionConstraint`)
- Server-rendered templates, one ~6 KB stylesheet, no JS framework (fast on 3G)
- Paystack (M-Pesa + cards), WeasyPrint (invoices), iCal import/export (Airbnb, Booking.com)
- Docker Compose: `web` (gunicorn), `scheduler` (holds + iCal sync), `db`, `caddy` (auto HTTPS)

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Postgres running locally with db/user/password "whitehouse" (or set POSTGRES_* env vars)
export DJANGO_DEBUG=1
python manage.py makemigrations properties bookings   # first time only — commit the results
python manage.py migrate
python manage.py seed_branches        # 3 branches + 1/2/3BR types with placeholder rates
python manage.py createsuperuser
python manage.py runserver
```
Then in `/admin/`: add **Units** under each unit type, upload photos, set real rates.

> Migration order matters: `bookings/migrations/0001_btree_gist.py` enables the `btree_gist`
> extension before the model migration that adds the no-overlap constraint.

## Deploy (single VPS)
```bash
cp .env.example .env    # fill in domain, secrets, Paystack keys, SMTP
docker compose up -d --build
docker compose exec web python manage.py seed_branches
docker compose exec web python manage.py createsuperuser
```
Point the domain's A record at the server first so Caddy can get the HTTPS certificate.

**Paystack dashboard → Settings → API Keys & Webhooks**
- Webhook URL: `https://<domain>/payments/paystack/webhook/`
- Callback URL is sent per transaction (`/payments/return/`)

**Backups:** nightly `docker compose exec -T db pg_dump -U whitehouse whitehouse | gzip > backup-$(date +%F).sql.gz`, copied off-server (e.g. S3).

## How booking works
1. Guest searches a branch → sees each unit type with price and how many are left
2. Checkout creates a **15-minute hold** on one auto-assigned unit
3. Paystack checkout (M-Pesa prompt or card)
4. Confirmation arrives two ways (redirect + webhook); both are idempotent
5. Booking → CONFIRMED, invoice PDF generated and emailed

Edge cases: lost races try the next unit; a payment that lands after its hold expired is re-placed
on any free unit of the same type, otherwise flagged ⚠ in admin for refund; amount mismatches are
flagged; failed payments release the hold immediately.

## Calendar sync
- **Export:** each unit has a private `.ics` URL (shown in admin) → paste into Airbnb / Booking.com
- **Import:** add the platform's `.ics` URL as a *Calendar feed* on the unit; synced every 15 minutes
- iCal is not instant. Imported overlaps that clash with an existing booking are flagged ⚠

## Before go-live (existing business)
- [ ] Enter every existing future booking (walk-in/phone/Airbnb) in admin
- [ ] Staff log every walk-in in admin — the database can only block what it knows about
- [ ] Real rates, photos, units, landmarks for each branch
- [ ] Paystack live keys + webhook; one real KES 10 test payment and refund
- [ ] Cancellation policy and house rules page
- [ ] Google Business Profile per branch, linking to its `/stays/<branch>/` page

## Open decisions
Second Kisumu branch landmark · deposit vs full payment · cancellation policy · VAT/levy (`TAX_RATE`) · which units are on Airbnb/Booking.com
