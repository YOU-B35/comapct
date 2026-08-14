#!/bin/bash
# Host memory watchdog: relieve pressure before the box freezes.
# - Does NOT "drop caches" (useless when apps hold RSS)
# - Stops confirmed-idle containers (free RAM permanently)
# - Dawn soft reclaim: low load + high swap → restart Commander once/day
# - Hard pressure: restart Commander, then AutoMedia if still tight
# - Soft-restarts Commander on sustained high CPU

set -u

LOG_DIR=/var/log/crosshub-watchdog
STATE_DIR=/var/lib/crosshub-watchdog
LOG_FILE="$LOG_DIR/watchdog.log"
LOW_STREAK_FILE="$STATE_DIR/low_streak"
CPU_STREAK_FILE="$STATE_DIR/cpu_streak"
COOLDOWN_FILE="$STATE_DIR/cooldown_until"
DAWN_DONE_FILE="$STATE_DIR/dawn_reclaim_day"

# thresholds (kB for MemAvailable)
MEM_SOFT_KB=$((450 * 1024))      # ~450MB available → warn / count
MEM_HARD_KB=$((280 * 1024))      # ~280MB available → act
SWAP_HARD_PCT=85                 # swap used percent → hard act
SWAP_SOFT_PCT=70                 # swap used percent → dawn soft reclaim
CPU_HARD_PCT=90                  # commander cpu
LOAD_SOFT_MAX=1                  # dawn reclaim only when 1-min load <= this
LOW_STREAK_NEED=2                # consecutive runs (~2 min if cron */1)
CPU_STREAK_NEED=3
COOLDOWN_SEC=900                 # 15 min between restart actions
DAWN_HOUR_START=3                # local 03:00 inclusive
DAWN_HOUR_END=5                  # local 05:00 exclusive

# Confirmed unused / non-business — stop and disable auto-restart
IDLE_STOP_CONTAINERS="1Panel-openlist-SSrO"

mkdir -p "$LOG_DIR" "$STATE_DIR"
chmod 755 "$LOG_DIR" "$STATE_DIR"

log() {
  echo "$(date -Is) $*" | tee -a "$LOG_FILE" >/dev/null
  # keep log small
  if [ -f "$LOG_FILE" ] && [ "$(wc -c < "$LOG_FILE")" -gt 2000000 ]; then
    tail -n 2000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
  fi
}

now_ts() { date +%s; }

in_cooldown() {
  local until=0
  [ -f "$COOLDOWN_FILE" ] && until=$(cat "$COOLDOWN_FILE" 2>/dev/null || echo 0)
  [ "$(now_ts)" -lt "${until:-0}" ]
}

set_cooldown() {
  echo $(( $(now_ts) + COOLDOWN_SEC )) > "$COOLDOWN_FILE"
}

read_streak() {
  local f="$1"
  local v=0
  [ -f "$f" ] && v=$(cat "$f" 2>/dev/null || echo 0)
  echo "${v:-0}"
}

write_streak() {
  echo "$2" > "$1"
}

mem_available_kb() {
  awk '/^MemAvailable:/ {print $2}' /proc/meminfo
}

swap_used_pct() {
  awk '
    /^SwapTotal:/ {t=$2}
    /^SwapFree:/ {f=$2}
    END {
      if (t+0 <= 0) { print 0; exit }
      u=t-f
      printf "%d", (u*100)/t
    }' /proc/meminfo
}

load1_int() {
  # 1-minute load average truncated to integer
  awk '{printf "%d", $1}' /proc/loadavg
}

local_hour() {
  date +%H | sed 's/^0//'
}

local_ymd() {
  date +%F
}

container_running() {
  docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null | grep -qx true
}

restart_container() {
  local name="$1"
  if container_running "$name"; then
    log "ACTION restart $name"
    docker restart "$name" >/dev/null 2>&1 || log "WARN restart failed $name"
  else
    log "SKIP restart $name (not running)"
  fi
}

stop_idle_containers() {
  local name stopped=0
  for name in $IDLE_STOP_CONTAINERS; do
    [ -z "$name" ] && continue
    if docker inspect "$name" >/dev/null 2>&1; then
      # prevent 1Panel/docker from bringing it back
      docker update --restart=no "$name" >/dev/null 2>&1 || true
      if container_running "$name"; then
        log "ACTION stop idle $name"
        docker stop "$name" >/dev/null 2>&1 || log "WARN stop failed $name"
        stopped=1
      fi
    fi
  done
  echo "$stopped"
}

commander_cpu_pct() {
  # e.g. 12.34%
  local raw
  raw=$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' 2>/dev/null | awk '$1 ~ /commander/ {gsub(/%/,"",$2); print $2; exit}')
  if [ -z "${raw:-}" ]; then
    echo 0
  else
    # truncate to int
    echo "${raw%%.*}"
  fi
}

MEM_AVAIL=$(mem_available_kb)
SWAP_PCT=$(swap_used_pct)
CPU_PCT=$(commander_cpu_pct)
LOAD1=$(load1_int)
HOUR=$(local_hour)
TODAY=$(local_ymd)
LOW_STREAK=$(read_streak "$LOW_STREAK_FILE")
CPU_STREAK=$(read_streak "$CPU_STREAK_FILE")

log "STATUS mem_avail_kb=$MEM_AVAIL swap_used_pct=$SWAP_PCT commander_cpu=$CPU_PCT load1=$LOAD1 hour=$HOUR low_streak=$LOW_STREAK cpu_streak=$CPU_STREAK"

# Always reclaim confirmed-idle services (cheap if already stopped)
IDLE_STOPPED=$(stop_idle_containers)

# streak updates
if [ "$MEM_AVAIL" -lt "$MEM_SOFT_KB" ] || [ "$SWAP_PCT" -ge "$SWAP_HARD_PCT" ]; then
  LOW_STREAK=$((LOW_STREAK + 1))
else
  LOW_STREAK=0
fi
write_streak "$LOW_STREAK_FILE" "$LOW_STREAK"

if [ "$CPU_PCT" -ge "$CPU_HARD_PCT" ]; then
  CPU_STREAK=$((CPU_STREAK + 1))
else
  CPU_STREAK=0
fi
write_streak "$CPU_STREAK_FILE" "$CPU_STREAK"

if in_cooldown; then
  log "COOLDOWN active, no action"
  exit 0
fi

acted=0

# Hard memory / swap pressure
if [ "$MEM_AVAIL" -lt "$MEM_HARD_KB" ] || { [ "$SWAP_PCT" -ge "$SWAP_HARD_PCT" ] && [ "$LOW_STREAK" -ge "$LOW_STREAK_NEED" ]; }; then
  if [ "$LOW_STREAK" -ge "$LOW_STREAK_NEED" ] || [ "$MEM_AVAIL" -lt "$MEM_HARD_KB" ]; then
    log "TRIGGER memory pressure mem_avail_kb=$MEM_AVAIL swap_used_pct=$SWAP_PCT"
    # Prefer restarting Commander first (historically CPU + large RSS), then AutoMedia
    restart_container commander-server-t260220
    sleep 3
    MEM_AVAIL2=$(mem_available_kb)
    if [ "$MEM_AVAIL2" -lt "$MEM_HARD_KB" ]; then
      restart_container automedia-social-auto-upload
    fi
    # light cleanup that does not touch running app data
    journalctl --vacuum-time=3d >/dev/null 2>&1 || true
    docker container prune -f >/dev/null 2>&1 || true
    acted=1
    write_streak "$LOW_STREAK_FILE" 0
  fi
fi

# Sustained commander CPU peg
if [ "$acted" -eq 0 ] && [ "$CPU_STREAK" -ge "$CPU_STREAK_NEED" ]; then
  log "TRIGGER commander high cpu streak=$CPU_STREAK cpu=$CPU_PCT"
  restart_container commander-server-t260220
  acted=1
  write_streak "$CPU_STREAK_FILE" 0
fi

# Dawn soft reclaim: once/day in 03:00-04:59, high swap, quiet load
DAWN_DONE_DAY=""
[ -f "$DAWN_DONE_FILE" ] && DAWN_DONE_DAY=$(cat "$DAWN_DONE_FILE" 2>/dev/null || true)
if [ "$acted" -eq 0 ] \
  && [ "$HOUR" -ge "$DAWN_HOUR_START" ] && [ "$HOUR" -lt "$DAWN_HOUR_END" ] \
  && [ "$DAWN_DONE_DAY" != "$TODAY" ] \
  && [ "$SWAP_PCT" -ge "$SWAP_SOFT_PCT" ] \
  && [ "$LOAD1" -le "$LOAD_SOFT_MAX" ]; then
  log "TRIGGER dawn soft reclaim swap_used_pct=$SWAP_PCT load1=$LOAD1"
  restart_container commander-server-t260220
  echo "$TODAY" > "$DAWN_DONE_FILE"
  acted=1
fi

if [ "$acted" -eq 1 ]; then
  set_cooldown
  log "DONE action applied, cooldown=${COOLDOWN_SEC}s"
elif [ "${IDLE_STOPPED:-0}" -eq 1 ]; then
  log "DONE idle containers stopped (no cooldown)"
fi

exit 0
