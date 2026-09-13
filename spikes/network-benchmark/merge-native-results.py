#!/usr/bin/env python3
"""Require passing, disjoint DNS/offline partitions of the unchanged CI selection."""
from pathlib import Path
import xml.etree.ElementTree as ET


def merge(out: Path):
    expected = set()
    suite = ''
    for line in (out / 'native-expected.txt').read_text().splitlines():
        clean = line.split('#', 1)[0].strip()
        if clean.endswith('.') and not line.startswith(' '):
            suite = clean
        elif line.startswith('  ') and clean:
            name = suite + clean
            if not suite or name in expected:
                raise ValueError('invalid or duplicate expected test: ' + name)
            expected.add(name)
    if not expected:
        raise ValueError('empty expected test selection')
    combined = ET.Element('testsuites')
    observed = set()
    for phase in ('full-native-offline', 'dns'):
        root = ET.parse(out / (phase + '.xml')).getroot()
        cases = root.findall('./testsuite/testcase')
        if (not cases or int(root.attrib['tests']) != len(cases)
                or any(int(root.attrib.get(key, 0)) for key in ('failures', 'errors', 'disabled', 'skipped'))):
            raise ValueError('failed, empty or inconsistent phase: ' + phase)
        for case in cases:
            name = case.attrib['classname'] + '.' + case.attrib['name']
            if (name in observed or case.find('failure') is not None
                    or case.find('error') is not None or case.find('skipped') is not None
                    or case.attrib.get('status') != 'run'
                    or case.attrib.get('result', 'completed') != 'completed'):
                raise ValueError('duplicate, failed or unexecuted test: ' + name)
            observed.add(name)
        combined.extend(root)
    if observed != expected:
        raise ValueError(f'coverage mismatch: missing={sorted(expected-observed)}, extra={sorted(observed-expected)}')
    combined.attrib.update(tests=str(len(observed)), failures='0', errors='0', name='AllTests')
    ET.ElementTree(combined).write(out / 'full-native.xml')
