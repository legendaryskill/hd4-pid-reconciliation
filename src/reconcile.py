"""
Cross-reference P&ID-extracted data against valve lists and equipment lists.

Design principles:
- Valve list is authoritative for valve status, size, spec
- Mech equipment list is authoritative for equipment specs  
- P&ID extraction is used for EXISTENCE checks and size/spec COMPARISON only
- Valve position (NO/NC/LO/LC/FC) is NOT compared (RTIO line code ambiguity)
- VF-series drawings contain existing installation valves not in PN12442 scope
- Size comparison normalises numeric values (25.0 == 25)
- BART/BARF specs on VF drawings are legacy equivalents of V100/V115
"""
import pandas as pd
import re


def _normalise_size(val):
    """Normalise valve size for comparison: '25.0' -> '25', handle nan."""
    s = str(val).strip()
    if s in ('', 'nan', 'None'):
        return ''
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
        return str(f)
    except ValueError:
        return s


# VF-series drawings that contain EXISTING valves (not new PN12442 scope)
EXISTING_DRAWINGS = {
    'HD4-2960-VF-00002',
    'HD4-2960-VF-00003',
    'HD4-2960-VF-00008',
    'HD4-2900-VF-00002',
    'HD4-2900-VF-00004',
    'HD4-2900-VF-00008',
    'HD4-2900-VF-00009',
}

# Legacy spec codes on VF drawings map to current V-series codes
SPEC_EQUIVALENTS = {
    'BART': 'V100',   # bar stock threaded ball valve
    'BARF': 'V115',   # bar stock flanged ball valve
    'GAVF': 'V100',   # gate valve flanged (approximate)
    'CHVF': 'V222',   # check valve flanged
}


def reconcile_valves(pid_valves, valve_list_combined):
    """Compare valves on P&IDs against official valve list."""
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
        pid_drawing = str(row.get('P&ID Drawing No.', '')).strip()
        is_existing = pid_drawing in EXISTING_DRAWINGS

        if on_list:
            m = list_lookup.get(tag)
            if m is not None:
                list_status = str(m.get('valve_status', '')).strip()
                list_size = str(m.get('size', '')).strip()
                list_spec = str(m.get('valve_code', '')).strip()

                # Size comparison (normalised)
                pid_size = _normalise_size(row.get('Size', ''))
                norm_list_size = _normalise_size(list_size)
                if (norm_list_size and pid_size and norm_list_size != pid_size):
                    notes = f'Size mismatch: P&ID={pid_size}, List={norm_list_size}'
                    status = 'MISMATCH -- REVIEW'

                # Spec comparison (with legacy equivalence)
                pid_spec = str(row.get('Valve Type / Spec', '')).strip()
                if pid_spec in ('', 'nan', 'None') or list_spec in ('', 'nan', 'None'):
                    pass
                else:
                    # Normalise legacy specs before comparing
                    pid_spec_norm = SPEC_EQUIVALENTS.get(pid_spec, pid_spec)
                    list_spec_norm = SPEC_EQUIVALENTS.get(list_spec, list_spec)
                    if pid_spec_norm != list_spec_norm:
                        spec_note = f'Spec mismatch: P&ID={pid_spec}, List={list_spec}'
                        notes = f'{notes}; {spec_note}'.strip('; ')
                        status = 'MISMATCH -- REVIEW'

        elif is_existing:
            status = 'EXISTING (not in PN12442 scope)'
            notes = f'Existing valve on {pid_drawing} -- not expected on PN12442 valve list'
        else:
            status = 'MISSING FROM VALVE LIST'
            notes = 'On P&ID but not found on valve list -- confirm with design team'

        results.append({
            'valve_tag': tag,
            'pid_size': _normalise_size(row.get('Size', '')),
            'pid_spec': str(row.get('Valve Type / Spec', '')),
            'pid_drawing': pid_drawing,
            'pid_description': str(row.get('P&ID Description', '')),
            'list_size': list_size,
            'list_spec': list_spec,
            'list_status': list_status,
            'on_valve_list': 'Y' if on_list else 'N',
            'status': status,
            'discrepancy_notes': notes,
        })

    # Valves on list but NOT in P&ID extraction
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
    """Compare equipment on P&IDs against official equipment list."""
    list_tags = set(equip_list_combined['equip_tag'].str.strip().values)

    prv_map = {}
    for tag in list_tags:
        if '.PRV' in tag:
            parts = tag.split('.PRV')
            if len(parts) == 2 and len(parts[1]) >= 3:
                prv_map[f'PRV-{parts[1][:3]}'] = tag

    dryer_map = {}
    for tag in list_tags:
        if '.DY' in tag:
            parts = tag.split('.DY')
            if len(parts) == 2:
                dryer_map[f'{parts[0]}.DRYR{parts[1]}'] = tag

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

        pid_drawing = str(row.get('P&ID Drawing No.', '')).strip()
        is_existing = pid_drawing in EXISTING_DRAWINGS
        on_list = tag in list_tags
        notes = ''
        status = 'OK' if on_list else 'MISSING'

        if not on_list:
            if tag.startswith('PRV-') and tag in prv_map:
                status = 'TAG MISMATCH'
                notes = f'P&ID="{tag}", List="{prv_map[tag]}" -- confirm tag convention'
            elif tag.endswith(')') and 'Dome' in tag:
                status = 'TAG MISMATCH'
                notes = 'Dome shelter item -- check tag convention against REG-00018'
            elif tag in dryer_map:
                status = 'TAG MISMATCH'
                notes = f'P&ID="{tag}", List="{dryer_map[tag]}" -- confirm tag convention'
            elif any(prefix in tag for prefix in instrument_prefixes):
                status = 'INSTRUMENT (not on mech list)'
                notes = 'Instrument/control item -- expected on I&C instrument index'
            elif is_existing:
                status = 'EXISTING (not in PN12442 scope)'
                notes = f'Existing equipment on {pid_drawing}'
            else:
                notes = 'On P&ID but not found on mechanical equipment list'

        results.append({
            'equip_tag': tag,
            'pid_description': str(row.get('Description', '')),
            'pid_type': str(row.get('Type / Service', '')),
            'pid_drawing': pid_drawing,
            'on_equip_list': 'Y' if on_list else 'N',
            'status': status,
            'discrepancy_notes': notes,
        })

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
                    f'On {row["source_doc"]} -- may be non-P&ID item or extraction miss'
                ),
            })

    return pd.DataFrame(results)
