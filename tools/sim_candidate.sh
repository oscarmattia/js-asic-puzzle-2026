#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if ! command -v iverilog >/dev/null 2>&1 || ! command -v vvp >/dev/null 2>&1; then
    echo "iverilog/vvp not found. Install with: brew install icarus-verilog"
    exit 2
fi

find_sky130_root() {
    local candidates=()
    if [[ -n "${SKY130_FD_SC_HD:-}" ]]; then
        candidates+=("${SKY130_FD_SC_HD}")
    fi
    candidates+=("${ROOT}/third_party/sky130_fd_sc_hd")
    if [[ -n "${PDK_ROOT:-}" ]]; then
        candidates+=("${PDK_ROOT}/sky130A/libs.ref/sky130_fd_sc_hd")
    fi
    local path
    for path in "${candidates[@]}"; do
        if [[ -d "${path}/cells" ]]; then
            echo "$path"
            return 0
        fi
    done
    return 1
}

netlist="${NETLIST:-${ROOT}/build/puzzle_extracted.v}"
if [[ ! -f "$netlist" ]]; then
    echo "missing extracted netlist: $netlist" >&2
    exit 1
fi

pdk_root="$(find_sky130_root || true)"
if [[ -z "$pdk_root" ]]; then
    echo "SKY130 standard-cell Verilog not found under third_party/sky130_fd_sc_hd" >&2
    exit 2
fi

mkdir -p build
cat > build/sky130_defines.v <<'EOF'
`define FUNCTIONAL
`define UNIT_DELAY
EOF

cell_files=()
include_dirs=()
while IFS= read -r cell; do
    family="${cell#sky130_fd_sc_hd__}"
    family="${family%_*}"
    f="${pdk_root}/cells/${family}/${cell}.v"
    if [[ ! -f "$f" ]]; then
        echo "missing cell model: $f" >&2
        exit 1
    fi
    cell_files+=("$f")
    include_dirs+=(-I "${pdk_root}/cells/${family}")
done < <(grep -oE 'sky130_fd_sc_hd__[a-z0-9_]+' "$netlist" | sort -u)
include_dirs+=(-I "${pdk_root}/models")

vvp_path="${ROOT}/build/puzzle_candidate.vvp"
stamp_path="${vvp_path}.netlist"
# Rebuild whenever the requested netlist differs from the compiled one, else a
# stale vvp silently answers for the wrong netlist.
stamp_now="$(cd "$(dirname "$netlist")" && pwd)/$(basename "$netlist")"
if [[ ! -f "$stamp_path" ]] || [[ "$(cat "$stamp_path")" != "$stamp_now" ]]; then
    REBUILD=1
fi
if [[ "${REBUILD:-}" == "1" || ! -f "$vvp_path" ]]; then
    echo "netlist: $netlist"
    echo "Using SKY130 cells from: $pdk_root (${#cell_files[@]} unique cells)"
    iverilog -g2012 -o "$vvp_path" \
        "${include_dirs[@]}" \
        build/sky130_defines.v \
        tb/puzzle_candidate_tb.v "$netlist" \
        "${cell_files[@]}"
    printf '%s' "$stamp_now" > "$stamp_path"
fi

stim="${1:-build/candidate_stim.txt}"
if [[ ! -f "$stim" ]]; then
    echo "missing stim: $stim" >&2
    exit 1
fi

# vvp plusarg: stim=PATH
set +e
vvp "$vvp_path" "+stim=${stim}"
rc=$?
set -e
exit "$rc"
