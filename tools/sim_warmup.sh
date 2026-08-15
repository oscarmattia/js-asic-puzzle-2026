#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

usage() {
    echo "Usage: tools/sim_warmup.sh rtl|gates|extracted"
    exit 1
}

if ! command -v iverilog >/dev/null 2>&1; then
    echo "iverilog not found. Install with: brew install icarus-verilog"
    exit 2
fi

if ! command -v vvp >/dev/null 2>&1; then
    echo "vvp not found. Install with: brew install icarus-verilog"
    exit 2
fi

MODE="${1:-}"
if [[ -z "$MODE" ]]; then
    usage
fi

mkdir -p build

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

sky130_missing_instructions() {
    cat <<'EOF'
SKY130 standard-cell Verilog not found.

Clone the HD library (already the expected layout):
  git clone --depth 1 https://github.com/google/skywater-pdk-libs-sky130_fd_sc_hd \
    third_party/sky130_fd_sc_hd

Or set SKY130_FD_SC_HD to that repo (must contain a cells/ directory).
EOF
}

case "$MODE" in
rtl)
    iverilog -g2012 -o build/warmup_rtl.vvp \
        tb/warmup_tb.v warmup/00_source.v
    vvp build/warmup_rtl.vvp
    if [[ -f build/warmup.vcd ]]; then
        cp -f build/warmup.vcd build/warmup_rtl.vcd
    fi
    ;;
gates)
    pdk_root="$(find_sky130_root || true)"
    if [[ -z "$pdk_root" ]]; then
        sky130_missing_instructions
        exit 2
    fi

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
    done < <(grep -oE 'sky130_fd_sc_hd__[a-z0-9_]+' warmup/01_netlist.v | sort -u)
    include_dirs+=(-I "${pdk_root}/models")

    echo "Using SKY130 cells from: $pdk_root (${#cell_files[@]} unique cells)"
    iverilog -g2012 -o build/warmup_gates.vvp \
        "${include_dirs[@]}" \
        build/sky130_defines.v \
        tb/warmup_tb.v warmup/01_netlist.v \
        "${cell_files[@]}"
    vvp build/warmup_gates.vvp
    if [[ -f build/warmup.vcd ]]; then
        cp -f build/warmup.vcd build/warmup_gates.vcd
    fi
    ;;
extracted)
    netlist="${ROOT}/build/warmup_extracted.v"
    if [[ ! -f "$netlist" ]]; then
        echo "missing extracted netlist: $netlist" >&2
        echo "run: uv run python tools/extract_netlist.py --gds warmup/04_final.gds --lef-dir third_party/sky130_fd_sc_hd --out build/warmup_extracted.v" >&2
        exit 1
    fi
    pdk_root="$(find_sky130_root || true)"
    if [[ -z "$pdk_root" ]]; then
        sky130_missing_instructions
        exit 2
    fi

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

    echo "Using SKY130 cells from: $pdk_root (${#cell_files[@]} unique cells)"
    iverilog -g2012 -o build/warmup_extracted.vvp \
        "${include_dirs[@]}" \
        build/sky130_defines.v \
        tb/warmup_tb.v "$netlist" \
        "${cell_files[@]}"
    vvp build/warmup_extracted.vvp
    if [[ -f build/warmup.vcd ]]; then
        cp -f build/warmup.vcd build/warmup_extracted.vcd
    fi
    ;;
*)
    usage
    ;;
esac
