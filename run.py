# pandas is imported inside main() so this module can be imported safely in test
_PANDAS_AVAILABLE = True
try:
    import pandas as pd  # noqa: F401
except Exception:
    _PANDAS_AVAILABLE = False
import argparse
import json
import os
from datetime import datetime
from urllib.parse import urlparse

# optional web checks (requests + bs4). Keep import optional so module is safe to import.
_WEBCHECK_AVAILABLE = True
try:
    import requests
    from bs4 import BeautifulSoup
except Exception:
    _WEBCHECK_AVAILABLE = False

# Keep a concise brand list for quick disqualification
BRAND_KEYWORDS = [
    "kajaria", "somany", "nitco", "varmora",
    "orientbell", "experience centre", "boutique", "infinity"
]


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def _compute_lead_score(row: dict) -> (int, str):
    """
    Compute a 0-100 lead score using available fields in `row`.
    Returns (score, reason_short).
    This is intentionally conservative and uses only fields commonly available
    from Google Maps scraping so the classifier is robust without extra site checks.
    """
    name = (row.get("business_name") or "").lower()
    rating = row.get("rating") or 0
    reviews = row.get("reviews") or 0
    has_website = bool(row.get("has_website"))
    website = (row.get("website") or "").strip()
    phone = (row.get("phone") or row.get("phone_number") or "").strip()
    photos = row.get("photos") or row.get("photo_count") or 0
    category = (row.get("category") or "").lower()

    # Disqualify known brand showrooms by name or by official brand domain
    for brand in BRAND_KEYWORDS:
        if brand in name:
            return 0, "DISQUALIFIED – Brand Showroom (name match)"
        if website and brand in website.lower():
            return 0, "DISQUALIFIED – Brand Showroom (website match)"

    # Strong offline presence disqualification
    if (not has_website) and rating >= 4.2 and reviews >= 50:
        return 0, "DISQUALIFIED – Strong Offline Presence"

    score = 0.0

    # Baseline: having a website is a strong positive signal
    if has_website:
        # base for having a website
        score += 10
        # run quick site checks (best-effort) to add site quality score (0-20)
        site_score = 0
        try:
            if website and _WEBCHECK_AVAILABLE:
                site_score, _ = quick_site_check(website)
        except Exception:
            site_score = 0

        # cap site score to 20 and add
        score += min(site_score, 20)

    # Rating (0-5) -> up to 20 points
    try:
        score += (float(rating) / 5.0) * 20
    except Exception:
        pass

    # Reviews -> up to 20 points (scaled, capped)
    try:
        reviews_val = float(reviews)
        reviews_score = min((reviews_val / 100.0) * 20.0, 20.0)
        score += reviews_score
    except Exception:
        pass

    # Phone/contact info
    if phone:
        score += 10

    # Photos presence (more photos often => active/engaged listing)
    try:
        photos_val = int(photos)
        photos_score = min((photos_val / 10.0) * 10.0, 10.0)
        score += photos_score
    except Exception:
        pass

    # Category relevance (tile/tile-shop related categories are good)
    if any(k in category for k in ["tile", "tiles", "ceramic"]):
        score += 10

    # Cap and normalize
    score = max(0.0, min(score, 100.0))

    return int(round(score)), "Score computed from maps signals"


def quick_site_check(url: str, timeout: int = 5) -> (int, dict):
    """
    Quick, best-effort homepage checks that return (score, details).
    Score ranges 0-20 and is a simple sum of heuristics:
      - HTTPS present: 4
      - viewport meta: 4
      - meta description: 3
      - contact link or mailto: 4
      - analytics snippet: 5

    If requests/bs4 not available or fetch fails, returns (0, {}).
    """
    details = {}
    if not _WEBCHECK_AVAILABLE or not url:
        return 0, details

    try:
        parsed = urlparse(url)
        score = 0
        if parsed.scheme == "https":
            score += 4

        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return 0, {"http_status": resp.status_code}

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        if soup.find("meta", attrs={"name": "viewport"}):
            score += 4

        if soup.find("meta", attrs={"name": "description"}):
            score += 3

        # contact link
        contact = False
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if "mailto:" in href or "contact" in href:
                contact = True
                break
        if contact:
            score += 4

        # analytics
        if "gtag(" in html or "analytics.js" in html or "ga('" in html or "google-analytics" in html:
            score += 5

        details = {"site_score": score}
        return int(round(min(score, 20))), details
    except Exception as e:
        return 0, {"error": str(e)}


def classify_lead(row: dict):
    """
    New classifier that returns (lead_type, classification_reason, lead_score).
    Uses `_compute_lead_score` and simple thresholds. The function is safe to
    import (it doesn't trigger scraping) so tests can import and run it.
    """
    score, reason = _compute_lead_score(row)

    if score == 0 and reason.startswith("DISQUALIFIED"):
        # Already a disqualifier
        return (reason, reason, score)

    if score >= 70:
        category = "PURSUE – High Priority"
        explanation = f"High opportunity (score={score}). {reason}"
    elif score >= 40:
        category = "POTENTIAL – Medium Priority"
        explanation = f"Medium opportunity (score={score}). {reason}"
    else:
        category = "LOW – Low Priority"
        explanation = f"Low opportunity (score={score}). {reason}"

    return (category, explanation, score)


def main():
    # Accept dynamic inputs via CLI. Primary input is a JSON file listing jobs.
    parser = argparse.ArgumentParser(
        description="Scrape Google Maps and classify leads. Primary input: a JSON file containing search jobs."
    )
    parser.add_argument("--config", default="searches.json",
                        help="Path to JSON file with search jobs (default: searches.json)")
    # Keep a fallback single-search interface (optional)
    parser.add_argument("--search", help="Full search string to send to Google Maps (overrides JSON)")
    parser.add_argument("--query", help="Search query (e.g. 'tiles shop')")
    parser.add_argument("--city", help="City or location to narrow the search")
    parser.add_argument("--scrolls", type=int, default=5, help="Number of scrolls to perform in the results panel")
    parser.add_argument("--output", help="CSV output path (overrides config OUTPUT_FILE)")
    parser.add_argument("--debug", action="store_true", help="Write per-job debug JSON with website candidates and rejection reasons")
    args = parser.parse_args()

    # If the config JSON exists and is non-empty, prefer it. Otherwise fallback to CLI args.
    jobs = []
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
                # Expecting either a list of jobs or a single job object
                if isinstance(payload, list):
                    jobs = payload
                elif isinstance(payload, dict):
                    jobs = [payload]
        except Exception as e:
            print(f"Error reading config {args.config}: {e}")

    # If no jobs loaded from JSON, use CLI args to build one job
    if not jobs:
        if args.search:
            search_query = args.search
        else:
            q = args.query or "tiles shop"
            c = args.city or "jaipur"
            search_query = f"{q} in {c}" if c else q

        jobs = [{
            "search": search_query,
            "scrolls": args.scrolls,
            "output": args.output or None
        }]

    print(f"Loaded {len(jobs)} job(s) from {args.config if jobs and os.path.exists(args.config) else 'CLI'}")

    # Expand jobs: support multi-category single-city and multi-city same-category patterns.
    def expand_jobs(raw_jobs):
        expanded = []
        for job in raw_jobs:
            cats = job.get('categories') or job.get('category_list')
            cities = job.get('cities') or job.get('city_list')

            # both lists provided -> cartesian product (category x city)
            if cats and cities:
                for cat in cats:
                    for city in cities:
                        new = dict(job)
                        # remove list fields to avoid re-processing
                        new.pop('categories', None)
                        new.pop('category_list', None)
                        new.pop('cities', None)
                        new.pop('city_list', None)
                        new['query'] = cat
                        new['city'] = city
                        expanded.append(new)
                continue

            # multi-category, single city
            if cats:
                city = job.get('city') or job.get('city_name')
                if city:
                    for cat in cats:
                        new = dict(job)
                        new.pop('categories', None)
                        new.pop('category_list', None)
                        new['query'] = cat
                        new['city'] = city
                        expanded.append(new)
                else:
                    # no city provided: treat each category as independent search string
                    for cat in cats:
                        new = dict(job)
                        new.pop('categories', None)
                        new.pop('category_list', None)
                        new['search'] = cat
                        expanded.append(new)
                continue

            # multi-city, same category/query
            if cities:
                q = job.get('query') or job.get('category') or job.get('search')
                if q:
                    for city in cities:
                        new = dict(job)
                        new.pop('cities', None)
                        new.pop('city_list', None)
                        new['query'] = q
                        new['city'] = city
                        expanded.append(new)
                else:
                    for city in cities:
                        new = dict(job)
                        new.pop('cities', None)
                        new.pop('city_list', None)
                        new['search'] = (job.get('search') or '') + f" in {city}"
                        expanded.append(new)
                continue

            # default: pass-through
            expanded.append(job)
        return expanded

    jobs = expand_jobs(jobs)

    # Import scraper and config here so the module can be safely imported for tests
    try:
        # when run as a script inside the lead_scraper folder
        from scraper.maps_scraper import scrape_google_maps
    except Exception:
        # when imported as a package (lead_scraper.run)
        from .scraper.maps_scraper import scrape_google_maps

    if args.output:
        OUTPUT = args.output
    else:
        try:
            from config import OUTPUT_FILE
            OUTPUT = OUTPUT_FILE
        except Exception:
            from .config import OUTPUT_FILE
            OUTPUT = OUTPUT_FILE

    # Prepare data folder and accumulator for aggregated positive leads
    base_dir = os.path.dirname(__file__)
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    all_results = []

    # Process each job from the JSON / CLI
    for job in jobs:
        # job can supply: search (full), or query+city; scrolls; output
        if job.get("search"):
            search_query = job.get("search")
        else:
            q = job.get("query") or job.get("q") or "tiles shop"
            c = job.get("city") or "jaipur"
            search_query = f"{q} in {c}" if c else q

        scrolls = int(job.get("scrolls") or job.get("scroll") or args.scrolls)

        # determine output path (place job outputs in data folder unless an absolute path provided)
        if job.get("output"):
            out_path = job.get("output")
        elif args.output:
            out_path = args.output
        else:
            # generate filename from query+city+timestamp
            safe = (search_query.replace(" ", "_").replace('/', '_'))
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            out_path = f"leads_{safe}_{ts}.csv"

        # if out_path not absolute, ensure it goes into data_dir
        if not os.path.isabs(out_path):
            out_path = os.path.join(data_dir, out_path)

        print(f"🔍 Running job: '{search_query}' (scrolls={scrolls}) -> {out_path}")

        data = scrape_google_maps(search_query, scrolls=scrolls)
        df = pd.DataFrame(data)

        # Ensure we can apply classifier even if some keys missing
        df = df.fillna(value={
            "business_name": "",
            "rating": 0,
            "reviews": 0,
            "has_website": False,
            "website": "",
            "phone": "",
            "photos": 0,
            "category": "",
        })

        # classify_lead returns a tuple (lead_type, explanation, score) per row.
        classified = df.apply(lambda r: pd.Series(classify_lead(r)), axis=1)
        classified.columns = ["lead_type", "classification_reason", "lead_score"]
        df = pd.concat([df.reset_index(drop=True), classified.reset_index(drop=True)], axis=1)

        df.to_csv(out_path, index=False)

        print(f"✅ Leads saved to {out_path}")
        print(df.head())

        # If debug requested, produce a JSON with candidate URLs and simple rejection reasons
        if args.debug:
            debug_list = []
            for _, row in df.iterrows():
                candidates = row.get('website_candidates') if 'website_candidates' in row else []
                if isinstance(candidates, str):
                    # sometimes pandas serializes list to string; try to evaluate simple repr
                    try:
                        import ast
                        candidates = ast.literal_eval(candidates)
                    except Exception:
                        candidates = [candidates]

                candidate_reasons = []
                for c in (candidates or []):
                    reason = 'accepted' if _valid_website_href(str(c)) else 'rejected'
                    # more detailed reasons
                    try:
                        p = urlparse(str(c))
                        dom = p.netloc.lower()
                        if any(b in dom for b in ['fonts.gstatic.com','gstatic.com','googleusercontent.com']):
                            reason = 'rejected: google/static asset domain'
                        elif any(str(c).lower().endswith(ext) for ext in ['.woff','.woff2','.ttf','.svg','.css','.js']):
                            reason = 'rejected: asset file'
                        elif 'google.com' in dom and p.path.startswith('/url'):
                            reason = 'redirect: google.com/url'
                    except Exception:
                        pass
                    candidate_reasons.append({'candidate': c, 'reason': reason})

                debug_list.append({
                    'business_name': row.get('business_name'),
                    'website': row.get('website'),
                    'candidates': candidate_reasons
                })

            debug_path = os.path.join(data_dir, f"debug_{os.path.basename(out_path)}.json")
            try:
                with open(debug_path, 'w', encoding='utf-8') as fh:
                    json.dump(debug_list, fh, ensure_ascii=False, indent=2)
                print(f"🪵 Debug written to {debug_path}")
            except Exception as e:
                print(f"Failed to write debug file: {e}")

        # accumulate for aggregated positive leads (lead_score > 10)
        all_results.append(df)

    # After all jobs, combine results and write Leads.csv containing only positive-scoring leads
    try:
        if all_results:
            combined = pd.concat(all_results, ignore_index=True)
            # Ensure lead_score column numeric
            combined['lead_score'] = pd.to_numeric(combined['lead_score'], errors='coerce').fillna(0)
            positive = combined[combined['lead_score'] > 10]
        else:
            positive = pd.DataFrame()

        leads_out = os.path.join(data_dir, 'Leads.csv')
        positive.to_csv(leads_out, index=False)
        print(f"✅ Aggregated positive leads (>10) saved to {leads_out} (count={len(positive)})")
    except Exception as e:
        print(f"Error while aggregating positive leads: {e}")


if __name__ == "__main__":
    main()
