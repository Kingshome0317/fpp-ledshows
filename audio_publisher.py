"""Publish explicitly selected source audio; playback timing stays with FPP."""
import json
import os
from pathlib import Path
import threading
import time
import urllib.parse
import urllib.request


class AudioPublisher:
    def __init__(self, config, directory, opener):
        self.config, self.directory, self.opener = config, Path(directory), opener
        self.items = []
        self.done = {}
        self.attempted = {}
        self.running = False
        self.error = False

    def offer(self, items):
        if not self.config.get('publishAudio', False):
            return
        self.items = list(items)
        if not self.running:
            self.running = True
            threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        try:
            for song in self.items:
                if time.time() - self.done.get(song['id'], 0) < 3600:
                    continue
                if time.time() - self.attempted.get(song['id'], 0) < 15:
                    continue
                self.attempted[song['id']] = time.time()
                temp = self.directory / 'audio-transfer.tmp'
                try:
                    directory = 'Videos' if song['filename'].lower().endswith('.mp4') else 'Music'
                    source = 'http://127.0.0.1/api/file/' + directory + '/' + urllib.parse.quote(song['filename'], safe='')
                    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    size = 0
                    with os.fdopen(fd, 'wb') as output, self.opener.open(source, timeout=20) as response:
                        while True:
                            block = response.read(65536)
                            if not block:
                                break
                            size += len(block)
                            if size > 50 * 1024 * 1024:
                                raise ValueError('Audio exceeds upload limit')
                            output.write(block)
                    url = 'https://kaart.ledshows.nl/nieuw/?api=fpp-audio-upload&id=' + str(self.config['showId']) + '&song=' + song['id']
                    with temp.open('rb') as payload:
                        req = urllib.request.Request(url, data=payload, method='POST', headers={
                            'X-Ledshows-Token': self.config['token'], 'Content-Type': 'application/octet-stream',
                            'Content-Length': str(size), 'User-Agent': 'LEDshows-FPP-Connector/0.3'})
                        with self.opener.open(req, timeout=60) as result:
                            if not json.load(result).get('success'):
                                raise ValueError('Audio upload rejected')
                    self.done[song['id']] = time.time()
                    self.error = False
                except Exception:
                    self.error = True
                finally:
                    temp.unlink(missing_ok=True)
        finally:
            self.running = False
