#!/usr/bin/env bash
# Phase 1: environment check (read-only)
head -3 /etc/os-release
for c in python3 node npm git psql; do printf "%s: " $c; $c --version 2>/dev/null || echo "MISSING"; done
df -h / | tail -1
free -h | head -2
