"""
base_data_gen.py — Blockchain Stability Analyzer
=================================================
Pulls live on-chain data from Base L2 or Ethereum mainnet via public
JSON-RPC endpoints and runs the FSR Predictability Score™ on it.

Best stats for stream (actual visual movement):
  GAS       — gas fees swing constantly, great entropy
  TX_COUNT  — block load varies wildly, very watchable
  BLOCK_TIME — use on Ethereum (~12s target with real variance),
               NOT Base (Base is always exactly 2.0s — flat line)

No API key required.
"""

import requests
import time
import os
from fsr import calculate_predictability
from sliding_window import calculate_sliding_window
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# RPC endpoints (public, no API key)
# ---------------------------------------------------------------------------

CHAINS = {
    'BASE': {
        'rpc':   'https://mainnet.base.org',
        'label': 'Base L2',
        'color': '#0052ff',
        'block_target': 2,
    },
    'ETH': {
        'rpc':   'https://eth.llamarpc.com',
        'label': 'Ethereum',
        'color': '#627eea',
        'block_target': 12,
    },
}

# Default chain — override with CHAIN env var (BASE or ETH)
DEFAULT_CHAIN = os.environ.get('CHAIN', 'BASE').upper()

RPC_URL = os.environ.get('BASE_RPC_URL', CHAINS.get(DEFAULT_CHAIN, CHAINS['BASE'])['rpc'])
CHAIN_META = CHAINS.get(DEFAULT_CHAIN, CHAINS['BASE'])

# Persistent session — reuses TCP connection, avoids ConnectionReset
SESSION = requests.Session()
SESSION.headers.update({'Content-Type': 'application/json'})

STAT_OPTIONS = {
    'TX_COUNT':   'Transactions per block — network throughput     ← BEST FOR STREAM (156-860 range)',
    'GAS':        'Base fee per gas (Gwei) — gas price stability  ← use ETH chain for movement',
    'BLOCK_TIME': 'Inter-block interval (seconds) — use ETH chain for variance',
}

K_FACTOR = 2.0  # Finance-grade sensitivity for infrastructure data


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def _rpc(method, params=None, rpc_url=None):
    url = rpc_url or RPC_URL
    payload = {'jsonrpc': '2.0', 'method': method, 'params': params or [], 'id': 1}
    try:
        resp = SESSION.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if 'error' in data:
            raise ValueError(f"RPC error: {data['error']}")
        return data.get('result')
    except Exception as e:
        raise ConnectionError(f"Base RPC call failed ({method}): {e}")


def get_latest_block_number():
    result = _rpc('eth_blockNumber')
    return int(result, 16)


def get_block(number_hex, full_tx=False):
    return _rpc('eth_getBlockByNumber', [number_hex, full_tx])


def hex_to_int(h):
    if h is None:
        return None
    return int(h, 16)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_blocks(num_blocks=50):
    """
    Fetches the last N blocks from Base L2.
    Uses a persistent session to reuse TCP connections and avoid ConnectionReset errors.
    Returns a list of dicts with timestamp, baseFeePerGas, tx_count.
    """
    print(f"Connecting to {CHAIN_META['label']} ({RPC_URL})...")
    latest = get_latest_block_number()
    print(f"Latest block: #{latest:,}")
    print(f"Fetching {num_blocks} blocks...")

    blocks = []
    for i in range(num_blocks):
        block_num = latest - (num_blocks - 1 - i)
        block_hex = hex(block_num)
        for attempt in range(3):
            try:
                block = get_block(block_hex, full_tx=False)
                if block:
                    blocks.append({
                        'number':    hex_to_int(block.get('number')),
                        'timestamp': hex_to_int(block.get('timestamp')),
                        'gas_used':  hex_to_int(block.get('gasUsed')),
                        'base_fee':  hex_to_int(block.get('baseFeePerGas')),
                        'tx_count':  len(block.get('transactions', [])),
                    })
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                else:
                    print(f"  Warning: could not fetch block #{block_num}: {e}")
        time.sleep(0.1)

    print(f"Successfully fetched {len(blocks)} blocks.\n")
    return blocks


def extract_series(blocks, stat_type):
    """Convert block data into a numeric series for FSR scoring."""
    stat_upper = stat_type.upper()

    if stat_upper == 'BLOCK_TIME':
        # Inter-block interval: difference in timestamps between consecutive blocks
        series = []
        for i in range(1, len(blocks)):
            dt = blocks[i]['timestamp'] - blocks[i - 1]['timestamp']
            if dt > 0:
                series.append(round(float(dt), 2))
        return series, 'seconds'

    elif stat_upper == 'GAS':
        # Base fee in Gwei (1 Gwei = 1e9 Wei)
        series = [
            round(b['base_fee'] / 1e9, 4)
            for b in blocks
            if b['base_fee'] is not None
        ]
        return series, 'Gwei'

    elif stat_upper == 'TX_COUNT':
        series = [b['tx_count'] for b in blocks]
        return series, 'txns/block'

    else:
        return [], ''


# ---------------------------------------------------------------------------
# Analysis + output
# ---------------------------------------------------------------------------

def analyze(stat_type, num_blocks=50):
    stat_upper = stat_type.upper()
    if stat_upper not in STAT_OPTIONS:
        print(f"Unknown stat '{stat_type}'. Choose from: {', '.join(STAT_OPTIONS)}")
        return

    try:
        blocks = fetch_blocks(num_blocks)
    except ConnectionError as e:
        print(f"Error: {e}")
        return

    series, unit = extract_series(blocks, stat_upper)
    if len(series) < 4:
        print("Not enough data points after parsing.")
        return

    score = calculate_predictability(series, k=K_FACTOR)
    avg   = sum(series) / len(series)

    print(f"=== Base L2 — {stat_upper} Predictability ===\n")
    print(f"Metric        : {STAT_OPTIONS[stat_upper]}")
    print(f"Blocks sampled: {num_blocks}  ({len(series)} data points)")
    print(f"Average       : {avg:.4f} {unit}")

    label = _stability_label(score)
    print(f"\n{'─'*40}")
    print(f"  Predictability Score™: {score:.2f}  [{label}]")
    print(f"{'─'*40}\n")

    print("--- COPY DATA FOR DASHBOARD ---\n")
    print(', '.join(str(v) for v in series))
    print()

    _save_chart(stat_upper, series, unit, score, avg, num_blocks)
    return score, series


def _stability_label(score):
    if score >= 90: return "⚡ ELITE INFRASTRUCTURE"
    if score >= 75: return "✅ HIGH STABILITY"
    if score >= 60: return "⚠️  MODERATE"
    if score >= 40: return "🔴 VOLATILE"
    return "💀 UNSTABLE"


def _save_chart(stat_upper, series, unit, score, avg, num_blocks):
    window_size = min(10, len(series) // 2)
    if window_size < 2:
        return

    # Close any leaked figures from previous failed renders
    plt.close('all')

    out_dir = os.path.join('static', 'images', 'base_charts')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'base_{stat_upper.lower()}_analysis.png')
    tmp_path = path + '.tmp'

    fig = None
    try:
        results = calculate_sliding_window(series, window_size, k=K_FACTOR)
        scores  = [None] * (window_size - 1) + [r['score'] for r in results]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 8))
        fig.patch.set_facecolor('#0f1117')
        for ax in (ax1, ax2):
            ax.set_facecolor('#1a1d27')
            ax.tick_params(colors='#aaaaaa')
            ax.spines['bottom'].set_color('#333')
            ax.spines['left'].set_color('#333')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

        ax1.plot(series, marker='o', markersize=3, linestyle='-', color=CHAIN_META['color'],
                 alpha=0.85, label=f'{stat_upper} ({unit})')
        ax1.axhline(y=avg, color='#888', linestyle='--', linewidth=1,
                    label=f'Avg: {avg:.4f} {unit}')
        ax1.set_title(f"{CHAIN_META['label']} — {stat_upper} per Block (last {num_blocks} blocks)",
                      color='white', fontsize=13, pad=10)
        ax1.set_ylabel(unit, color='#aaaaaa')
        ax1.legend(facecolor='#1a1d27', labelcolor='white', framealpha=0.5)
        ax1.grid(True, alpha=0.15)

        ax2.plot(scores, color='#00c2ff', linewidth=2,
                 label=f'Predictability Score ({window_size}-block window)')
        ax2.axhline(y=score, color=CHAIN_META['color'], linestyle='--', linewidth=1,
                    label=f'Overall: {score:.2f}')
        ax2.axhline(y=80, color='#00ff88', linestyle=':', linewidth=1, label='Elite (80)')
        ax2.axhline(y=60, color='#ffaa00', linestyle=':', linewidth=1, label='Volatile (60)')
        ax2.set_title('FSR Predictability Score™ — Sliding Window', color='white',
                      fontsize=13, pad=10)
        ax2.set_ylabel('Score (0–100)', color='#aaaaaa')
        ax2.set_xlabel('Block (relative)', color='#aaaaaa')
        ax2.set_ylim(0, 105)
        ax2.legend(facecolor='#1a1d27', labelcolor='white', framealpha=0.5)
        ax2.grid(True, alpha=0.15)

        plt.tight_layout()
        # Write to temp file first, then rename — prevents black flash mid-write
        plt.savefig(tmp_path, facecolor='#0f1117')
        os.replace(tmp_path, path)
        print(f"Chart saved → {path}")

    except Exception as e:
        print(f"Chart render error (keeping last good chart): {e}")
        # Clean up temp file if it exists
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    finally:
        if fig is not None:
            plt.close(fig)


# ---------------------------------------------------------------------------
# Live stream mode — continuously updates every N seconds
# ---------------------------------------------------------------------------

def stream_mode(stat_type, refresh_seconds=10, num_blocks=50):
    """
    Continuously re-fetches and scores blockchain data.
    Default refresh: 10s (fast enough to feel live, slow enough to fetch cleanly).
    """
    print(f"\n🔴 LIVE STREAM MODE — {CHAIN_META['label']} {stat_type.upper()}")
    print(f"   Refreshing every {refresh_seconds}s. Ctrl+C to stop.\n")
    try:
        while True:
            try:
                print(f"\n[{time.strftime('%H:%M:%S')}] Fetching fresh data...")
                analyze(stat_type, num_blocks)
                print(f"Next update in {refresh_seconds}s...")
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Cycle error (stream continues): {e}")
                print(f"Retrying in {refresh_seconds}s...")
            time.sleep(refresh_seconds)
    except KeyboardInterrupt:
        print("\nStream stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print("Blockchain Stability Analyzer")
    print("Powered by FSR Predictability Score™")
    print("=" * 42)
    print(f"\nActive chain: {CHAIN_META['label']} ({RPC_URL})")
    print("Switch chain: set CHAIN=ETH or CHAIN=BASE env var\n")
    print("Available metrics (pick for stream action):")
    for k, v in STAT_OPTIONS.items():
        print(f"  {k:<12} — {v}")
    print()

    while True:
        stat = input("Stat to analyze (TX_COUNT / GAS / BLOCK_TIME) or 'q' [default: TX_COUNT]: ").strip().upper() or 'TX_COUNT'
        if stat == 'Q':
            break
        if stat not in STAT_OPTIONS:
            print(f"Unknown stat. Choose from: {', '.join(STAT_OPTIONS)}")
            continue

        try:
            n = int(input("Number of blocks to sample (default 50): ").strip() or "50")
        except ValueError:
            n = 50

        live = input("Live stream mode? (y/n, default y): ").strip().lower()
        if live != 'n':
            try:
                interval = int(input("Refresh interval in seconds (default 10): ").strip() or "10")
            except ValueError:
                interval = 10
            stream_mode(stat, refresh_seconds=interval, num_blocks=n)
        else:
            analyze(stat, num_blocks=n)
        print()
