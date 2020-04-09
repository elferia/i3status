from __future__ import annotations
from collections import namedtuple
from functools import partial
from itertools import chain, islice, repeat
import json
from numbers import Real
from operator import sub, truediv
from sys import stdin
from time import time
from typing import Any, Dict, Iterable, List, Sequence, TextIO, Tuple

import pynvml

ENERGY_PATH = '/sys/class/powercap/intel-rapl:0/energy_uj'
NET_STAT_PATH = '/proc/net/dev'

TDP = 54

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

    modified_status = list(
        chain.from_iterable(
            gpu_info(h, i) for i, h in enumerate(device_handles)))
    modified_status.extend(
        {'full_text': f'{s.interface} Rx: {s.receive.bytes / 1024:.1f} KiB/s '
         f'Tx: {s.transmit.bytes / 1024:.1f} KiB/s', 'name': s.interface
         } for s in net_diff if s.interface == 'enp3s0')
    old_netstat = new_netstat
    modified_status.append(
        dict(full_text=f'{power / 1_000_000:.1f} W / {TDP} W', name='power'))
    modified_status.extend(status)
    return modified_status


def gpu_info(gpu_handle, i: int = 0) -> List[Dict[str, Any]]:
    power = pynvml.nvmlDeviceGetPowerUsage(gpu_handle) / 1000
    temperature = pynvml.nvmlDeviceGetTemperature(
        gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
    free_memory = (
        pynvml.nvmlDeviceGetMemoryInfo(gpu_handle).free / 1024 / 1024 / 1024)
    return [
        dict(full_text=f'GPU Power {power:.1f} W', name=f'gpu{i}_power'),
        dict(full_text=f'GPU Temp {temperature} ℃', name=f'gpu{i}_temperature'),
        dict(full_text=f'GPU RAM {free_memory:.1f} GiB', name=f'gpu{i}_free_memory')]


_print(input())  # Skip the first line which contains the version header.
_print(input())  # The second line contains the start of the infinite array.

f = open(ENERGY_PATH, buffering=1)
old_energy = int(f.read())
old_time = time()
f_netstat = open(NET_STAT_PATH, buffering=1)
old_netstat = NetStat.load(f_netstat)
pynvml.nvmlInit()
device_handles = list(
    map(pynvml.nvmlDeviceGetHandleByIndex, range(pynvml.nvmlDeviceGetCount())))

for line in stdin:
    prefix = ',' if line.startswith(',') else ''
    status = json.loads(line.lstrip(','))
    _print(prefix, json.dumps(modify_status(status)), sep='')
