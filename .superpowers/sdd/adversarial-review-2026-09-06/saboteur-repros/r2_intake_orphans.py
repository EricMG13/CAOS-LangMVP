import asyncio, sys, shutil, io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from harness import *
from starlette.datastructures import UploadFile, Headers
from caos.intake.service import IntakeService, IntakeRefused
import sqlalchemy as sa
from caos.storage.store import sources, cases


def up(name, body):
    return UploadFile(file=io.BytesIO(body), filename=name, headers=Headers({"content-type": "text/plain"}))


def vault_state(settings):
    files = [p for p in (settings.storage_dir / "sources").rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


async def main():
    tmp = Path(__file__).parent / "data_r2"
    shutil.rmtree(tmp, ignore_errors=True)
    settings, store, engine = make(tmp)
    svc = IntakeService(store=store, engine=None, settings=settings)
    big1 = b"Issuer Alpha annual report line\n" * 200_000   # ~6.4 MB each
    big2 = b"Issuer Alpha annual report other line\n" * 200_000
    try:
        await svc.submit(actor="analyst", uploads=[up("report.txt", big1), up("report.txt", big2)], case_id=None)
    except IntakeRefused as exc:
        print("refused:", exc.code)
    print("vault files left behind (count, bytes):", vault_state(settings))
    with store.engine.connect() as conn:
        print("source rows:", conn.execute(sa.select(sa.func.count()).select_from(sources)).scalar_one(),
              "case rows:", conn.execute(sa.select(sa.func.count()).select_from(cases)).scalar_one())
    # a pack with one inadmissible file (wrong suffix) beside a valid 6 MB document
    try:
        await svc.submit(actor="analyst", uploads=[up("report2.txt", big1 + b"v2\n"), up("tool.exe", b"MZ")], case_id=None)
    except IntakeRefused as exc:
        print("refused again:", exc.code)
    print("vault files after second refusal (count, bytes):", vault_state(settings))
    with store.engine.connect() as conn:
        print("source rows:", conn.execute(sa.select(sa.func.count()).select_from(sources)).scalar_one())
    store.close()


asyncio.run(main())
