# MVP PLAYBOOK – ONE PAGE

Goal: autonomous red→green turn on simplest possible defect.

Run:

```bash
python mvp_loop.py --model gpt-4.1 --max-attempts 3
```

Expect:

```
Attempt 1 … FAIL
Attempt 2 … FAIL
Attempt 3 … SUCCESS 🎉
```

Safety:

* No shell or git invocations.
* All patches held in memory; original tree untouched.
* Loop exits 1 on failure so CI can gate.

Once `SUCCESS` observed and committed, flip the project switch:

```
echo "MVP_PROOF=done" >> cadence.conf
```

That unlocks POST_MVP epics in backlog.json.