"""Offline regression tests. All generated offers below are SYNTHETIC, not live data."""
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.error import HTTPError
from matpriskollen_mcp.core import (
    STORES, TTL_SECONDS, OfferService, SourceError, parse_page,
    normalize_offer, fetch_public_page, NoRedirect,
)

KEY = "hemkop_bredang"
NOW = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)


def synthetic_offer(number=1, **changes):
    offer = {"id": f"00000000-0000-0000-0000-{number:012d}", "storeKey": STORES[KEY]["uuid"],
             "title": "SYNTHETIC Äpple \"Grönt\"", "subtitle": "Test only", "priceLabel": "2 för 28,00",
             "volume": "700 g", "comprice": "20,00/kg", "category": "Frukt",
             "categories": [{"name": "Frukt", "parent_category": "Grönt"}],
             "condition": "$undefined", "productTags": [], "validFrom": int((NOW - timedelta(days=1)).timestamp()),
             "validTo": int((NOW + timedelta(seconds=30)).timestamp())}
    offer.update(changes)
    return offer


def synthetic_html(offers=None, count="auto", store_uuid=None, prefix="", split=False):
    if offers is None:
        offers = [synthetic_offer()]
    identity = {"id": store_uuid or STORES[KEY]["uuid"], "title": "SYNTHETIC STORE"}
    if count != "missing":
        identity["deals"] = len(offers) if count == "auto" else count
    payload = prefix + '4:' + json.dumps(["$", "component", None, {"initialStore": identity, "initialDeals": offers}], ensure_ascii=False) + '\n'
    chunks = [payload[:37], payload[37:]] if split else [payload]
    return '<html><!-- SYNTHETIC FIXTURE ONLY -->' + ''.join('<script>self.__next_f.push(' + json.dumps([1, x]) + ');</script>' for x in chunks) + '</html>'


class ParserTests(unittest.TestCase):
    def test_multibuy_unicode_and_chunking(self):
        result = parse_page(synthetic_html(split=True), KEY)
        offer = normalize_offer(result['source_deals'][0], 'source', NOW.isoformat(), NOW)
        self.assertEqual(offer['price_label'], '2 för 28,00')
        self.assertEqual(offer['volume'], '700 g')
        self.assertEqual(offer['comparison_price'], '20,00/kg')
        self.assertEqual(offer['title'], 'SYNTHETIC Äpple "Grönt"')
        self.assertIsNone(offer['membership_required'])
        self.assertIsNone(offer['condition'])
        self.assertIn('condition', offer['unknown_fields'])
        self.assertTrue(offer['valid_from'].endswith('+02:00'))

    def test_utf8_length_prefixed_text_not_instructions(self):
        text = 'ÄÖÅ\n4:{"initialDeals":[]}'
        prefix = f'1:T{len(text.encode()):x},' + text
        self.assertEqual(parse_page(synthetic_html(prefix=prefix), KEY)['deduplicated_count'], 1)

    def test_javascript_never_evaluated(self):
        with self.assertRaises(SourceError):
            parse_page('<script>self.__next_f.push(eval("evil"))</script>', KEY)

    def test_unsupported_flight_reference_fails(self):
        with self.assertRaises(SourceError):
            parse_page(synthetic_html([synthetic_offer(volume='$a')]), KEY)

    def test_redirected_or_wrong_store_data(self):
        with self.assertRaises(SourceError):
            parse_page(synthetic_html(store_uuid=STORES['ica_liljeholmen']['uuid']), KEY)
        with self.assertRaises(SourceError):
            parse_page(synthetic_html([synthetic_offer(storeKey='other')]), KEY)

    def test_missing_and_malformed_offer_fields(self):
        for updates in ({'title': ''}, {'id': 'not-a-uuid'}, {'priceLabel': 20}):
            with self.subTest(updates=updates), self.assertRaises(SourceError):
                parse_page(synthetic_html([synthetic_offer(**updates)]), KEY)

    def test_missing_optional_price_is_unknown(self):
        raw = synthetic_offer()
        del raw['priceLabel']
        offer = normalize_offer(parse_page(synthetic_html([raw]), KEY)['source_deals'][0], 'source', NOW.isoformat(), NOW)
        self.assertIsNone(offer['price_label'])
        self.assertIn('price_label', offer['unknown_fields'])

    def test_explicit_membership_not_guessed(self):
        raw = synthetic_offer(condition='Medlemspris. Max 2 köp/hushåll.')
        offer = normalize_offer(raw, 'source', NOW.isoformat(), NOW)
        self.assertEqual(offer['condition'], raw['condition'])
        self.assertIsNone(offer['membership_required'])
        raw['membershipRequired'] = True
        self.assertTrue(normalize_offer(raw, 'source', NOW.isoformat(), NOW)['membership_required'])

    def test_count_mismatch_fails(self):
        with self.assertRaisesRegex(SourceError, 'declared=2, parsed=1, unique=1'):
            parse_page(synthetic_html(count=2), KEY)

    def test_duplicate_counts_and_conflicts(self):
        raw = synthetic_offer()
        data = parse_page(synthetic_html([raw, raw], count=1), KEY)
        self.assertEqual((data['parsed_count'], data['deduplicated_count']), (2, 1))
        self.assertTrue(data['warnings'])
        with self.assertRaises(SourceError):
            parse_page(synthetic_html([raw, dict(raw, priceLabel='1,00')]), KEY)

    def test_missing_count_warns(self):
        data = parse_page(synthetic_html(count='missing'), KEY)
        self.assertIsNone(data['source_declared_count'])
        self.assertTrue(data['warnings'])

    def test_empty_requires_explicit_zero(self):
        self.assertEqual(parse_page(synthetic_html([], count=0), KEY)['deduplicated_count'], 0)
        for html in (synthetic_html([], count='missing'), synthetic_html([], count=3), '<html>Access denied</html>'):
            with self.assertRaises(SourceError):
                parse_page(html, KEY)

    def test_truncation_and_ambiguity(self):
        for html in (synthetic_html(prefix='1:Tffffff,short'), synthetic_html() + synthetic_html()):
            with self.assertRaises(SourceError):
                parse_page(html, KEY)

    def test_date_states_and_invalid_dates(self):
        raw = synthetic_offer()
        check = lambda r, now: normalize_offer(r, 'source', NOW.isoformat(), now)['validity_status']
        self.assertEqual(check(raw, NOW), 'within_source_date_window')
        self.assertEqual(check(raw, NOW + timedelta(seconds=31)), 'expired')
        self.assertEqual(check(raw, NOW - timedelta(days=2)), 'not_yet_valid')
        self.assertEqual(check(dict(raw, validFrom=None), NOW), 'unknown')
        self.assertEqual(check(dict(raw, validTo=None), NOW), 'unknown')
        for changes in ({'validTo': 'tomorrow'}, {'validTo': -100}, {'validTo': float('nan')}, {'validTo': True}):
            with self.subTest(changes=changes), self.assertRaises(SourceError):
                check(dict(raw, **changes), NOW)

    def test_malformed_category_data_refused(self):
        for categories in ('Frukt', [12], [{'name': 12}]):
            with self.subTest(categories=categories), self.assertRaises(SourceError):
                normalize_offer(synthetic_offer(categories=categories), 'source', NOW.isoformat(), NOW)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.now, self.mono, self.calls = NOW, 1.0, 0
        self.html = synthetic_html([synthetic_offer(), synthetic_offer(2, title='SYNTHETIC Bröd', category='Bageri', categories=[])])
        self.service = OfferService(self.fetch, lambda: self.now, lambda: self.mono)

    def fetch(self, key):
        self.calls += 1
        return self.html

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)
        self.mono += seconds

    def test_filter_pagination_exact_counts(self):
        page = self.service.get_offers(KEY, limit=1)
        self.assertEqual((page['total'], page['returned_count'], page['next_offset']), (2, 1, 1))
        last = self.service.get_offers(KEY, limit=1, offset=1)
        self.assertFalse(last['has_more'])
        self.assertNotEqual(last['offers'][0]['id'], page['offers'][0]['id'])
        self.assertEqual(self.service.get_offers(KEY, query='ÄPPLE', category='grönt')['total'], 1)
        self.assertEqual(self.service.get_offers(KEY, query='ÄPPLE', category='bageri')['total'], 0)
        self.assertEqual(self.service.get_offers(KEY, offset=100)['returned_count'], 0)
        self.assertEqual(self.calls, 1)

    def test_cache_ttl_boundary_and_validity_recomputed(self):
        first = self.service.get_offers(KEY)
        self.assertEqual(first['freshness']['status'], 'fetched_now')
        self.advance(31)
        cached = self.service.get_offers(KEY)
        self.assertEqual(cached['offers'][0]['validity_status'], 'expired')
        self.assertEqual(cached['freshness']['status'], 'cached_within_ttl')
        self.assertEqual(cached['freshness']['age_seconds'], 31)
        self.advance(TTL_SECONDS - 31)
        self.service.get_offers(KEY)
        self.assertEqual(self.calls, 2)

    def test_wall_clock_jump_invalidates_cache(self):
        self.service.get_offers(KEY)
        self.now += timedelta(hours=2)
        self.service.get_offers(KEY)
        self.assertEqual(self.calls, 2)

    def test_failure_no_stale_fallback_and_cooldown(self):
        self.service.get_offers(KEY)
        self.advance(TTL_SECONDS)
        self.html = '<html>blocked</html>'
        with self.assertRaises(SourceError):
            self.service.get_offers(KEY)
        with self.assertRaisesRegex(SourceError, 'Recent source failure'):
            self.service.get_offers(KEY)
        self.assertEqual(self.calls, 2)
        self.assertNotIn(KEY, self.service.cache)
        self.advance(61)
        self.html = synthetic_html()
        self.assertEqual(self.service.get_offers(KEY)['total'], 1)

    def test_validation_before_network(self):
        for kwargs in ({'store_id': 'https://evil.example'}, {'store_id': KEY, 'limit': 101}, {'store_id': KEY, 'limit': 0}, {'store_id': KEY, 'offset': -1}, {'store_id': KEY, 'query': 'x'*201}):
            with self.assertRaises(ValueError):
                self.service.get_offers(**kwargs)
        self.assertEqual(self.calls, 0)

    def test_return_values_cannot_mutate_cache(self):
        result = self.service.get_offers(KEY)
        result['offers'][0]['source_fields']['title'] = 'changed'
        result['offers'][0]['categories'][0]['name'] = 'changed'
        self.assertNotEqual(self.service.get_offers(KEY)['offers'][0]['title'], 'changed')
        self.assertEqual(self.service.get_offers(KEY)['offers'][0]['categories'][0]['name'], 'Frukt')

    def test_concurrent_calls_share_one_fetch(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.service.get_offers(KEY), range(16)))
        self.assertEqual(self.calls, 1)
        self.assertTrue(all(result['total'] == 2 for result in results))


class FetchTests(unittest.TestCase):
    def test_redirect_is_refused(self):
        with self.assertRaises(SourceError):
            NoRedirect().redirect_request(None, None, 302, 'redirect', {}, 'https://other.example')

    def test_http_block_no_retry(self):
        with patch('matpriskollen_mcp.core.build_opener') as opener:
            opener.return_value.open.side_effect = HTTPError('url', 403, 'Forbidden', {}, None)
            with self.assertRaisesRegex(SourceError, 'no retry'):
                fetch_public_page(KEY)
            self.assertEqual(opener.return_value.open.call_count, 1)

    def test_oversize_and_wrong_content_type(self):
        for oversized in (True, False):
            with patch('matpriskollen_mcp.core.build_opener') as opener:
                response = opener.return_value.open.return_value.__enter__.return_value
                response.status, response.url = 200, STORES[KEY]['source_url']
                response.headers.get_content_type.return_value = 'text/html' if oversized else 'application/json'
                response.read.return_value = b'x' * 4_000_001
                with self.assertRaises(SourceError):
                    fetch_public_page(KEY)


if __name__ == '__main__':
    unittest.main()
