from functools import partial
import json
from sys import stdin
from time import time
from typing import List, Any, Sequence

ENERGY_PATH = '/sys/class/powercap/intel-rapl:0/energy_uj'

_print = partial(print, flush=True)


def modify_status(status: Sequence[Any]) -> List[Any]:
    global old_energy, old_time
    f.seek(0)
    new_energy = int(f.read())
    new_time = time()
    power = (new_energy - old_energy) / (new_time - old_time)
    old_energy, old_time = new_energy, new_time
    return [
        dict(full_text=f'{power / 1_000_000:.2f} W', name='power')
    ] + list(status)


_print(input())  # Skip the first line which contains the version header.
_print(input())  # The second line contains the start of the infinite array.

f = open(ENERGY_PATH, buffering=1)
old_energy = int(f.read())
old_time = time()

for line in stdin:
    prefix = ',' if line.startswith(',') else ''
    status = json.loads(line.lstrip(','))
    _print(prefix, json.dumps(modify_status(status)), sep='')
