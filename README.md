# Launch-Day Shape Pool — GTA VI Twitch CCU Forecast

![make.fun bounty](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)
![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/isanssss/gta6-ccu-forecast-v4/rank.svg)
![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/isanssss/gta6-ccu-forecast-v4/reward.svg)

Entry for the make.fun bounty [gta6-twitch-ccu-forecast-01](https://make.fun/bounty/gta6-twitch-ccu-forecast-01):
forecast, for each hour 2–24 of Grand Theft Auto VI's release day (2026-11-19 UTC),
five quantiles (5/25/50/75/95%) of the Twitch category's concurrent viewers,
given everything known at the end of hour 1.

## How it works

`main.py` (Python 3, standard library only) treats the case's past-launch
comparables as a shape library:

1. Each comparable's release day is reduced to log-ratios against its own
   hour-1 print, one value per hour.
2. Comparables whose research note affirmatively reports an early-access
   period before the standard release are set aside — their release-day
   curve is the shape of a fourth day of play, not of a launch day.
   Negated mentions ("no early access") and campaign-only previews do not
   exclude a comparable.
3. The rest are weighted by a Gaussian kernel on the log distance between
   hour-1 sizes (bandwidth 0.9), because launches of similar scale share an
   unlock-day shape.
4. Every hour's quantiles are read straight off the weighted empirical
   distribution of that hour's pooled log-ratios — no normal fit, so the
   tails are the pool's own — with the spread around the median scaled by
   0.95. If no comparable is usable, the forecast falls back to persistence
   with a widening spread, so the output is always well-formed.

The design was tuned by leave-one-out over the comparables and checked
against the four practice launches shipped in the competition kit; the
program itself is deterministic and runs in a fraction of a second per case.

## Running

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `*.in` case file in the input directory and writes one
`<id>.out` forecast per case to the output directory.

## License

MIT — see `LICENSE`.
