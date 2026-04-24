# Known run failures and their process-hygiene fixes

A running log of runs that crashed, hung, or were killed — what
happened, what was preserved, what the re-run needs. Kept in the repo
so a future operator (SBA, the assistant continuing this session, or
a new contributor) can reproduce or avoid the same failure.

Format per incident: date, scope, what happened, what was preserved,
re-run checklist.

---

## 2026-04-24 — Phase B B6 VA API noise-floor run: silent SIGKILL

### Scope

First Pillar 1 noise-floor run against the live Venture Assessment API
on the 8-case tryout corpus.
- Config: `/Users/sb/MyDev/kelvin-tryout/runs_0.2.1/real/kelvin.yaml`
  with `noise_floor.enabled: true, replications: 10` and
  `retry_policy: transient_exit_codes: [1], max_attempts: 3`
- Expected wall-clock: ~60-75 min for baseline + replay phase alone

### What happened

The process ran for ~47 minutes, completing baselines + 10-replay
noise-floor measurement for 4 of 8 cases:

| Case | σ_c | Replays | Baseline score |
|---|---:|---:|---:|
| `ai_dev_tool` | 0.1716 | 10 | 38 |
| `biotech_diagnostics` | 0.0982 | 10 | 66 |
| `content_solo_creator` | 0.0978 | 10 | 58 |
| `fintech_compliance` | 0.1847 | 10 | 69 |

On the 5th case (`hardware_climate`), the process hit 3 sequential
`retry_detected` events (transient exit-1 failures from the VA API
wrapper), then **went silent with no further output**. Process was
gone from `ps` ~3 minutes after the last event.

No Python traceback anywhere — neither in `runs_0.2.1/logs/
real_noise.log` (JSON) nor in the Bash-captured stdout+stderr output
at `/private/tmp/claude-501/.../bfr509iwc.output`. Last log event was
a normal `retry_detected` that would have been followed by a 1.2s
sleep then a retry attempt. Neither the subsequent retry nor a
`retry_giving_up` fired.

### Diagnosis

Silent external kill. Most likely causes (in rough order of
probability):

1. **macOS kernel OOM reaper** — silently terminates processes under
   memory pressure with no stderr output. The run had been spawning
   Python subprocesses at ~50-60s intervals for 47 minutes while
   parallel side-channel runs (constant/brittle/adversary for mid-
   run reporting) were firing additional short-lived Python
   interpreters from the same venv.
2. **System sleep / power state** — a laptop left idle for 47 min of
   mostly network-bound work may have gone to sleep; waking
   subprocesses can get killed.
3. **Unrelated watchdog / OS event** — e.g., a security update
   daemon, storage operation, or low-battery handler.

What we can rule out from the log:
- Not a Python exception (would have traceback on stderr; none
  present)
- Not a Kelvin-internal error path (all error paths emit a catalog
  message to the event logger first; no such event)
- Not a hang in urllib (would have hit wrapper's 90s timeout; that
  would emit a non-zero exit code and trigger retry logic visibly)

### What was preserved

- Full JSON event log: `/Users/sb/MyDev/kelvin-tryout/runs_0.2.1/
  logs/real_noise.log` (15 events)
- 4 cases' canonical baselines (cache hits on re-run):
  `/Users/sb/MyDev/kelvin-tryout/runs_0.2.1/cache_real/` — replays
  bypass cache by design so those are **not** preserved and must be
  re-measured
- Partial η = 0.1381 (mean of 4 σ_c values)
- Projected K_cal for VA API ≈ 1.110 (documented with n=4 caveat in
  `experiments/pillar1_va_api_partial.md`)

### Re-run checklist (for 0.3.0-rc1 verification run)

Before invoking the B6 re-run:

- [ ] **Wrap in `caffeinate -s`** to block the laptop from sleeping
      during the 60-75 min run:
      ```
      caffeinate -s kelvin check --log-format json 2> stderr.log | \
          tee runs/real_rerun.log
      ```
- [ ] **Redirect stderr to a separate file**, not `2>&1` into the
      same stream as stdout. A silent kill this time left no stderr;
      if next time there's a Python traceback or subprocess error,
      it must land somewhere inspectable. Command above uses
      `2> stderr.log`.
- [ ] **Run under `launchctl asuser` or a long-lived terminal
      session**, not a transient ssh / IDE subshell that might
      terminate the parent.
- [ ] **Close other Python tooling** and avoid parallel `kelvin
      check` side-channel runs from the same venv during the long
      run. If you need mid-run progress, tail the JSON log only;
      don't spin up additional kelvin invocations.
- [ ] **Check system free memory before starting** (`vm_stat` on
      macOS). Aim for >4 GB free.
- [ ] **Use `nohup`** so the process survives shell detachment:
      ```
      nohup caffeinate -s kelvin check --log-format json \
          > run.out 2> stderr.log &
      ```
- [ ] **Cache preserved from B6** — the 4 completed cases' canonical
      baselines will cache-hit. Only replays and remaining 4 cases
      cost fresh calls. Budget: ~40 fresh replay calls for the 4
      missing cases + up to ~30 calls of retries = ~30-45 min.
- [ ] **Expect ~80 fresh API calls** (from-scratch) or ~40 (with
      cache warm from B6). At $X per call (check current VA pricing)
      this is meaningful spend — the re-run is a scheduled paper-
      table item, not a casual iteration.

### Success gate

- `run_completed` event fires and `runs/real/kelvin/report.json` exists
- All 8 cases have σ_c measurements in the log
- No orphan `retry_detected` events (every one is followed either by
  another `retry_detected` at higher attempt or by `retry_giving_up`
  or by the case's `noise_floor_measured`)
- If final η differs from 0.1381 by >0.02, update
  `experiments/pillar1_va_api_partial.md` and whitepaper §5.3;
  specifically re-check whether K_cal remains measurable
  (η < 1 - Inv_raw = 0.164)
