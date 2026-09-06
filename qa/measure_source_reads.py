"""Compare source read shapes on one isolated fixture; no production-load claim."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'caos/server'))
from fastapi.testclient import TestClient  # noqa: E402
from caos.api import create_app  # noqa: E402
from caos.config import Settings  # noqa: E402
from caos.storage.store import DomainStore  # noqa: E402


def measure() -> dict:
    with tempfile.TemporaryDirectory(prefix='caos-source-reads-') as directory:
        path = Path(directory)
        store = DomainStore.from_url(f'sqlite:///{path / "store.db"}')
        try:
            case = store.create_case('Read profile', 'Issuer', 'Services', 'analyst')['id']
            for index in range(80):
                text = f'Document {index} evidence needle ' + 'x' * 480
                store.ingest({'id': f'src-{index:04}', 'case_id': case, 'filename': f'doc-{index}.txt',
                              'media_type': 'text/plain', 'bytes': len(text) * 160,
                              'sha256': hashlib.sha256(text.encode()).hexdigest(),
                              'blocks': [{'block_id': f'b{block:04}', 'text': text,
                                          'locator': {'line': block}, 'confidence': 'HIGH',
                                          'untrusted_data': True, 'extractor_version': 'profile-v1'}
                                         for block in range(160)]}, 'analyst')
            with TestClient(create_app(settings=Settings(storage_dir=path), store=store, engine=None)) as client:
                paths = {'legacy_inventory': f'/api/cases/{case}/sources',
                         'summary_page': f'/api/cases/{case}/source-summaries',
                         'selected_detail': f'/api/cases/{case}/sources/src-0000',
                         'evidence_search': f'/api/cases/{case}/evidence-search?q=needle'}
                results = {}
                for name, route in paths.items():
                    times, sizes = [], []
                    for _ in range(20):
                        start = time.perf_counter()
                        response = client.get(route, headers={'accept-encoding': 'identity'})
                        assert response.status_code == 200, response.text
                        times.append((time.perf_counter() - start) * 1000)
                        sizes.append(len(response.content))
                    results[name] = {'p50_ms': round(statistics.median(times), 3),
                                     'p95_ms': round(sorted(times)[18], 3), 'response_bytes': max(sizes)}
            return {'schema_version': 'caos.source-read-profile.v1', 'proof': 'LOCAL_READ_SHAPE_BENCHMARK',
                    'measured_at': datetime.now(UTC).isoformat(),
                    'code_sha256': {str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest()
                                    for file in (ROOT / 'caos/server/caos/api/__init__.py',
                                                 ROOT / 'caos/server/caos/storage/store.py', Path(__file__).resolve())},
                    'profile': {'documents': 80, 'blocks_per_document': 160, 'repetitions': 20,
                                'database': 'SQLite', 'transport': 'in-process ASGI, uncompressed',
                                'python': platform.python_version(), 'platform': platform.platform()},
                    'limitations': ['Not the concurrent production lab profile or PERF-009 qualification',
                                    'Legacy inventory returns all documents; summary page returns up to 50',
                                    'No provider, scanner or network latency is measured',
                                    'Shared development host; background workloads are not isolated'], 'results': results}
        finally:
            store.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = measure()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['results'], indent=2))
