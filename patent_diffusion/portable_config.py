"""Versioned portable method contract. Frozen paper modules do not import this."""
import copy
import hashlib
import json
import re
from pathlib import Path
import pandas as pd


DEFAULTS = {
    'schema_version': 'portable_v1',
    'metadata': {},
    'inputs': {'family_columns': {}, 'edge_columns': {}, 'classification_system': 'WIPO35',
               'id_policy': 'opaque_string_reject_float'},
    'comparison': {'type': 'technology', 'groups': ['A', 'B'], 'group_definition': '',
                   'country_basis': None, 'cutoff': None, 'windows_years': [1, 3, 5],
                   'observation_origin': 'first_eligible_grant_in_declared_office_scope',
                   'grant_office_scope': []},
    'matching': {'method': 'exact_1_to_1_without_replacement', 'columns': ['grant_quarter', 'focal_field'],
                 'cluster_columns': ['grant_quarter', 'focal_field'], 'seed': 20260907},
    'quality': {'classified_edge_coverage_min': .985, 'absolute_missing_rate_gap_max_exclusive': .01,
                'minimum_effective_clusters_for_inference': 30,
                'failed_field_quality_action': 'entry_only_plus_exploratory_classification_complete_description'},
    'reference': {'enabled': True, 'main_pool': 'pooled_groups', 'crossfit_folds': 5,
        'fold_unit': 'matched_pair', 'fold_seed': 20260918, 'lag_bands_calendar_years': [1, 3, 5],
        'calendar_block_years': 3, 'calendar_anchor_year': 2019,
        'grant_cohort_block_years': 3, 'grant_cohort_anchor_year': 2019,
        'minimum_donor_edges': 200, 'minimum_distinct_citing_families': 50,
        'fallback': ['same_field_same_lag_drop_calendar', 'same_field_drop_lag'],
        'unsupported_action': 'exclude_entire_pair_from_this_reference_estimand', 'cross_field_pooling': False,
        'simulation': {'initial': 2000, 'increment': 2000, 'maximum': 10000, 'mcse_target_pp': .1,
                       'precision_endpoints': ['H4', 'H5'], 'seed_base': 20260919},
        'inference': {'bootstrap_unit': 'matching_cell', 'bootstrap_replicates': 2000,
            'bootstrap_seed': 20260920, 'primary_interval': 'conditional_on_estimated_pool',
            'p_method': 'approximate_two_sided_wald_using_bootstrap_se',
            'multiplicity': 'holm_H4_H5_across_prespecified_windows',
            'undefined_test_policy': 'retain_family_size_display_null'},
        'sensitivities': ['group_b_only_donors', 'additional_grant_cohort_stratum',
                         'reweighted_pool_fixed_support', 'unique_field_event_rule', 'cross_only_event_rule'],
        'reweighted_pool': {'bootstrap_replicates': 2000, 'bootstrap_seed': 20260921,
            'field_seed_base': 20270000, 'zero_weight_pool_action': 'explicit_failed_draw_no_uniform_fallback',
            'inner_simulation': {'initial': 50, 'increment': 50, 'maximum': 2000, 'mcse_target_pp': .1,
                'precision_endpoints': ['H4', 'H5'], 'failure_action': 'whole_sensitivity_precision_not_met_no_draw_discard'}},
        'report_variant_intersection_support': True, 'report_reproduced_share': False},
    'execution': {'mode': 'formal', 'offline_analysis': True, 'new_output_directory_only': True},
    'outputs': {'include_input_data_in_default_download': False,
        'record_input_output_method_and_environment_hashes': True, 'strict_json_no_nan_or_infinity': True}
}
INPUT_EXTRA = {'families', 'edges', 'source_manifest', 'classification_mapping_manifest'}


def resolve(raw):
    if not isinstance(raw,dict): raise ValueError('Configuration must be an object')
    if raw.get('schema_version') != 'portable_v1':
        raise ValueError('Require schema_version portable_v1; old configs need --profile legacy_v0_2')
    def merge(base, value, path=''):
        if not isinstance(value, dict): raise ValueError('Object required: ' + path)
        for key, val in value.items():
            name = path + key
            if key not in base:
                if path == 'inputs.' and key in INPUT_EXTRA:
                    base[key] = val; continue
                if path in ('metadata.', 'inputs.family_columns.', 'inputs.edge_columns.'):
                    base[key] = val; continue
                raise ValueError('Unknown configuration field: ' + name)
            if isinstance(base[key], dict): merge(base[key], val, name + '.')
            else: base[key] = val
    c = copy.deepcopy(DEFAULTS); merge(c, raw)
    comp = c['comparison']; groups = comp['groups']
    if not isinstance(groups, list) or len(groups) != 2 or any(not isinstance(x, str) or not x.strip() for x in groups) or groups[0] == groups[1]:
        raise ValueError('Two different nonempty string group labels required')
    if comp['type'] not in ('country', 'technology', 'other') or not isinstance(comp['group_definition'],str) or not comp['group_definition'].strip():
        raise ValueError('Explicit comparison type and group definition required')
    if comp['type'] == 'country' and comp['country_basis'] not in ('applicant','inventor','priority','grant_office','other_explicit'):
        raise ValueError('Country basis required')
    if not isinstance(comp['grant_office_scope'],list) or not comp['grant_office_scope'] or any(not isinstance(x,str) or not re.fullmatch('[A-Z]{2}',x) for x in comp['grant_office_scope']):
        raise ValueError('Declare grant_office_scope')
    if not isinstance(comp['cutoff'],str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',comp['cutoff']): raise ValueError('ISO YYYY-MM-DD cutoff required')
    date = pd.Timestamp(comp['cutoff'])
    if pd.isna(date) or date.tz is not None or date != date.normalize(): raise ValueError('Calendar cutoff required')
    years = comp['windows_years']
    if not isinstance(years,list) or not years or any(type(x) is not int or x not in range(1,6) for x in years) or len(set(years)) != len(years):
        raise ValueError('Unique integer year windows 1..5 required')
    comp['windows_years'] = sorted(years)
    m = c['matching']
    if not isinstance(m['columns'],list) or any(not isinstance(x,str) for x in m['columns']) or 'focal_field' not in m['columns'] or len(set(m['columns'])) != len(m['columns']) or m['cluster_columns'] != m['columns']:
        raise ValueError('Match on focal_field; cluster columns must equal matching columns')
    # These are method choices, not effect-tuning switches.
    mutable = {'reference.enabled', 'reference.calendar_anchor_year', 'reference.grant_cohort_anchor_year',
               'reference.fold_seed', 'reference.simulation.seed_base', 'reference.inference.bootstrap_seed',
               'reference.reweighted_pool.bootstrap_seed', 'reference.reweighted_pool.field_seed_base'}
    def fixed(actual, defaults, prefix):
        for k,v in defaults.items():
            p=prefix+k
            if p in mutable: continue
            if isinstance(v,dict): fixed(actual[k],v,p+'.')
            elif type(actual[k]) is not type(v) or actual[k] != v: raise ValueError('Fixed portable_v1 method policy: '+p)
    fixed(c['quality'],DEFAULTS['quality'],'quality.')
    fixed(c['reference'],DEFAULTS['reference'],'reference.')
    fixed(c['outputs'],DEFAULTS['outputs'],'outputs.')
    if m['method'] != DEFAULTS['matching']['method'] or c['inputs']['classification_system'] != 'WIPO35' or c['inputs']['id_policy'] != DEFAULTS['inputs']['id_policy']:
        raise ValueError('Unsupported input/matching method')
    if comp['observation_origin'] != DEFAULTS['comparison']['observation_origin']: raise ValueError('Unsupported observation origin')
    if c['execution']['mode'] not in ('formal','smoke') or c['execution']['offline_analysis'] is not True or c['execution']['new_output_directory_only'] is not True:
        raise ValueError('Unsupported execution policy')
    if type(c['reference']['enabled']) is not bool: raise ValueError('reference.enabled must be boolean')
    for seed in [m['seed'],c['reference']['fold_seed'],c['reference']['simulation']['seed_base'],c['reference']['inference']['bootstrap_seed'],c['reference']['reweighted_pool']['bootstrap_seed'],c['reference']['reweighted_pool']['field_seed_base']]:
        if type(seed) is not int or not 0 <= seed < 2**32: raise ValueError('Seeds must be uint32 integers')
    for k in ('calendar_anchor_year','grant_cohort_anchor_year'):
        if type(c['reference'][k]) is not int or not 1700 <= c['reference'][k] <= 2200: raise ValueError('Invalid calendar anchor')
    return c


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''): h.update(b)
    return h.hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def contract(c):
    return {'method_id':'portable_v1', 'design_date':'2026-10-14', 'kind':'versioned design, not historical preregistration',
        'definitions': {'H1':'first distinct external family citation', 'H3':'first nonfocal field arrival',
            'H4':'second distinct family in same external field on a strictly later date',
            'H5':'previously unreached external field first arrives strictly after earliest H4'},
        'estimand':'pair-weighted A minus B on identical reference-supported pairs; residual = observed minus reference',
        'inference_scope':'matching-cell independent sampling assumption; conditional and fixed-support reweighted pools',
        'configuration':c}
