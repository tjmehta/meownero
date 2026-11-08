#!/usr/bin/env python3
"""Synthetic aggregation through actual staged controller and report exporter.

No Windows executable runs. Historical ARM receipts provide shaped journey data;
only the native execution boundary is replaced. Do not use reports as acceptance.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bundle', type=Path, required=True)
parser.add_argument('--arm-report', type=Path, required=True)
parser.add_argument('--controls-report', type=Path, required=True)
parser.add_argument('--evidence', type=Path, required=True)
args = parser.parse_args()
args.evidence.mkdir(parents=True, exist_ok=True)

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

with zipfile.ZipFile(args.arm_report) as z:
    historical_journey = json.loads(z.read('public/journey.json'))
with zipfile.ZipFile(args.controls_report) as z:
    incomplete_controls = json.loads(z.read('public/controls.json'))

observed = []
for scenario, expected, exit_code in [('incomplete', 'INCOMPLETE_NATIVE_ARCHIVE_CONTROLS', 2),
        ('full', 'PASS_NATIVE_ARCHIVE_JOURNEY_AND_TEN_CONTROLS', 0), ('refusal-failed', 'FAIL', 1)]:
    with tempfile.TemporaryDirectory(prefix='tjs1882-export-boundary-') as folder:
        root = Path(folder)
        with zipfile.ZipFile(args.bundle) as z: z.extractall(root)
        runner = load('bound_runner', root / 'meownero-windows-test/windows-test-bundle.py')
        def run_controller(path, run_name):
            controller = load('bound_controller', Path(path))
            controller.os = SimpleNamespace(**{**vars(os), 'name': 'nt'})
            def native_boundary(package, out, row):
                journey = copy.deepcopy(historical_journey)
                journey.update(release_manifest_sha256=row['release_manifest_sha256'], program_sha256=row['program_sha256'],
                    evidence='SYNTHETIC_NO_WINDOWS_EXECUTION')
                (out / 'journey').mkdir()
                (out / 'journey/result.json').write_text(json.dumps(journey))
                controls = copy.deepcopy(incomplete_controls)
                controls.update(release_manifest_sha256=row['release_manifest_sha256'], evidence='SYNTHETIC_NO_WINDOWS_EXECUTION')
                if scenario == 'full':
                    controls['cases'][4] = {'case': 'symlink-directory', 'refused': True}
                    controls['result'] = 'PASS_REFUSALS'
                elif scenario == 'refusal-failed':
                    controls['cases'][4] = {'case': 'symlink-directory', 'refused': False}
                    controls['result'] = 'FAIL_REFUSALS'
                (out / 'controls').mkdir()
                (out / 'controls/controls.json').write_text(json.dumps(controls))
                check = {'schema': 'meownero-native-windows-ci-check/1',
                    'result': 'INCOMPLETE_NATIVE_ARCHIVE_CONTROLS' if scenario == 'incomplete' else 'PASS_NATIVE_ARCHIVE_JOURNEY',
                    'native_architecture': 'aarch64', 'package_architecture': 'aarch64', 'execution_substrate': 'NATIVE',
                    'phases': [], 'owned_job': {'active_processes': 0},
                    'native_cli_event': {'status': 'NOT_REQUESTED', 'cause': 'UNKNOWN'}}
                (out / 'check-receipt.json').write_text(json.dumps(check))
            controller.windows_check = native_boundary
            with patch.object(controller.platform, 'machine', lambda: 'ARM64'):
                controller.main()
        with patch.object(sys, 'argv', ['runner']), patch.object(runner, 'native_target', lambda: 'windows-aarch64'), \
             patch.object(runner.runpy, 'run_path', run_controller):
            status = runner.main()
        assert status == exit_code, (scenario, status)
        reports = list(runner.ROOT.glob('run-*/report.zip')); assert len(reports) == 1
        data = reports[0].read_bytes()
        with zipfile.ZipFile(reports[0]) as z:
            receipt = json.loads(z.read('bundle-receipt.json'))
            proof = json.loads(z.read('public/ci-receipt.json'))
            assert receipt['result'] == proof['result'] == expected
            if scenario == 'incomplete':
                controls = json.loads(z.read('public/controls.json'))
                assert 'refused' not in controls['cases'][4]
                assert len(controls['cases']) == 10
        name = 'synthetic-' + scenario + '-report.zip'
        (args.evidence / name).write_bytes(data)
        observed.append({'scenario': scenario, 'result': expected, 'exit': status, 'report': name,
            'report_sha256': hashlib.sha256(data).hexdigest(), 'evidence': 'SYNTHETIC_NO_WINDOWS_EXECUTION'})
(args.evidence / 'aggregation.json').write_text(json.dumps(observed, indent=2) + '\n')
print('PASS_SYNTHETIC_STAGED_CONTROLLER_AND_BUNDLE_EXPORT', len(observed))
