import pytest
import sys
sys.path.insert(0, '/Users/prashukjain/Desktop')
from lead_scraper import run as run_mod


def test_brand_disqualifier():
    row = {'business_name': 'Kajaria Tiles Jaipur', 'rating': 4.0, 'reviews': 10, 'has_website': False}
    lead_type, reason, score = run_mod.classify_lead(row)
    assert 'DISQUALIFIED' in lead_type


def test_strong_offline_disqualifier():
    row = {'business_name': 'Some Local Store', 'rating': 4.3, 'reviews': 60, 'has_website': False}
    lead_type, reason, score = run_mod.classify_lead(row)
    assert 'DISQUALIFIED' in lead_type


def test_site_score_integration(monkeypatch):
    # ensure quick_site_check is used and influences score
    def fake_quick(url):
        return (15, {'note': 'fake'})

    monkeypatch.setattr(run_mod, 'quick_site_check', fake_quick)

    row = {'business_name': 'Local Tiles', 'rating': 4.0, 'reviews': 20, 'has_website': True, 'website': 'https://example.com'}
    lead_type, reason, score = run_mod.classify_lead(row)
    # base: has_website 10 + site 15 + rating component (~16) + reviews (~4) => should be >40
    assert score >= 40
