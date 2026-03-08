#!/usr/bin/env python3
"""
HD4 PN12442 P&ID Reconciliation Pipeline
==========================================
Extracts data from project REG documents, cross-references against
P&ID baseline data, and outputs a reconciliation register.

Usage:
    python run.py

Input files go in:
    input/registers/   — REG PDF documents (valve lists, equipment lists, etc.)
    input/pids/        — P&ID baseline spreadsheet (from Claude or manual entry)

Output goes to:
    output/            — Reconciliation spreadsheet
"""
import os
import sys
import glob
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from extract import (
    extract_valve_list_fuel,
    extract_valve_list_npi,
    extract_mech_equip_fuel,
    extract_mech_equip_npi,
    extract_line_list_fuel,
    extract_special_items,
    extract_tiein_list,
)
from reconcile import reconcile_valves, reconcile_equipment
from output import build_workbook

# ----------------------------------------------------------------
# Config — file name patterns to match in the input folders
# ----------------------------------------------------------------
REG_PATTERNS = {
    'vlv_fuel':  '*REG-00021*',
    'vlv_npi':   '*REG-00009*',
    'eq_fuel':   '*REG-00019*',
    'eq_npi':    '*REG-00018*',
    'lines':     '*REG-00020*',
    'sp_items':  '*REG-00022*',
    'tieins':    '*REG-00023*',
}

PID_BASELINE = '*PID_Reconciliation_Register*'


def find_file(folder, pattern):
    """Find a single file matching a glob pattern in a folder."""
    matches = glob.glob(os.path.join(folder, pattern))
    if not matches:
        return None
    return matches[0]


def main():
    print("=" * 60)
    print("  HD4 PN12442 P&ID RECONCILIATION PIPELINE")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    reg_dir = os.path.join(base_dir, 'input', 'registers')
    pid_dir = os.path.join(base_dir, 'input', 'pids')
    out_dir = os.path.join(base_dir, 'output')

    os.makedirs(out_dir, exist_ok=True)

    # Check input folders exist
    if not os.path.isdir(reg_dir):
        print(f"\nERROR: Register input folder not found: {reg_dir}")
        print("Create it and drop your REG PDFs in there.")
        sys.exit(1)

    # --- Phase 1: Extract from REG documents ---
    print("\n--- Phase 1: Extracting from REG documents ---")
    counts = {}

    f = find_file(reg_dir, REG_PATTERNS['vlv_fuel'])
    vlv_fuel = extract_valve_list_fuel(f) if f else pd.DataFrame()
    counts['vlv_fuel'] = f'{len(vlv_fuel)} valves'

    f = find_file(reg_dir, REG_PATTERNS['vlv_npi'])
    vlv_npi = extract_valve_list_npi(f) if f else pd.DataFrame()
    counts['vlv_npi'] = f'{len(vlv_npi)} valves'

    f = find_file(reg_dir, REG_PATTERNS['eq_fuel'])
    eq_fuel = extract_mech_equip_fuel(f) if f else pd.DataFrame()
    counts['eq_fuel'] = f'{len(eq_fuel)} items'

    f = find_file(reg_dir, REG_PATTERNS['eq_npi'])
    eq_npi = extract_mech_equip_npi(f) if f else pd.DataFrame()
    counts['eq_npi'] = f'{len(eq_npi)} items'

    f = find_file(reg_dir, REG_PATTERNS['lines'])
    lines = extract_line_list_fuel(f) if f else pd.DataFrame()
    counts['lines'] = f'{len(lines)} lines'

    f = find_file(reg_dir, REG_PATTERNS['sp_items'])
    sp_items = extract_special_items(f) if f else pd.DataFrame()
    counts['sp_items'] = f'{len(sp_items)} items'

    f = find_file(reg_dir, REG_PATTERNS['tieins'])
    tieins = extract_tiein_list(f) if f else pd.DataFrame()
    counts['tieins'] = f'{len(tieins)} tie-ins'

    # --- Phase 2: Load P&ID baseline ---
    print("\n--- Phase 2: Loading P&ID baseline ---")
    pid_file = find_file(pid_dir, PID_BASELINE)
    if not pid_file:
        # Also check output folder in case it's there
        pid_file = find_file(out_dir, PID_BASELINE)
    if not pid_file:
        print(f"\nERROR: P&ID baseline spreadsheet not found.")
        print(f"Looking for: {PID_BASELINE}")
        print(f"In: {pid_dir} or {out_dir}")
        print("Place the HD4_PID_Reconciliation_Register.xlsx file there.")
        sys.exit(1)

    print(f"  Using: {pid_file}")
    pid_valves = pd.read_excel(pid_file, sheet_name='Valve Register', header=3)
    pid_equip = pd.read_excel(pid_file, sheet_name='Equipment Register', header=3)
    print(f"  P&ID Valves: {len(pid_valves)}, Equipment: {len(pid_equip)}")

    # --- Phase 3: Cross-reference ---
    print("\n--- Phase 3: Cross-referencing ---")
    vlv_combined = pd.concat([vlv_fuel, vlv_npi], ignore_index=True)
    eq_combined = pd.concat([eq_fuel, eq_npi], ignore_index=True)

    valve_recon = reconcile_valves(pid_valves, vlv_combined)
    equip_recon = reconcile_equipment(pid_equip, eq_combined)

    # --- Print results ---
    print(f"\n  Valve reconciliation: {len(valve_recon)} entries")
    for s in valve_recon['status'].value_counts().items():
        print(f"    {s[0]}: {s[1]}")

    print(f"\n  Equipment reconciliation: {len(equip_recon)} entries")
    for s in equip_recon['status'].value_counts().items():
        print(f"    {s[0]}: {s[1]}")

    # --- Phase 4: Build output ---
    print("\n--- Phase 4: Building output ---")
    out_path = os.path.join(out_dir, 'HD4_PID_Reconciliation_AUTOMATED.xlsx')
    build_workbook(valve_recon, equip_recon, counts, out_path)

    print("\n" + "=" * 60)
    print("  DONE — open the file in Excel to review")
    print("=" * 60)


if __name__ == '__main__':
    main()
