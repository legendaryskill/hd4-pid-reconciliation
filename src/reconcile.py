"""
Cross-reference P&ID-extracted data against valve lists and equipment lists.
Produces reconciliation DataFrames with status flags and discrepancy notes.
"""
import pandas as pd


def reconcile_valves(pid_valves, valve_list_combined):
    """
    Compare valves found on P&IDs against the official valve list.

    Args:
        pid_valves: DataFrame from the P&ID baseline spreadsheet (Valve Register tab)
        valve_list_combined: DataFrame of all valves from REG valve lists

    Returns:
        DataFrame with reconciliation results
    """
    list_tags = set(valve_list_combined['valve_tag'].str.strip().values)
    list_lookup = valve_list_combined.set_index('valve_tag')

    results = []
    pid_tags_seen = set()

    for _, row in pid_valves.iterrows():
        tag = str(row.get('Valve Tag', '')).strip()
        if not tag or tag == 'nan':
            continue
        pid_tags_seen.add(tag)

        on_list = tag in list_tags
        notes = ''
        list_status = ''
        status = 'OK'

        if on_list:
            m = list_lookup.loc[tag] if tag in list_lookup.index else None
            if m is not None:
                if isinstance(m, pd.DataFrame):
                    m = m.iloc[0]  # handle duplicates
                list_status = str(m.get('valve_status', '')).strip()
                pid_status = str(row.get('Normal Position', '')).strip()

                # Status comparison
                if pid_status in ('', 'nan', 'None') and list_status not in ('', 'nan', 'None', 'N/A'):
                    status = 'CHECK (P&ID status not extracted)'
                    notes = f'List status={list_status}, P&ID status not readable — verify on drawing'
                elif list_status not in ('', 'nan', 'None', 'N/A') and pid_status not in ('', 'nan', 'None'):
                    if list_status != pid_status:
                        status = 'MISMATCH — REVIEW'
                        notes = f'Status mismatch: P&ID={pid_status}, List={list_status}'

                # Size comparison
                list_size = str(m.get('size', '')).strip()
                pid_size = str(row.get('Size', '')).strip()
                if list_size and pid_size and list_size != pid_size and pid_size != 'nan':
                    size_note = f'Size mismatch: P&ID={pid_size}, List={list_size}'
                    notes = f'{notes}; {size_note}'.strip('; ') if notes else size_note
                    status = 'MISMATCH — REVIEW'
        else:
            status = 'MISSING FROM VALVE LIST'
            notes = 'On P&ID but not found on valve list'

        results.append({
            'valve_tag': tag,
            'pid_size': str(row.get('Size', '')),
            'pid_type': str(row.get('Valve Type / Spec', '')),
            'pid_status': str(row.get('Normal Position', '')),
            'pid_drawing': str(row.get('P&ID Drawing No.', '')),
            'pid_description': str(row.get('P&ID Description', '')),
            'on_valve_list': 'Y' if on_list else 'N',
            'list_status': list_status,
            'status': status,
            'discrepancy_notes': notes,
        })

    # Valves on list but NOT on P&IDs
    for _, row in valve_list_combined.iterrows():
        tag = row['valve_tag'].strip()
        if tag not in pid_tags_seen:
            results.append({
                'valve_tag': tag,
                'pid_size': '',
                'pid_type': '',
                'pid_status': '',
                'pid_drawing': row.get('pid_no', ''),
                'pid_description': '',
                'on_valve_list': 'Y',
                'list_status': str(row.get('valve_status', '')),
                'status': 'EXTRA (on list, not in P&ID extract)',
                'discrepancy_notes': f'On {row["source_doc"]} but not in P&ID extraction — verify on drawing',
            })

    return pd.DataFrame(results)


def reconcile_equipment(pid_equip, equip_list_combined):
    """
    Compare equipment found on P&IDs against the official equipment list.
    Also handles tag naming convention differences (PRV-00x vs BD2947.PRVxxx)
    and separates instrument items from mechanical items.
    """
    list_tags = set(equip_list_combined['equip_tag'].str.strip().values)

    # Build a lookup for fuzzy matching (PRV tags)
    prv_map = {}
    for tag in list_tags:
        if '.PRV' in tag:
            # BD2947.PRV001 -> PRV-001
            m = tag.split('.PRV')
            if len(m) == 2:
                prv_map[f'PRV-{m[1][:3]}'] = tag

    instrument_prefixes = ['.PDT', '.FS0', '.FT0', '.FQ0', '.ESS', '.SV0',
                           '.ZS', '.LS0', '.PCV', '.PIT', '.SV1']

    results = []
    pid_tags_seen = set()

    for _, row in pid_equip.iterrows():
        tag = str(row.get('Equipment Tag', '')).strip()
        if not tag or tag == 'nan':
            continue
        pid_tags_seen.add(tag)

        on_list = tag in list_tags
        notes = ''
        status = 'OK' if on_list else 'MISSING'

        if not on_list:
            # Check PRV naming convention mismatch
            if tag.startswith('PRV-') and tag in prv_map:
                status = 'TAG MISMATCH'
                notes = f'P&ID uses "{tag}", equip list uses "{prv_map[tag]}" — same item, confirm tag convention'
            elif tag.endswith(')') and 'Dome' in tag:
                # Handle "PRV-001 (Dome)" type tags
                status = 'TAG MISMATCH'
                notes = f'Dome shelter PRV — check tag convention against REG-00018'
            elif any(prefix in tag for prefix in instrument_prefixes):
                status = 'INSTRUMENT (not on mech list)'
                notes = 'Instrument/control item — check I&C instrument list or instrument index'
            else:
                notes = 'On P&ID but not found on mechanical equipment list'

        results.append({
            'equip_tag': tag,
            'pid_description': str(row.get('Description', '')),
            'pid_type': str(row.get('Type / Service', '')),
            'pid_drawing': str(row.get('P&ID Drawing No.', '')),
            'on_equip_list': 'Y' if on_list else 'N',
            'status': status,
            'discrepancy_notes': notes,
        })

    # Equipment on list but NOT on P&IDs
    for _, row in equip_list_combined.iterrows():
        tag = row['equip_tag'].strip()
        if tag not in pid_tags_seen:
            results.append({
                'equip_tag': tag,
                'pid_description': row.get('description', ''),
                'pid_type': '',
                'pid_drawing': row.get('pid_no', ''),
                'on_equip_list': 'Y',
                'status': 'EXTRA (on list, not in P&ID extract)',
                'discrepancy_notes': f'On {row["source_doc"]} — verify on drawing or may be non-P&ID item (boom gate, fire extinguisher, etc.)',
            })

    return pd.DataFrame(results)
