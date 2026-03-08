# HD4 P&ID Reconciliation Tool

Automated cross-referencing of P&ID drawings against valve lists, equipment lists, and other project registers for the **PN12442 HD4 Early Tonnes** project (Hope Downs 4, Bulk Diesel Storage & Refuelling).

## What it does

1. **Extracts** tabular data from project register PDFs (valve lists, equipment lists, line lists, etc.)
2. **Cross-references** the extracted data against a P&ID baseline spreadsheet
3. **Flags discrepancies** — missing items, status mismatches, tag naming issues, instrument vs mechanical classification
4. **Outputs** a formatted Excel reconciliation register with colour-coded status flags

## Quick start

### 1. Clone the repo

```
git clone https://github.com/YOUR_USERNAME/hd4-pid-reconciliation.git
cd hd4-pid-reconciliation
```

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Drop in your input files

Copy your project PDFs into the input folders:

```
input/
  registers/     <-- Drop REG PDF files here
    PN12442-REG-00009_*.pdf
    PN12442-REG-00018_*.pdf
    PN12442-REG-00019_*.pdf
    PN12442-REG-00020_*.pdf
    PN12442-REG-00021_*.pdf
    PN12442-REG-00022_*.pdf
    PN12442-REG-00023_*.pdf
  pids/           <-- Drop P&ID baseline spreadsheet here
    HD4_PID_Reconciliation_Register.xlsx
```

### 4. Run

```
python run.py
```

Output will be in `output/HD4_PID_Reconciliation_AUTOMATED.xlsx`

## Project structure

```
hd4-pid-reconciliation/
├── run.py                  # Main script — run this
├── requirements.txt        # Python dependencies
├── .gitignore
├── README.md
├── src/
│   ├── __init__.py
│   ├── extract.py          # PDF data extraction functions
│   ├── reconcile.py        # Cross-reference / comparison logic
│   └── output.py           # Excel output builder
├── input/
│   ├── registers/          # REG PDFs go here (gitignored)
│   └── pids/               # P&ID baseline spreadsheet (gitignored)
└── output/                 # Generated files land here (gitignored)
```

## Output tabs

The output spreadsheet has three tabs:

- **Valve Reconciliation** — Every valve from P&IDs and valve lists, with match status
- **Equipment Reconciliation** — Every equipment item, with match status
- **Summary** — Counts, key actions, and source document references

### Status colour codes

| Colour | Status | Meaning |
|--------|--------|---------|
| Green | OK | Matched between P&ID and list |
| Red/Pink | MISMATCH / MISSING | Genuine discrepancy — needs review |
| Yellow | CHECK | P&ID data wasn't fully extracted — verify on drawing |
| Orange | EXTRA / TAG MISMATCH | On one document but not the other, or tag naming differs |
| Blue | INSTRUMENT | Instrument/control item — not expected on mech list |

## Notes

- The P&ID baseline was built by extracting valve and equipment tags from PDF renderings of the P&ID drawings. OCR quality varies — the newer F-series drawings extracted well, but the older VF-series B1-size drawings are harder to read. Items flagged as "EXTRA (on list, not in P&ID extract)" are most likely real items that just couldn't be read from the drawing PDFs.
- Input PDFs are gitignored by default since they contain project-specific data. Only the code is version-controlled.
- The script is built for the PN12442 document set but the extraction functions in `src/extract.py` could be adapted for other projects with similar register formats.

## Requirements

- Python 3.9+
- See `requirements.txt` for packages
