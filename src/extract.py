"""
Extract tabular data from PN12442 REG documents (valve lists, equipment lists, etc.)
using pdfplumber. Returns pandas DataFrames for each document type.
"""
import pdfplumber
import pandas as pd
import re
import os


def _find_in_row(row_cells, pattern):
    """Search all cells in a row for a regex pattern, return first match or ''."""
    for c in row_cells:
        m = re.search(pattern, str(c) if c else '')
        if m:
            return m.group()
    return ''


def _cell(row, idx, default=''):
    """Safely get a cell value from a row by index."""
    if idx < len(row) and row[idx]:
        return str(row[idx]).strip()
    return default


def extract_valve_list_fuel(path):
    """Extract valve data from REG-00021 (Fuel Facility Valve List)."""
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cleaned = [str(c).strip() if c else '' for c in row]
                    tag = _find_in_row(cleaned, r'(?:VF|VA|VW|VP|VL)-\d{4}-\d{3}')
                    if tag:
                        rows.append({
                            'valve_tag': tag,
                            'size': _cell(cleaned, 1),
                            'valve_code': _cell(cleaned, 2),
                            'fluid_type': _cell(cleaned, 3),
                            'area_no': _cell(cleaned, 8),
                            'pid_no': _cell(cleaned, 11),
                            'line_no': _cell(cleaned, 12),
                            'description': _cell(cleaned, 15),
                            'end_connection': _cell(cleaned, 17),
                            'valve_status': _cell(cleaned, 20),
                            'comments': _cell(cleaned, 22),
                            'source_doc': 'PN12442-REG-00021',
                        })
    df = pd.DataFrame(rows).drop_duplicates(subset='valve_tag')
    print(f"  Fuel Valve List (REG-00021): {len(df)} valves")
    return df


def extract_valve_list_npi(path):
    """Extract valve data from REG-00009 (NPI & Dome Shelter Valve List)."""
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cleaned = [str(c).strip() if c else '' for c in row]
                    tag = _find_in_row(cleaned, r'(?:VA|VW)-\d{4}-\d{3}')
                    if tag:
                        pid = _find_in_row(cleaned, r'HD4-\d{4}-F-\d{5}')
                        rows.append({
                            'valve_tag': tag,
                            'size': _cell(cleaned, 1),
                            'valve_code': _cell(cleaned, 2),
                            'fluid_type': _cell(cleaned, 4),
                            'area_no': _cell(cleaned, 8),
                            'pid_no': pid,
                            'line_no': _cell(cleaned, 12),
                            'description': _cell(cleaned, 15),
                            'end_connection': _cell(cleaned, 17),
                            'valve_status': '',
                            'comments': _cell(cleaned, 19),
                            'source_doc': 'PN12442-REG-00009',
                        })
    df = pd.DataFrame(rows).drop_duplicates(subset='valve_tag')
    print(f"  NPI/Dome Valve List (REG-00009): {len(df)} valves")
    return df


def extract_mech_equip_fuel(path):
    """Extract equipment data from REG-00019 (Fuel Facility Mech Equipment List)."""
    rows = []
    keywords = ['HME REFUEL', 'DIESEL', 'AIR', 'LUBE', 'COOLANT', 'GREASE',
                'FIRE', 'OILY', 'WASTE', 'BOOM', 'WASH', 'SAFETY', 'STRAINER',
                'PRESSURE', 'ACCUMULATOR', 'HOSE', 'FILTER', 'SEPARATOR', 'RECEIVER',
                'COMPRESSOR', 'DRYER', 'PUMP', 'TANK', 'LOADING', 'DAVIT', 'SUMP',
                'EXTINGUISHER', 'SPILL']
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cleaned = [str(c).strip() if c else '' for c in row]
                    tag = _find_in_row(cleaned, r'BD2947\.\w+')
                    if tag and tag != 'BD2947':
                        pid = _find_in_row(cleaned, r'HD4-\d{4}-[A-Z]-\d{5}')
                        desc = ''
                        for c in cleaned:
                            if any(kw in c.upper() for kw in keywords) and len(c) > len(desc):
                                desc = c
                        rows.append({
                            'equip_tag': tag,
                            'description': desc,
                            'pid_no': pid,
                            'source_doc': 'PN12442-REG-00019',
                        })
    df = pd.DataFrame(rows).drop_duplicates(subset='equip_tag')
    print(f"  Fuel Mech Equip List (REG-00019): {len(df)} items")
    return df


def extract_mech_equip_npi(path):
    """Extract equipment data from REG-00018 (NPI & Dome Shelter Mech Equipment List)."""
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cleaned = [str(c).strip() if c else '' for c in row]
                    tag = _find_in_row(cleaned, r'BD194[23]\.\w+')
                    if tag:
                        pid = _find_in_row(cleaned, r'HD4-\d{4}-[A-Z]-\d{5}')
                        desc = ''
                        for c in cleaned:
                            if any(kw in c.upper() for kw in ['DOME', 'NPI', 'HAUL', 'TEXAS']) and len(c) > len(desc):
                                desc = c
                        rows.append({
                            'equip_tag': tag,
                            'description': desc,
                            'pid_no': pid,
                            'source_doc': 'PN12442-REG-00018',
                        })
    df = pd.DataFrame(rows).drop_duplicates(subset='equip_tag')
    print(f"  NPI/Dome Mech Equip List (REG-00018): {len(df)} items")
    return df


def extract_line_list_fuel(path):
    """Extract line data from REG-00020 (Fuel Facility Line List)."""
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cleaned = [str(c).strip() if c else '' for c in row]
                    line = _find_in_row(cleaned, r'HD4-\d{4}-[A-Z]{2,3}-\d{4}-\d+-[A-Z0-9]+')
                    if line:
                        rows.append({
                            'line_number': line,
                            'source_doc': 'PN12442-REG-00020',
                        })
    df = pd.DataFrame(rows).drop_duplicates(subset='line_number')
    print(f"  Fuel Line List (REG-00020): {len(df)} lines")
    return df


def extract_special_items(path):
    """Extract special items from REG-00022."""
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cleaned = [str(c).strip() if c else '' for c in row]
                    sp = _find_in_row(cleaned, r'SP-\d{3}')
                    if sp:
                        pid = _find_in_row(cleaned, r'HD4-\d{4}-[A-Z]-\d{5}')
                        rows.append({
                            'sp_tag': sp,
                            'pid_no': pid,
                            'source_doc': 'PN12442-REG-00022',
                        })
    df = pd.DataFrame(rows).drop_duplicates(subset='sp_tag')
    print(f"  Special Items (REG-00022): {len(df)} items")
    return df


def extract_tiein_list(path):
    """Extract tie-in points from REG-00023."""
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cleaned = [str(c).strip() if c else '' for c in row]
                    tip = _find_in_row(cleaned, r'TIP\d{2}[AB]?')
                    if tip:
                        rows.append({
                            'tiein_tag': tip,
                            'source_doc': 'PN12442-REG-00023',
                        })
    df = pd.DataFrame(rows).drop_duplicates(subset='tiein_tag')
    print(f"  Tie-in List (REG-00023): {len(df)} tie-ins")
    return df
