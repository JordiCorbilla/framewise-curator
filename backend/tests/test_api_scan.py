import csv
import io
import threading

from conftest import create_scanned
from framewise.db.models import Library, Photo, ScanJob, Session, initialize
from framewise.workers.scan import ScanManager


def test_library_creation_and_validation(client, source):
    assert client.post('/api/libraries', json={"source": str(source / "missing")}).status_code == 422
    result = client.post('/api/libraries', json={"source": str(source)})
    assert result.status_code == 200
    assert client.post('/api/libraries', json={"source": str(source)}).json()['id'] == result.json()['id']
    assert len(client.get('/api/libraries').json()) == 1


def test_manual_decisions_budget_restart_csv_and_xmp(client, source):
    sidecar = source / 'duplicate.xmp'
    sidecar.write_text('<x:xmpmeta xmlns:x="adobe:ns:meta/"><original>keep everything</original></x:xmpmeta>')
    original_xmp = sidecar.read_bytes()
    lib_id, job_id = create_scanned(source)
    response = client.get(f'/api/libraries/{lib_id}/photos').json()
    assert response['total'] == 3
    keeper, reject = response['items'][:2]
    assert client.patch(f"/api/photos/{keeper['id']}/decision", json={"decision": "keep", "stars": 5}).status_code == 200
    client.patch(f"/api/photos/{reject['id']}/decision", json={"decision": "reject"})
    assert client.patch(f'/api/libraries/{lib_id}/budget', json={"budget": 100}).status_code == 200
    initialize()  # Simulates application reopening using the same database.
    selected = client.get(f'/api/libraries/{lib_id}/photos?filter=selected').json()['items']
    assert keeper['id'] in {p['id'] for p in selected}
    assert reject['id'] not in {p['id'] for p in selected}
    assert client.get(f"/api/photos/{keeper['id']}").json()['stars'] == 5
    for filename, count in [('all_photos.csv',3),('selected_photos.csv',2)]:
        response = client.get(f'/api/libraries/{lib_id}/export/{filename}')
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        assert len(rows) == count
        assert all(row['original_path'].startswith(str(source)) for row in rows)
        assert any(row['filename'] == 'frame, 你好.JPG' for row in rows)
    assert client.get(f'/api/jobs/{job_id}').json()['scored'] == 0
    preview = client.get(f'/api/libraries/{lib_id}/xmp/preview').json()
    assert not preview['enabled'] and preview['conflicts']
    assert client.post(f'/api/libraries/{lib_id}/xmp/confirm', json={}).status_code == 409
    assert sidecar.read_bytes() == original_xmp


def test_security_pagination_preview_and_filters(client, source):
    lib_id, _ = create_scanned(source)
    assert client.post('/api/libraries', json={"source": str(source)}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post('/api/libraries', content='{}', headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.get('/api/libraries', headers={"Host": "evil.example"}).status_code == 400
    assert client.get(f'/api/libraries/{lib_id}/photos?filter=unknown').status_code == 422
    assert client.get(f'/api/libraries/{lib_id}/photos?limit=10000').status_code == 422
    page = client.get(f'/api/libraries/{lib_id}/photos?limit=1&page=2').json()
    assert page['total'] == 3 and len(page['items']) == 1
    assert client.get(page['items'][0]['thumbnail']).headers['content-type'] == 'image/jpeg'
    assert client.get('/api/photos/unknown/preview').status_code == 404
    assert client.patch(f"/api/photos/{page['items'][0]['id']}/decision", json={"stars": 6}).status_code == 422
    assert client.patch(f'/api/libraries/{lib_id}/weights', json={"aesthetic":1,"sharpness":0,"exposure":0}).status_code == 422


def test_cancellation_and_resume_cache(source, monkeypatch):
    from framewise.workers import scan
    image = next(source.glob('*.JPG')).read_bytes()
    for n in range(16):
        (source / f'extra-{n}.jpg').write_bytes(image)
    with Session.begin() as db:
        library = Library(source=str(source), name='Resume fixture')
        db.add(library)
        db.flush()
        job = ScanJob(library_id=library.id)
        db.add(job)
        db.flush()
        lib_id, first_id = library.id, job.id
    stop = threading.Event()
    original = scan.acquire
    calls = []
    def interrupted(*args):
        calls.append(args[0])
        stop.set()
        return original(*args)
    monkeypatch.setattr(scan, 'acquire', interrupted)
    manager = ScanManager()
    manager.run(first_id, stop)
    with Session.begin() as db:
        assert db.get(ScanJob, first_id).status == 'cancelled'
        assert db.query(Photo).filter_by(status='ready').count() == 8
        next_job = ScanJob(library_id=lib_id)
        db.add(next_job)
        db.flush()
        next_id = next_job.id
    monkeypatch.setattr(scan, 'acquire', original)
    manager.run(next_id, threading.Event())
    with Session() as db:
        result = db.get(ScanJob, next_id)
        assert result.status == 'complete'
        assert result.progress['reused'] == 8
        assert result.progress['thumbnails'] == 19


def test_corrupt_file_isolated_and_sse(client, source):
    (source / 'broken.NEF').write_bytes(b'broken')
    lib_id, job_id = create_scanned(source)
    data = client.get(f'/api/jobs/{job_id}').json()
    assert data['status'] == 'complete' and data['failed'] == 1 and data['thumbnails'] == 3
    assert 'data: ' in client.get(f'/api/jobs/{job_id}/events').text
    assert client.get(f'/api/libraries/{lib_id}/photos?filter=failed').json()['total'] == 1


def test_startup_marks_interrupted_jobs():
    with Session.begin() as db:
        lib = Library(source='/fixture', name='fixture')
        db.add(lib)
        db.flush()
        job = ScanJob(library_id=lib.id, status='running')
        db.add(job)
        db.flush()
        job_id = job.id
    initialize()
    with Session() as db:
        assert db.get(ScanJob, job_id).status == 'interrupted'
