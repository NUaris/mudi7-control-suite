"""Offline tests with synthetic domain statistics only; no browsing history."""
import json
import os
from pathlib import Path
import sys

from lupa import LuaRuntime

lua = LuaRuntime(unpack_returned_tuples=True)
root = Path(__file__).parent
module = lua.execute((root / 'adguard-rankings.lua').read_text(encoding='utf-8'))
for count in (0, 1, 5, 6, 100):
    requested = [{f'query-{n}.example': 1000 - n} for n in range(count)]
    blocked = [{f'ad-{n}.example': 2000 - n} for n in range(count)]
    source = {'top_queried_domains': requested, 'top_blocked_domains': blocked,
              'num_dns_queries': 9999, 'num_blocked_filtering': 1234,
              'top_clients': [{'192.0.2.1': 888}], 'other': [[], {}, 'quote" backslash\\, ]']}
    raw = json.dumps(source, ensure_ascii=False)
    result = json.loads(module.limit(raw, 5))
    assert result['top_queried_domains'] == requested[:5]
    assert result['top_blocked_domains'] == blocked[:5]
    for key in ('num_dns_queries', 'num_blocked_filtering', 'top_clients', 'other'):
        assert result[key] == source[key]
    assert module.limit(module.limit(raw, 5), 5) == module.limit(raw, 5)
    if count <= 5:
        assert module.limit(raw, 5) == raw

raw = json.dumps({'top_queried_domains': [{f'escaped-"-{i},].example': i} for i in range(8)],
                  'top_blocked_domains': [], 'extra': {'nested': [1, 2, 3]}})
assert len(json.loads(module.limit(raw, 5))['top_queried_domains']) == 5
for raw in ('{}', '{"top_queried_domains":null}', '{"top_queried_domains":[{"example":1}'):
    assert module.limit(raw, 5) == raw
lua.execute('assert(load(...))', (root / 'mudi7-adguard-top-five.lua').read_text(encoding='utf-8'))
print('PASS: top-five only, zero/five/100 items, original order, unchanged totals/clients, empty arrays, escaped strings, idempotence, filter syntax')
