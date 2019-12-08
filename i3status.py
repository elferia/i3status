from __future__ import annotations
from collections import namedtuple
from functools import partial
from itertools import islice, repeat
import json
from numbers import Real
from operator import sub, truediv
from sys import stdin
from time import time
from typing import Any, Iterable, List, Sequence, TextIO, Tuple

ENERGY_PATH = '/sys/class/powercap/intel-rapl:0/energy_uj'
NET_STAT_PATH = '/proc/net/dev'

_print = partial(print, flush=True)

Transmit = namedtuple(
    'Transmit', 'bytes packets errs drop fifo colls carrier compressed')
Receive = namedtuple(
    'Receive', 'bytes packets errs drop fifo frame compressed multicast')


class NetStat:
    @classmethod
    def load(cls, f: TextIO) -> Tuple[NetStat]:
        f.seek(0)
        return tuple(map(cls, islice(f, 2, None)))

    def __init__(self, line: str = None) -> None:
        if line is not None:
            cells = iter(line.split())
            self.interface = next(cells).rstrip(':')
            self.receive = Receive._make(map(
                int, islice(cells, len(Receive._fields))))
            self.transmit = Transmit._make(map(int, cells))

    @staticmethod
    def diff(
        b: Iterable[NetStat], a: Iterable[NetStat], timedelta: float
    ) -> Iterable[NetStat]:
        return map(truediv, map(sub, b, a), repeat(timedelta))

    def __sub__(self, other: Any) -> NetStat:
        if isinstance(other, NetStat):
            result = NetStat()
            result.interface = self.interface
            result.receive = Receive._make(
                map(sub, self.receive, other.receive))
            result.transmit = Transmit._make(
                map(sub, self.transmit, other.transmit))
            return result
        return NotImplemented

    def __truediv__(self, other: Any) -> NetStat:
        if isinstance(other, Real):
            result = NetStat()
            result.interface = self.interface
            result.receive = Receive._make(
                map(truediv, self.receive, repeat(other)))
            result.transmit = Transmit._make(
                map(truediv, self.transmit, repeat(other)))
            return result
        return NotImplemented


def modify_status(status: Sequence[Any]) -> List[Any]:
    global old_energy, old_time, old_netstat
    f.seek(0)
    new_energy = int(f.read())
    new_time = time()
    power = (new_energy - old_energy) / (new_time - old_time)
    new_netstat = NetStat.load(f_netstat)
    net_diff = NetStat.diff(new_netstat, old_netstat, new_time - old_time)
    old_energy, old_time = new_energy, new_time
    modified_status = [
        {'full_text': f'{s.interface} Rx: {s.receive.bytes / 1024:.2f} KiB/s '
         f'Tx: {s.transmit.bytes / 1024:.2f} KiB/s', 'name': s.interface
         } for s in net_diff]
    old_netstat = new_netstat
    modified_status.append(
        dict(full_text=f'{power / 1_000_000:.2f} W', name='power'))
    modified_status.extend(status)
    return modified_status


_print(input())  # Skip the first line which contains the version header.
_print(input())  # The second line contains the start of the infinite array.

f = open(ENERGY_PATH, buffering=1)
old_energy = int(f.read())
old_time = time()
f_netstat = open(NET_STAT_PATH, buffering=1)
old_netstat = NetStat.load(f_netstat)

for line in stdin:
    prefix = ',' if line.startswith(',') else ''
    status = json.loads(line.lstrip(','))
    _print(prefix, json.dumps(modify_status(status)), sep='')
