#!/usr/bin/env bash
# Prevent idle sleep (user-level; no sudo). Foreground for launchd KeepAlive.
exec /usr/bin/caffeinate -dimsu
