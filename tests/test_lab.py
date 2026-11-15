import http.client
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from lab import Conflict, LabServer, WorkflowManager

FFMPEG = os.environ.get('FFMPEG_PATH') or shutil.which('ffmpeg')
FFPROBE = os.environ.get('FFPROBE_PATH') or shutil.which('ffprobe')


class ValidationTests(unittest.TestCase):
    def test_duration_is_bounded_and_boolean_is_not_an_integer_input(self):
        manager = WorkflowManager()
        for value in (None, True, '5', 2, 16, 3.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                manager.start(value)

    def test_missing_dependencies_do_not_create_a_job(self):
        manager = WorkflowManager()
        manager.ffmpeg = None
        with self.assertRaises(ValueError):
            manager.start(3)
        self.assertEqual(manager.list(), [])


@unittest.skipUnless(FFMPEG and FFPROBE, 'Install FFmpeg/FFprobe for real-media tests')
class RealMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = WorkflowManager(self.temp.name, FFMPEG, FFPROBE)

    def tearDown(self):
        self.manager.close()
        self.temp.cleanup()

    def test_srt_recording_has_real_audio_video_and_duration(self):
        job = self.manager.start(3)
        result = self.manager.wait(job['id'])
        self.assertEqual(result['status'], 'completed', result)
        streams = {s['codec_type']: s for s in result['probe']['streams']}
        self.assertEqual(streams['video']['codec_name'], 'h264')
        self.assertEqual(streams['video']['width'], 640)
        self.assertEqual(streams['audio']['codec_name'], 'aac')
        self.assertGreaterEqual(float(result['probe']['format']['duration']), 2)
        self.assertTrue((Path(self.temp.name)/job['id']/'result.json').exists())

    def test_stop_conflict_and_subsequent_restart(self):
        first = self.manager.start(15)
        with self.assertRaises(Conflict):
            self.manager.start(3)
        self.manager.stop(first['id'])
        self.assertEqual(self.manager.wait(first['id'])['status'], 'stopped')
        self.assertEqual(self.manager.stop(first['id'])['status'], 'stopped')
        second = self.manager.start(3)
        self.assertEqual(self.manager.wait(second['id'])['status'], 'completed')

    def test_startup_failure_is_reported_and_a_new_job_can_recover(self):
        self.manager.ffmpeg = str(Path(self.temp.name)/'missing-ffmpeg')
        first = self.manager.start(3)
        self.assertEqual(self.manager.wait(first['id'])['status'], 'failed')
        self.manager.ffmpeg = FFMPEG
        second = self.manager.start(3)
        self.assertEqual(self.manager.wait(second['id'])['status'], 'completed')


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = WorkflowManager(self.temp.name)
        self.server = LabServer(('127.0.0.1', 0), self.manager)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.manager.close()
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        result = (response.status, response.read(), response.getheader('Content-Type'))
        conn.close()
        return result

    def test_dashboard_and_health_are_available(self):
        code, body, _ = self.request('GET', '/')
        self.assertEqual(code, 200)
        self.assertIn(b'Media Workflow Lab', body)
        code, body, _ = self.request('GET', '/api/health')
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)['status'], 'ok')

    def test_mutations_require_dashboard_token(self):
        code, _, _ = self.request('POST','/api/jobs','{"seconds":3}',{'Content-Type':'application/json'})
        self.assertEqual(code, 403)

    def test_wrong_host_is_rejected(self):
        code, _, _ = self.request('GET','/api/jobs', headers={'Host':'untrusted.invalid'})
        self.assertEqual(code, 403)

    def test_unknown_fields_and_invalid_duration_are_rejected(self):
        headers = {'Content-Type':'application/json','X-Lab-Token':self.server.token}
        for body in ('{"seconds":99}', '{"seconds":3,"input":"/etc/passwd"}', '[]', '{'):
            with self.subTest(body=body):
                self.assertEqual(self.request('POST','/api/jobs',body,headers)[0], 400)
        self.assertEqual(self.manager.list(), [])

    def test_missing_job_and_path_traversal_are_not_served(self):
        for path in ('/api/jobs/missing', '/media/../recording.mp4','/../lab.py','/artifacts'):
            with self.subTest(path=path):
                self.assertEqual(self.request('GET',path)[0], 404)

    @unittest.skipUnless(FFMPEG and FFPROBE, 'Install media tools')
    def test_http_start_status_and_recording(self):
        headers = {'Content-Type':'application/json','X-Lab-Token':self.server.token}
        code, body, _ = self.request('POST','/api/jobs','{"seconds":3}',headers)
        self.assertEqual(code, 202)
        ident = json.loads(body)['id']
        self.assertEqual(self.manager.wait(ident)['status'], 'completed')
        code, body, _ = self.request('GET',f'/api/jobs/{ident}')
        self.assertEqual(json.loads(body)['status'], 'completed')
        code, body, kind = self.request('GET',f'/media/{ident}/recording.mp4')
        self.assertEqual((code, kind), (200,'video/mp4'))
        self.assertGreater(len(body),1000)


if __name__ == '__main__':
    unittest.main()
