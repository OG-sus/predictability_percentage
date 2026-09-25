#!/usr/bin/env python3
"""
demographics_gen.py — US Birth Rate + Divorce Rate FSR Chart (YouTube Edition)
==============================================================================
Birth Rate: World Bank API (1960-present, annual)
Divorce Rate: NCHS/CDC historical data (1940-2019)
YouTube-ready 1920x1080 dark chart.

Usage:
    python demographics_gen.py
"""

import requests
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
from matplotlib.patches import FancyBboxPatch
from datetime import datetime

from fsr import calculate_predictability
from sliding_window import calculate_sliding_window

# ── CONFIG ────────────────────────────────────────────────────────────────────
WINDOW   = 10   # 10-year rolling window
K        = 1.5  # demographic data — moderate sensitivity

# ── PALETTE ───────────────────────────────────────────────────────────────────
BG    = '#080810'
PANEL = '#0d0d1c'
GRID  = '#1a1a2e'
TEXT  = '#d4d4f0'
DIM   = '#5a5a8a'
WHITE = '#f0f0ff'
GREEN = '#00e676'
GOLD  = '#ffca28'
RED   = '#ff5252'
BLUE  = '#29b6f6'
PINK  = '#f06292'

def score_color(s):
    if s >= 70: return GREEN
    if s >= 45: return GOLD
    return RED

def score_label(s):
    if s >= 70: return 'CONSISTENT'
    if s >= 45: return 'MODERATE'
    return 'VOLATILE'

def style_ax(ax):
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_edgecolor(GRID)
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.grid(axis='y', color=GRID, linewidth=0.5, alpha=0.5)

# ── BIRTH RATE DATA (World Bank) ───────────────────────────────────────────────
print("Fetching US Birth Rate from World Bank...")
try:
    url = 'https://api.worldbank.org/v2/country/US/indicator/SP.DYN.CBRT.IN?format=json&per_page=100&mrv=70'
    r = requests.get(url, timeout=15)
    raw = [x for x in r.json()[1] if x.get('value') is not None]
    raw.sort(key=lambda x: x['date'])
    birth_years  = [int(x['date']) for x in raw]
    birth_values = [float(x['value']) for x in raw]
    print(f"  {len(birth_values)} data points | {birth_years[0]}-{birth_years[-1]} | latest: {birth_values[-1]:.1f}/1000")
except Exception as e:
    print(f"  ERROR: {e}")
    birth_years, birth_values = [], []

# ── DIVORCE RATE DATA (NCHS/CDC — embedded, last published 2019) ──────────────
# Source: National Vital Statistics System, CDC/NCHS
# Rates per 1,000 population
DIVORCE_DATA = {
    1940:2.0, 1941:2.2, 1942:2.4, 1943:2.6, 1944:2.9,
    1945:3.5, 1946:4.3, 1947:3.4, 1948:2.8, 1949:2.7,
    1950:2.6, 1951:2.5, 1952:2.5, 1953:2.5, 1954:2.4,
    1955:2.3, 1956:2.3, 1957:2.2, 1958:2.1, 1959:2.2,
    1960:2.2, 1961:2.3, 1962:2.2, 1963:2.3, 1964:2.4,
    1965:2.5, 1966:2.5, 1967:2.6, 1968:2.9, 1969:3.2,
    1970:3.5, 1971:3.7, 1972:4.0, 1973:4.3, 1974:4.6,
    1975:4.8, 1976:5.0, 1977:5.0, 1978:5.1, 1979:5.3,
    1980:5.2, 1981:5.3, 1982:5.1, 1983:4.9, 1984:5.0,
    1985:5.0, 1986:4.9, 1987:4.8, 1988:4.8, 1989:4.7,
    1990:4.7, 1991:4.7, 1992:4.8, 1993:4.6, 1994:4.6,
    1995:4.4, 1996:4.3, 1997:4.3, 1998:4.2, 1999:4.1,
    2000:4.2, 2001:4.0, 2002:3.9, 2003:3.8, 2004:3.7,
    2005:3.6, 2006:3.6, 2007:3.6, 2008:3.5, 2009:3.4,
    2010:3.6, 2011:3.6, 2012:3.4, 2013:3.3, 2014:3.2,
    2015:3.1, 2016:3.2, 2017:2.9, 2018:2.9, 2019:2.9,
}

div_years  = sorted(DIVORCE_DATA.keys())
div_values = [DIVORCE_DATA[y] for y in div_years]
print(f"Divorce Rate: {len(div_values)} data points | {div_years[0]}-{div_years[-1]} | latest: {div_values[-1]}/1000")

# ── FSR CALCULATIONS ──────────────────────────────────────────────────────────
birth_fsr   = calculate_predictability(birth_values, k=K)
div_fsr     = calculate_predictability(div_values,   k=K)

def rolling(vals, years):
    if len(vals) < WINDOW + 1:
        return [], [], []
    sw = calculate_sliding_window(vals, WINDOW, k=K)
    rx = [years[r['window_end'] - 1] for r in sw]
    ry = [r['score'] for r in sw]
    return rx, ry

birth_rx, birth_ry = rolling(birth_values, birth_years)
div_rx,   div_ry   = rolling(div_values,   div_years)

print(f"\nBirth Rate FSR:  {birth_fsr:.1f}  [{score_label(birth_fsr)}]")
print(f"Divorce Rate FSR: {div_fsr:.1f}  [{score_label(div_fsr)}]")

def make_full_chart(title, subtitle, years, values, color, fsr_score,
                    rx, ry, shade_spans, footnote, out_file):
    """Save a full 1920x1080 dual-axis chart: data line + rolling FSR."""
    fig, ax1 = plt.subplots(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(BG)
    ax1.set_facecolor(PANEL)
    for sp in ax1.spines.values(): sp.set_edgecolor(GRID)

    # Data line
    ax1.fill_between(years, values, alpha=0.18, color=color)
    ax1.plot(years, values, color=color, linewidth=2.5)
    avg = sum(values) / len(values)
    ax1.axhline(avg, color=color, linewidth=1.2, linestyle='--', alpha=0.5,
                label=f'Avg: {avg:.2f}')
    for (x0, x1, c, lbl) in shade_spans:
        ax1.axvspan(x0, x1, color=c, alpha=0.10, label=lbl)
    ax1.set_ylabel('Per 1,000 Population', color=TEXT, fontsize=13, fontfamily='monospace')
    ax1.tick_params(colors=TEXT, labelsize=11)
    ax1.grid(True, color=GRID, linewidth=0.4, alpha=0.5)
    leg1 = ax1.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                      fontsize=12, loc='upper right')
    for t in leg1.get_texts(): t.set_fontfamily('monospace')

    # Rolling FSR on right axis
    if rx:
        ax2 = ax1.twinx()
        ax2.plot(rx, ry, color=RED, linewidth=2.2, linestyle='--', alpha=0.75,
                 label=f'{WINDOW}-Year Rolling FSR')
        ax2.scatter([rx[-1]], [ry[-1]], color=score_color(fsr_score),
                    s=100, zorder=10, edgecolors=BG, linewidths=1.5)
        ax2.axhline(70, color=GREEN, linewidth=0.7, linestyle=':', alpha=0.4)
        ax2.axhline(45, color=GOLD,  linewidth=0.7, linestyle=':', alpha=0.4)
        ax2.set_ylim(0, 105)
        ax2.set_ylabel('FSR Score (0-100)', color=RED, fontsize=13, fontfamily='monospace')
        ax2.tick_params(colors=RED, labelsize=11)
        leg2 = ax2.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                          fontsize=12, loc='lower right')
        for t in leg2.get_texts(): t.set_fontfamily('monospace')

    sc = score_color(fsr_score)
    fig.text(0.5, 0.960, title, ha='center', fontsize=22, fontweight='bold',
             color=WHITE, fontfamily='monospace')
    fig.text(0.5, 0.918, subtitle, ha='center', fontsize=13, color=sc,
             fontfamily='monospace')
    if footnote:
        fig.text(0.99, 0.005, footnote, ha='right', fontsize=8,
                 color='#2a2a45', fontfamily='monospace')
    fig.text(0.01, 0.005,
             f'Sources: World Bank · CDC/NCHS  ·  {datetime.now().strftime("%Y-%m-%d")}  ·  predictability-api.com',
             ha='left', fontsize=8, color='#2a2a45', fontfamily='monospace')

    fig.tight_layout(rect=[0, 0.02, 1, 0.895])
    plt.savefig(out_file, dpi=100, facecolor=BG)
    plt.close(fig)
    print(f'Saved: {out_file}')


def make_fsr_only(title, rx_a, ry_a, label_a, color_a, fsr_a,
                        rx_b, ry_b, label_b, color_b, fsr_b, out_file):
    """Save a full 1920x1080 rolling FSR comparison chart for both series."""
    fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values(): sp.set_edgecolor(GRID)

    if rx_a:
        ax.fill_between(rx_a, ry_a, alpha=0.08, color=color_a)
        ax.plot(rx_a, ry_a, color=color_a, linewidth=2.5,
                label=f'{label_a}  FSR: {fsr_a:.1f}')
        ax.scatter([rx_a[-1]], [ry_a[-1]], color=score_color(fsr_a),
                   s=100, zorder=10, edgecolors=BG, linewidths=1.5)
    if rx_b:
        ax.fill_between(rx_b, ry_b, alpha=0.08, color=color_b)
        ax.plot(rx_b, ry_b, color=color_b, linewidth=2.5,
                label=f'{label_b}  FSR: {fsr_b:.1f}')
        ax.scatter([rx_b[-1]], [ry_b[-1]], color=score_color(fsr_b),
                   s=100, zorder=10, edgecolors=BG, linewidths=1.5)

    ax.axhline(70, color=GREEN, linewidth=1.0, linestyle=':', alpha=0.5)
    ax.axhline(45, color=GOLD,  linewidth=1.0, linestyle=':', alpha=0.5)
    ax.text(0.02, 0.685, 'CONSISTENT >= 70', color=GREEN, fontsize=12, alpha=0.7,
            fontfamily='monospace', transform=ax.transAxes)
    ax.text(0.02, 0.445, 'MODERATE >= 45',   color=GOLD,  fontsize=12, alpha=0.7,
            fontfamily='monospace', transform=ax.transAxes)
    ax.set_ylim(0, 105)
    ax.set_ylabel('FSR Predictability Score (0-100)', color=TEXT, fontsize=13,
                  fontfamily='monospace')
    ax.set_xlabel('Year', color=TEXT, fontsize=11, fontfamily='monospace')
    ax.tick_params(colors=TEXT, labelsize=11)
    ax.grid(True, color=GRID, linewidth=0.4, alpha=0.5)
    leg = ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
                    fontsize=13, loc='lower right')
    for t in leg.get_texts(): t.set_fontfamily('monospace')

    fig.text(0.5, 0.960, title, ha='center', fontsize=20, fontweight='bold',
             color=WHITE, fontfamily='monospace')
    fig.text(0.5, 0.918,
             f'{WINDOW}-Year Rolling Window  ·  FSR Predictability Score™  ·  K={K}',
             ha='center', fontsize=12, color=DIM, fontfamily='monospace')
    fig.text(0.99, 0.005,
             f'Sources: World Bank · CDC/NCHS  ·  {datetime.now().strftime("%Y-%m-%d")}  ·  predictability-api.com',
             ha='right', fontsize=8, color='#2a2a45', fontfamily='monospace')

    fig.tight_layout(rect=[0, 0.02, 1, 0.895])
    plt.savefig(out_file, dpi=100, facecolor=BG)
    plt.close(fig)
    print(f'Saved: {out_file}')


# ── CHART 1: BIRTH RATE ───────────────────────────────────────────────────────
if birth_values:
    avg_b = sum(birth_values) / len(birth_values)
    make_full_chart(
        title    = 'US BIRTH RATE  —  FSR PREDICTABILITY ANALYSIS',
        subtitle = f'FSR Score: {birth_fsr:.1f}/100  ·  {score_label(birth_fsr)}  ·  {birth_years[0]}-{birth_years[-1]}  ·  Latest: {birth_values[-1]:.1f}/1,000',
        years    = birth_years,
        values   = birth_values,
        color    = BLUE,
        fsr_score= birth_fsr,
        rx       = birth_rx,
        ry       = birth_ry,
        shade_spans = [(1946, 1964, GOLD, 'Baby Boom 1946-64')],
        footnote = None,
        out_file = 'demographics_birth_rate.png',
    )

# ── CHART 2: DIVORCE RATE ─────────────────────────────────────────────────────
make_full_chart(
    title    = 'US DIVORCE RATE  —  FSR PREDICTABILITY ANALYSIS',
    subtitle = f'FSR Score: {div_fsr:.1f}/100  ·  {score_label(div_fsr)}  ·  1940-2019  ·  Peak: {max(div_values):.1f}/1,000 (1980)',
    years    = div_years,
    values   = div_values,
    color    = PINK,
    fsr_score= div_fsr,
    rx       = div_rx,
    ry       = div_ry,
    shade_spans = [(1970, 1981, RED, 'Peak Era 1970-81')],
    footnote = '* CDC/NCHS stopped national reporting after 2019',
    out_file = 'demographics_divorce_rate.png',
)

# ── CHART 3: ROLLING FSR COMPARISON ──────────────────────────────────────────
make_fsr_only(
    title   = 'BIRTH RATE  vs  DIVORCE RATE  —  HOW PREDICTABLE HAS THE DECLINE BEEN?',
    rx_a=birth_rx, ry_a=birth_ry, label_a='Birth Rate',   color_a=BLUE, fsr_a=birth_fsr,
    rx_b=div_rx,   ry_b=div_ry,   label_b='Divorce Rate', color_b=PINK, fsr_b=div_fsr,
    out_file = 'demographics_fsr_comparison.png',
)
