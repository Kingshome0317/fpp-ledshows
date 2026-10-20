import sys
import tempfile
import time
import json
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connector import Connector, ENDPOINT, FPP, song_id


class FakeFPP:
    def __init__(self):
        self.commands = []
        self.heartbeats = []
        self.requests = []
        self.playlist = 'Background'
        self.playing = True
        self.fail_command = False

    def __call__(self, url, payload=None, timeout=3):
        if url == FPP + '/api/fppd/status':
            return {'status': 1 if self.playing else 0, 'seconds_played': 12,
                    'current_playlist': {'playlist': self.playlist}, 'current_song': ''}
        if url.startswith(FPP + '/api/playlist/'):
            if url.endswith('Bad'):
                return {'mainPlaylist': [{'type': 'command', 'enabled': 1}]}
            return {'name': 'Good', 'mainPlaylist': [{'type': 'both', 'mediaName': 'Good.mp3', 'sequenceName': 'Good.fseq'}]}
        if url == ENDPOINT:
            self.heartbeats.append(payload)
            if payload.get('ack') and self.requests:
                self.requests.pop(0)
            return {'success': True, 'data': {'request': self.requests[0] if self.requests else None}}
        if url == FPP + '/api/command':
            self.commands.append(payload)
            if self.fail_command:
                raise OSError('simulated network failure')
            return {'Status': 'OK'}
        raise AssertionError('Unexpected endpoint')


class ConnectorTests(unittest.TestCase):
    def test_changed_pairing_drops_previous_request(self):
        self.connector.state['pending'] = {'id': 99, 'time': time.time()}
        self.connector.save()
        new_cfg = dict(self.cfg, showId=2)
        reloaded = Connector(new_cfg, self.path, self.fpp)
        self.assertNotIn('pending', reloaded.state)

    def test_expired_request_state_is_purged_without_network(self):
        self.connector.state['pending'] = {'id': 99, 'time': time.time() - 90000}
        self.connector.save()
        reloaded = Connector(self.cfg, self.path, self.fpp)
        self.assertNotIn('pending', reloaded.state)
        self.assertNotIn('pending', json.loads(self.path.read_text()))

    def test_local_status_contains_no_pairing_token(self):
        self.connector.tick()
        raw = (self.path.parent / 'status.json').read_text()
        self.assertNotIn(self.cfg['token'], raw)
        self.assertEqual(json.loads(raw)['showId'], 1)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'state.json'
        self.fpp = FakeFPP()
        self.cfg = {'showId': 1, 'token': 'a' * 64, 'playlists': ['Good', 'Bad'],
                    'audio': {'Good': 'https://example.invalid/own-recording.mp3'}, 'acceptRequests': True}
        self.connector = Connector(self.cfg, self.path, self.fpp)

    def tearDown(self):
        self.temp.cleanup()

    def enqueue(self, rid=1, name='Good'):
        self.fpp.requests.append({'id': rid, 'song_id': song_id(name)})

    def test_only_single_media_playlists_are_exposed(self):
        self.connector.tick()
        self.assertEqual(['Good'], [s['title'] for s in self.fpp.heartbeats[-1]['songs']])
        self.assertNotIn('current_playlist', self.fpp.heartbeats[-1])

    def test_queue_waits_for_requested_song_to_start(self):
        self.enqueue()
        self.connector.tick()
        self.connector.tick()
        self.assertEqual(1, len(self.fpp.commands))
        self.assertEqual('Insert Playlist After Current', self.fpp.commands[0]['command'])
        self.assertNotIn('ack', self.fpp.heartbeats[-1])
        self.fpp.playlist = 'Good'
        self.connector.tick()
        self.assertTrue(self.fpp.heartbeats[-1]['ack']['ok'])
        self.assertNotIn('pending', self.connector.state)

    def test_restart_does_not_duplicate_queued_song(self):
        self.enqueue()
        self.connector.tick()
        restarted = Connector(self.cfg, self.path, self.fpp)
        restarted.tick()
        self.assertEqual(1, len(self.fpp.commands))

    def test_uncertain_command_is_not_retried(self):
        self.enqueue()
        self.fpp.fail_command = True
        self.connector.tick()
        self.connector.tick()
        self.assertEqual(1, len(self.fpp.commands))
        self.assertFalse(self.fpp.heartbeats[-1]['ack']['ok'])

    def test_website_cannot_inject_unlisted_playlist(self):
        self.enqueue(name='Unlisted command')
        self.connector.tick()
        self.assertFalse(self.fpp.commands)

    def test_idle_show_is_never_started(self):
        self.enqueue()
        self.fpp.playing = False
        self.connector.tick()
        self.assertFalse(self.fpp.commands)

    def test_operator_must_enable_requests(self):
        self.cfg['acceptRequests'] = False
        self.enqueue()
        self.connector.tick()
        self.assertFalse(self.fpp.commands)


if __name__ == '__main__':
    unittest.main()
