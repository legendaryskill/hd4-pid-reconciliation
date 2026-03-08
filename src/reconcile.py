"""
Cross-reference P&ID-extracted data against valve lists and equipment lists.
Produces reconciliation DataFrames with status flags and discrepancy notes.

Design principles:
- Valve list (REG-00021/00009) is authoritative for valve status, size, spec
- Mech equipment list (REG-00019/00018) is authoritative for equipment specs
- P&ID extraction is used for EXISTENCE checks and size/spec COMPARISON only
- Valve position (NO/NC/LO/LC/FC) is NOT compared -- P&ID extraction of these
  is unreliable due to ambiguity with RTIO line service codes (LO=Lube Oil,
  FO=Fuel Oil, etc.)
"""
import pandas as pd


def reconcile_valves(pid_valves, valve_list_combined):
    """
    Compare valves found on P&IDs against the official valve list.
    Focuses on existence and size/spec matching.
    Valve status is carried from the list as informational only -- not compared.
    """
    list_tags = set(valve_list_combined['valve_tag'].str.strip().values)
    list_lookup = {}
    for _, row in valve_list_combined.iterrows():
        tag = row['valve_tag'].strip()
        if tag not in list_lookup:
            list_lookup[tag] = row

    results = []
    pid_tags_seen = set()

    for _, row in pid_valves.iterrows():
        tag = str(row.get('Valve Tag', '')).strip()
        if not tag or tag == 'nan':
            continue
        pid_tags_seen.add(tag)

        on_list = tag in list_tags
        notes = ''
        status = 'OK'
        list_status = ''
        list_size = ''
        list_spec = ''

        if on_list:
            m = list_lookup.get(tag)
            if m is not None:
                list_status = str(m.get('valve_status', '')).strip()
                list_size = str(m.get('size', '')).strip()
                list_spec = str(m.get('valve_code', '')).strip()

                # Size comparison (only if both sides have data)
                pid_size = str(row.get('Size', '')).strip()
                if (list_size and pid_size
                        and list_size not in ('', 'nan', 'None')
                        and pid_size not in ('', 'nan', 'None')
                        and list_size != pid_size):
                    notes = f'Size mismatch: P&ID={pid_size}, List={list_size}'
                    status = 'MISMATCH -- REVIEW'

                # Spec code comparison
                pid_spec = str(row.get('Valve Type / Spec', '')).strip()
                if (list_spec and pid_spec
                        and list_spec not in ('', 'nan', 'None')
                        and pid_spec not in ('', 'nan', 'None')
                        and list_spec != pid_spec):
                    spec_note = f'Spec mismatch: P&ID={pid_spec}, List={list_spec}'
                    notes = f'{notes}; {spec_note}'.strip('; ')
                    status = 'MISMATCH -- REVIEW'
        else:
            status = 'MISSING FROM VALVE LIST'
            notes = 'On P&ID but not found on valve list -- confirm with design team'

        results.append({
            'valve_tag': tag,
            'pid_size': str(row.get('Size', '')),
            'pid_spec': str(row.get('Valve Type / Spec', '')),
            'pid_drawing': str(row.get('P&ID Drawing No.', '')),
            'pid_description': str(row.get('P&ID Description', '')),
            'list_size': list_size,
            'list_spec': list_spec,
            'list_status': list_status,
            'on_valve_list': 'Y' if on_list else 'N',
            'status': status,
            'discrepancy_notes': notes,
        })

    # Valves on list but NOT found in P&ID extraction
    for _, row in valve_list_combined.iterrows():
        tag = row['valve_tag'].strip()
        if tag not in pid_tags_seen:
            results.append({
                'valve_tag': tag,
                'pid_size': '',
                'pid_spec': '',
                'pid_drawing': row.get('pid_no', ''),
                'pid_description': '',
                'list_size': str(row.get('size', '')),
                'list_spec': str(row.get('valve_code', '')),
                'list_status': str(row.get('valve_status', '')),
                'on_valve_list': 'Y',
                'status': 'EXTRA (on list, not in P&ID extract)',
                'discrepancy_notes': (
                    f'On {row["source_doc"]} but not in P&ID extraction '
                    f'-- likely on drawing but not captured from PDF'
                ),
            })

    return pd.DataFrame(results)


def reconcile_equipment(pid_equip, equip_list_combined):
    """
    Compare equipment found on P&IDs against the official equipment list.
    Handles tag naming convention differences (PRV-00x vs BD2947.PRVxxx)
    and separates instrument items from mechanical items.
    """
    list_tags = set(equip_list_combined['equip_tag'].str.strip().values)

    # Build lookup for PRV tag convention matching
    prv_map = {}
    for tag in list_tags:
        if '.PRV' in tag:
            parts = tag.split('.PRV')
            if len(parts) == 2 and len(parts[1]) >= 3:
                prv_map[f'PRV-{parts[1][:3]}'] = tag

    # Build lookup for dryer tag convention (DRYR01 vs DY01)
    dryer_map = {}
    for tag in list_tags:
        if '.DY' in tag:
            parts = tag.split('.DY')
            if len(parts) == 2:
                prefix = parts[0]
                num = parts[1]
                dryer_map[f'{prefix}.DRYR{num}'] = tag

    instrument_prefixes = [
        '.PDT', '.FS0', '.FT0', '.FQ0', '.ESS', '.SV0', '.SV1',
        '.ZS', '.LS0', '.PCV', '.PIT', '.FAL', '.PAL', '.PAH',
        '.LAH', '.LAL', '.LSH', '.LIT', '.PDI', '.PDS', '.PDAH',
    ]

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
            # Check PRV naming convention
            if tag.startswith('PRV-') and tag in prv_map:
                status = 'TAG MISMATCH'
                notes = (
                    f'P&ID uses "{tag}", equip list uses "{prv_map[tag]}" '
                    f'-- same item, confirm tag convention with design team'
                )
            elif tag.endswith(')') and 'Dome' in tag:
                status = 'TAG MISMATCH'
                notes = 'Dome shelter item -- check tag convention against REG-00018'
            # Check dryer naming convention
            elif tag in dryer_map:
                status = 'TAG MISMATCH'
                notes = (
                    f'P&ID uses "{tag}", equip list uses "{dryer_map[tag]}" '
                    f'-- same item, confirm tag convention'
                )
            # Check if instrument/control item
            elif any(prefix in tag for prefix in instrument_prefixes):
                status = 'INSTRUMENT (not on mech list)'
                notes = (
                    'Instrument/control item -- expected on I&C instrument '
                    'index rather than mechanical equipment list'
                )
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

    # Equipment on list but NOT in P&ID extraction
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
                'discrepancy_notes': (
                    f'On {row["source_doc"]} -- may be non-P&ID item '
                    f'(boom gate, fire extinguisher, etc.) or extraction miss'
                ),
            })

    return pd.DataFrame(results)
