"""Locked search contract and deterministic comparison-count benchmark."""
import json
import runpy
from pathlib import Path
search = runpy.run_path('candidate.py')['search']
for items, target, expected in [([],1,-1),([1],1,0),([1,1,2],1,0),(list(range(80)),64,64),([1,3,5],4,-1)]:
    assert search(items,target) == expected, (items,target,expected)
class Counted:
    comparisons = 0
    def __init__(self, value): self.value = value
    def __lt__(self, other):
        Counted.comparisons += 1
        return self.value < other
    def __eq__(self, other):
        Counted.comparisons += 1
        return self.value == other
assert search([Counted(i) for i in range(1024)],1023) == 1023
Path('metric.json').write_text(json.dumps({'comparisons': Counted.comparisons}))
