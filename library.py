"""Discover individual FPP media and reuse safe sequence/media pairings."""
import hashlib
import os
import urllib.parse

REQUEST_PROGRAM = 'LEDshows Connector Requests'
MEDIA_EXTENSIONS = {'.mp3', '.m4a', '.aac', '.wav', '.ogg', '.flac', '.mp4'}


def discover(transport, base):
    media = transport(base + '/api/media')
    media = sorted({n for n in media if isinstance(n, str) and os.path.basename(n) == n
                    and os.path.splitext(n)[1].lower() in MEDIA_EXTENSIONS})
    paired = {}
    programs = transport(base + '/api/playlists')
    for name in programs:
        if name == REQUEST_PROGRAM:
            continue
        program = transport(base + '/api/playlist/' + urllib.parse.quote(name, safe=''))
        for item in program.get('mainPlaylist', []):
            filename = item.get('mediaName')
            sequence = item.get('sequenceName', '')
            if filename in media and item.get('type') in ('media', 'both') and item.get('enabled', 1):
                paired.setdefault(filename, sequence if isinstance(sequence, str) and os.path.basename(sequence) == sequence else '')
    playable = transport(base + '/api/playlists/playable')
    return [{'filename': n, 'title': os.path.splitext(n)[0],
             'id': hashlib.sha256(('media:' + n).encode()).hexdigest(),
             'sequence': paired.get(n, os.path.splitext(n)[0] + '.fseq' if os.path.splitext(n)[0] + '.fseq' in playable else '')}
            for n in media], programs
