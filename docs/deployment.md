# Deployment notes

Operational notes for running the Hermes gateway + dashboard as a managed
service. Companion to the leak-prevention work in PR #1 (worker/PTY/fd reaping);
this covers the OS-level limits that bound the blast radius.

## macOS (launchd): open-file limit

launchd starts services with a **soft `NumberOfFiles` limit of 256**. The
dashboard's slash-command workers and PTY children each consume several file
descriptors, so a busy or leaky session could exhaust the cap and wedge the
gateway (#24775).

The generated `ai.hermes.gateway` plist raises this:

```xml
<key>SoftResourceLimits</key>
<dict><key>NumberOfFiles</key><integer>8192</integer></dict>
<key>HardResourceLimits</key>
<dict><key>NumberOfFiles</key><integer>16384</integer></dict>
```

Child processes (slash workers, PTY-hosted TUIs) inherit the limit — there is a
single gateway plist, no separate dashboard service. Existing installs pick the
new limit up automatically: `launchd_plist_is_current()` detects the limit-less
plist as stale and `run_gateway()` rewrites it on the next boot (no manual
`hermes update` required).

Verify the running limit:

```sh
launchctl limit maxfiles                  # system defaults
cat /proc/$(pgrep -f hermes_cli.main)/limits 2>/dev/null   # Linux equivalent
```

## Linux (systemd): worker reaping at stop

The user unit ships `KillMode=mixed`, which sends SIGTERM to the main process
and then **SIGKILLs the entire control group** at `TimeoutStopSec`. That already
sweeps up any leaked slash-worker/PTY children on stop or restart — do **not**
switch to `KillMode=control-group`, which would SIGTERM every process at once
and undercut the gateway's own orchestrated drain (exit-75 restart flow).

If workers ever linger after the main process exits (e.g. a wedged child
ignoring SIGTERM during the stop window), force-kill the whole group manually:

```sh
systemctl --user kill --kill-who=all <unit>
```

The run-time leak itself is fixed in PR #1 (disconnect reaping + the
`create_time` watchdog); the notes here only bound what happens when something
slips through.
