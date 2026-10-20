#!/usr/bin/env python3
"""LEDshows FPP connector, outbound HTTPS only, Python standard library."""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import signal
import time
import urllib.parse
import urllib.request

ENDPOINT = 'https://kaart.ledshows.nl/nieuw/?api=fpp-heartbeat'
FPP = 'http://127.0.0.1'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Unexpected HTTP redirect')


HTTP = urllib.request.build_opener(NoRedirect())


def request(url, payload=None, timeout=3):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data, {'User-Agent': 'LEDshows-FPP-Connector/0.2', 'Content-Type': 'application/json'})
    with HTTP.open(req, timeout=timeout) as res:
        raw = res.read(2_000_000)
        try:
            return json.loads(raw)
        except ValueError:
            if url == FPP + '/api/command':
                message = raw.decode('utf-8', 'replace').strip()
                if not message or any(word in message.lower() for word in ['error', 'failed', 'unknown']):
                    raise ValueError('FPP command failed')
                return {'Status': 'OK'}
            raise


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(value, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def load_config(path):
    with open(path) as handle:
        cfg = json.load(handle)
    if cfg.get('endpoint') != ENDPOINT:
        raise ValueError('The endpoint must be the official LEDshows endpoint')
    if not isinstance(cfg.get('showId'), int) or cfg['showId'] < 1:
        raise ValueError('A positive showId is required')
    token = cfg.get('token', '')
    if len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('Configure the private connector key from your show manager')
    names = cfg.get('playlists', [])
    if not isinstance(names, list) or len(names) > 150 or any(not isinstance(n, str) or not n or len(n) > 160 for n in names):
        raise ValueError('playlists must contain at most 150 playlist names')
    return cfg


def song_id(name):
    return hashlib.sha256(name.encode()).hexdigest()


class Connector:
    def __init__(self, config, state_path, transport=request):
        self.config = config
        self.state_path = Path(state_path)
        self.transport = transport
        self.songs = []
        self.allowed = {}
        self.updated_catalog = 0
        self.state = {}
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
        identity = hashlib.sha256((str(config['showId']) + config['token']).encode()).hexdigest()
        if self.state.get('identity') != identity:
            self.state = {'identity': identity}
        self.purge_expired()

    def purge_expired(self):
        pending = self.state.get('pending')
        if pending and time.time() - pending.get('time', 0) > 86400:
            self.state.pop('pending', None)
            self.save()

    def save(self):
        atomic_json(self.state_path, self.state)

    def catalog(self):
        songs, allowed = [], {}
        for name in self.config.get('playlists', []):
            playlist = self.transport(FPP + '/api/playlist/' + urllib.parse.quote(name, safe=''))
            # Requests are intentionally limited to single media/sequence items.
            # Multi-song playlists and command/script items are not visitor selectable.
            lead = (playlist.get('leadIn') or []) + (playlist.get('leadOut') or [])
            items = [i for i in playlist.get('mainPlaylist', []) if i.get('enabled', 1)]
            if lead or len(items) != 1 or items[0].get('type') not in ('both', 'media', 'sequence'):
                logging.warning('One configured playlist is not a single playable song; skipped')
                continue
            item = items[0]
            sid = song_id(name)
            audio = self.config.get('audio', {}).get(name, '')
            if audio and urllib.parse.urlparse(audio).scheme != 'https':
                logging.warning('One audio URL is not HTTPS; skipped')
                audio = ''
            songs.append({'id': sid, 'title': name, 'audioUrl': audio})
            allowed[sid] = {'playlist': name, 'media': item.get('mediaName', ''), 'sequence': item.get('sequenceName', '')}
        self.songs, self.allowed = songs, allowed
        self.updated_catalog = time.monotonic()

    def tick(self):
        self.purge_expired()
        if not self.updated_catalog or time.monotonic() - self.updated_catalog > 60:
            self.catalog()
        status = self.transport(FPP + '/api/fppd/status')
        playing = str(status.get('status', 0)) in ('1', '2', '3')
        current = status.get('current_playlist', {}).get('playlist', '')
        media = status.get('current_song', '') or status.get('media_filename', '')
        sequence = status.get('current_sequence', '')
        title = os.path.splitext(os.path.basename(media or sequence or current))[0]
        active_id = ''
        for sid, song in self.allowed.items():
            if current == song['playlist'] or (media and media == song['media']) or (not media and sequence and sequence == song['sequence']):
                title, active_id = song['playlist'], sid
                break
        pending = self.state.get('pending')
        ack = None
        if pending:
            if pending.get('phase') == 'failed' or time.time() - pending['time'] > 540:
                ack = {'id': pending['id'], 'ok': False}
            elif pending.get('phase') == 'attempting':
                # A process died during the HTTP command. Do not risk replaying it.
                ack = {'id': pending['id'], 'ok': False}
            elif active_id == pending['song_id'] and playing:
                ack = {'id': pending['id'], 'ok': True}
        payload = {'showId': self.config['showId'], 'token': self.config['token'], 'songs': self.songs,
                   'playing': playing, 'accepting': bool(self.config.get('acceptRequests', False)),
                   'title': title if playing else '', 'elapsed': float(status.get('seconds_played', 0) or 0)}
        if ack:
            payload['ack'] = ack
        response = self.transport(ENDPOINT, payload, timeout=12)
        if not response.get('success'):
            raise ValueError('Website rejected the heartbeat')
        atomic_json(self.state_path.parent / 'status.json', {'lastHeartbeat': int(time.time()),
                    'songs': len(self.songs), 'playing': playing, 'accepting': payload['accepting'], 'showId': self.config['showId']})
        if ack:
            self.state.pop('pending', None)
            self.save()
        requested = response['data'].get('request')
        if not requested or not self.config.get('acceptRequests', False):
            return
        rid = int(requested['id'])
        if self.state.get('pending', {}).get('id') == rid:
            return  # Wait until this song starts, then acknowledge. Never overwrite it.
        sid = requested.get('song_id')
        if sid not in self.allowed or not playing or self.state.get('pending'):
            return
        self.state['pending'] = {'id': rid, 'song_id': sid, 'time': time.time(), 'phase': 'attempting'}
        self.save()  # Durable before dispatch: restarting cannot duplicate an uncertain command.
        try:
            result = self.transport(FPP + '/api/command', {'command': 'Insert Playlist After Current',
                'multisyncCommand': False, 'multisyncHosts': '',
                'args': [self.allowed[sid]['playlist'], '-1', '-1', 'false']})
            if isinstance(result, dict) and (str(result.get('Status', '')).lower() == 'error' or 'error' in result):
                raise ValueError('FPP rejected the requested playlist')
            self.state['pending']['phase'] = 'waiting'
            self.save()
        except Exception:
            self.state['pending']['phase'] = 'failed'
            self.save()
            logging.warning('A song could not be queued; it will not be retried automatically')


def main():
    parser = argparse.ArgumentParser(description='LEDshows FPP Connector')
    parser.add_argument('--config', required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    logdir = Path(os.environ.get('LOGDIR', '/home/fpp/media/logs'))
    logging.basicConfig(filename=logdir / 'plugin-fpp-ledshows.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    try:
        cfg = load_config(args.config)
    except Exception:
        logging.error('Configuration invalid or missing; check the private config file')
        return 1
    if not cfg.get('enabled', False) and not args.check:
        return 0
    connector = Connector(cfg, Path(args.config).resolve().parent / 'runtime-state.json')
    if args.check:
        connector.catalog()
        connector.transport(FPP + '/api/fppd/status')
        print('Configuration and FPP API reachable. Selectable songs: ' + str(len(connector.songs)))
        return 0
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    delay = 3
    logging.info('Connector started')
    while not stopping:
        try:
            connector.tick()
            delay = 3
        except Exception:
            # Exception strings can contain request data. Never write them to logs.
            logging.warning('FPP or website temporarily unreachable; reconnecting')
            delay = min(60, delay * 2)
        for _ in range(delay * 5):
            if stopping:
                break
            time.sleep(.2)
    logging.info('Connector stopped')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
