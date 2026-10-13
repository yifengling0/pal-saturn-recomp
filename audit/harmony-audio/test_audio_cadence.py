#!/usr/bin/env python3
"""Deterministic source FIFO model, not an OHOS device/SDL-thread test.
Time is in 1/44100 second units, so 735/VB and 4096/pull are exact.
The real producer's smaller chunks are aggregated to 60Hz for this experiment.
SDL mixer silence is counted separately; never added to the source FIFO.
"""
import heapq
import json
import random
from fractions import Fraction
from pathlib import Path

RATE, CHUNK, QUANTUM, PRIME, CAP = 44100, 735, 4096, 4410, 11025

def simulate(*, phase=0, jitter=0, seed=0, prime=PRIME, burst=1,
             producer_period=CHUNK, pauses=(), reset_every=0, device_rate=44100):
    quantum = Fraction(4096*RATE, device_rate)
    duration = 60*RATE
    rng = random.Random(seed)
    events = []
    def paused(t):
        return any(a <= t < b for a,b in pauses)
    # During a host menu both PCM production and stream consumption stop.
    # Shift producer timebase, but preserve downstream pull phase at resume.
    n = 1
    t = CHUNK
    delay = 0
    previous = 0
    while t < duration:
        at = t + rng.randrange(jitter+1)
        if reset_every and n % reset_every == 0:
            delay += 101*RATE//1000
        at += delay
        for a,b in pauses:
            if at >= a:
                at += b-a
        at = max(previous, at)  # one producer, delayed chunks never reorder
        previous = at
        if at < duration: heapq.heappush(events,(at,1,CHUNK))
        n += 1
        t = n*producer_period
    for i in range(burst): heapq.heappush(events,(phase,0,quantum))
    t = phase+quantum
    while t < duration:
        if not paused(t): heapq.heappush(events,(t,0,quantum))
        t += quantum
    queued = prime
    accepted = dropped = pulled = silence = shortages = late_shortages = 0
    low,high = prime,prime
    for t,kind,frames in iter(lambda: heapq.heappop(events) if events else None,None):
        if kind:
            if queued+frames > CAP: dropped += frames
            else: queued += frames; accepted += frames
        else:
            take=min(queued,frames)
            queued-=take; pulled+=take
            missed=frames-take
            silence+=missed
            shortages+=bool(missed)
            late_shortages+=bool(missed and t >= 10*RATE)
        low=min(low,queued);high=max(high,queued)
        assert 0 <= queued <= CAP
        assert prime+accepted == pulled+queued
    return dict(short_calls=shortages,after_10s_short_calls=late_shortages,
                mixer_silence_frames=float(silence),dropped_real_frames=dropped,
                accepted_real_frames=accepted,source_min=float(low),source_max=float(high))

def main():
    phase_cases=[simulate(phase=p) for p in range(0,CHUNK,7)]
    margin_cases=[simulate(phase=p,prime=QUANTUM+CHUNK) for p in range(0,CHUNK,7)]
    assert max(x['mixer_silence_frames'] for x in phase_cases)>0
    assert all(x['mixer_silence_frames'] <= QUANTUM+CHUNK-PRIME for x in phase_cases)
    assert all(x['short_calls']==0 for x in margin_cases)
    assert all(x['dropped_real_frames']==0 for x in phase_cases+margin_cases)
    jitter_cases=[simulate(phase=p,jitter=j,seed=p) for p in range(0,CHUNK,21) for j in (882,1764)]
    assert all(x['dropped_real_frames']==0 for x in jitter_cases)
    bursts=[simulate(burst=n) for n in (1,2,3)]
    assert bursts[2]['mixer_silence_frames']>bursts[0]['mixer_silence_frames']
    assert all(x['mixer_silence_frames'] <= i*QUANTUM+CHUNK-PRIME for i,x in enumerate(bursts,1))
    menus=[simulate(phase=p,pauses=((10*RATE,12*RATE+441), (30*RATE,31*RATE+999))) for p in range(0,CHUNK,21)]
    assert all(x['dropped_real_frames']==0 for x in menus)
    candidates = [simulate(phase=p, prime=(4096*RATE+r-1)//r+882,
                           jitter=100, device_rate=r) for r in (44100,48000) for p in range(0,CHUNK,7)]
    assert all(x['short_calls']==0 and x['dropped_real_frames']==0 for x in candidates)
    candidate_menus = [simulate(phase=p, prime=4978, pauses=((10*RATE,12*RATE+441),
                                (30*RATE,31*RATE+999))) for p in range(0,CHUNK,21)]
    assert all(x['short_calls']==0 and x['dropped_real_frames']==0 for x in candidate_menus)
    slow=simulate(producer_period=CHUNK+1)
    rebases=simulate(reset_every=300)
    assert slow['after_10s_short_calls']>0 and rebases['after_10s_short_calls']>0
    def envelope(xs):
        return {k:{'min':min(x[k] for x in xs),'max':max(x[k] for x in xs)} for k in xs[0]}
    result=dict(scope=__doc__,phase_sweeps=len(phase_cases),
                baseline=envelope(phase_cases), quantum_plus_one_tick=envelope(margin_cases),
                bounded_20_40ms_jitter=envelope(jitter_cases), startup_bursts=bursts,
                menu_phase_resume=envelope(menus), bounded_quantum_plus_20ms=envelope(candidates),
                candidate_menu_resume=envelope(candidate_menus), sustained_0_136percent_slow=slow,
                repeated_101ms_producer_clock_rebase=rebases)
    print(json.dumps(result,indent=2))
    Path(__file__).with_name('cadence-results.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__': main()
