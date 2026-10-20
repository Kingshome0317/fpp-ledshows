import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from audio_publisher import AudioPublisher


class Uploads:
    def __init__(self):
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, request.data.read()))
        return io.BytesIO(b'{"success":true}')


class AudioPublisherTests(unittest.TestCase):
    def test_large_video_uploads_audio_only(self):
        with tempfile.TemporaryDirectory() as root:
            media = Path(root)
            data = media / 'plugindata' / 'fpp-ledshows'
            data.mkdir(parents=True)
            (media / 'videos').mkdir()
            video = media / 'videos' / "Disney's Frozen.mp4"
            video.write_bytes(b'video')
            uploads = Uploads()
            publisher = AudioPublisher({'showId': 12, 'token': 'test'}, data, uploads)
            publisher.items = [{'id': 'abc', 'filename': video.name}]
            def convert(args, **kwargs):
                self.assertEqual(args[args.index('-i')+1], str(video))
                self.assertEqual(args[args.index('-map')+1], '0:a:0')
                self.assertIn('-vn', args)
                self.assertEqual(kwargs['timeout'], 180)
                Path(args[-1]).write_bytes(b'converted AAC')
            with patch('audio_publisher.shutil.which', return_value='/usr/bin/ffmpeg'), patch('audio_publisher.subprocess.run', side_effect=convert):
                publisher.run()
            self.assertIn('abc', publisher.done)
            self.assertEqual(uploads.requests[0][1], b'converted AAC')
            self.assertFalse(list(data.glob('audio-transfer.*')))

    def test_failed_conversion_never_uploads(self):
        with tempfile.TemporaryDirectory() as root:
            uploads = Uploads()
            publisher = AudioPublisher({'showId': 12, 'token': 'test'}, root, uploads)
            publisher.items = [{'id': 'abc', 'filename': 'song.mp3'}]
            with patch('audio_publisher.shutil.which', return_value='/usr/bin/ffmpeg'), patch('audio_publisher.subprocess.run', side_effect=RuntimeError('conversion failed')):
                publisher.run()
            self.assertTrue(publisher.error)
            self.assertEqual(uploads.requests, [])
            self.assertEqual(publisher.done, {})
            self.assertFalse(list(Path(root).glob('audio-transfer.*')))

    def test_invalid_filename_never_runs_conversion(self):
        with tempfile.TemporaryDirectory() as root:
            publisher = AudioPublisher({'showId': 12, 'token': 'test'}, root, Uploads())
            publisher.items = [{'id': 'abc', 'filename': '../private.mp3'}]
            with patch('audio_publisher.subprocess.run') as convert:
                publisher.run()
            convert.assert_not_called()
            self.assertTrue(publisher.error)
