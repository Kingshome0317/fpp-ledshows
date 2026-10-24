import sys, tempfile, unittest, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connector import Connector, ENDPOINT, FPP
from library import REQUEST_PROGRAM

class FakeFPP:
    def __init__(self):
        self.commands=[];self.heartbeats=[];self.requests=[];self.playing=True;self.media='Background.mp3';self.fail=False;self.position=1
        self.programs={'Main':{'name':'Main','mainPlaylist':[{'type':'both','enabled':1,'mediaName':'Good.mp3','sequenceName':'Good.fseq'},{'type':'both','enabled':1,'mediaName':'Second.mp3','sequenceName':'Second.fseq'},{'type':'command','enabled':1,'command':'Reboot'}]}}
    def __call__(self,url,payload=None,timeout=3):
        if url==FPP+'/api/media': return ['Good.mp3','Second.mp3','../secret.mp3']
        if url==FPP+'/api/playlists': return list(self.programs)
        if url==FPP+'/api/playlists/playable': return ['Main','Good.fseq','Second.fseq']
        if url.startswith(FPP+'/api/playlist/'):
            import urllib.parse
            name=urllib.parse.unquote(url.rsplit('/',1)[1])
            if payload is not None:self.programs[name]=payload;return payload
            return self.programs[name]
        if url==FPP+'/api/fppd/status':return {'status':1 if self.playing else 0,'current_song':self.media if self.playing else '', 'current_sequence':'Background.fseq' if self.playing else '', 'seconds_played':12,'current_playlist':{'playlist':'Main','index':self.position,'count':2}}
        if url==ENDPOINT:
            self.heartbeats.append(payload)
            if payload.get('ack') and self.requests:self.requests.pop(0)
            return {'success':True,'data':{'request':self.requests[0] if self.requests else None}}
        if url==FPP+'/api/command':
            self.commands.append(payload)
            if self.fail:raise OSError('uncertain response')
            return {'Status':'OK'}
        raise AssertionError(url)

class ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'state.json';self.fpp=FakeFPP()
        self.cfg={'showId':1,'token':'a'*64,'songs':['Good.mp3','Second.mp3'],'acceptRequests':True,'allowIdleRequests':True,'requestMode':'next','publishAudio':False}
        self.c=Connector(self.cfg,self.path,self.fpp);self.c.catalog();self.sid=self.c.songs[0]['id']
    def tearDown(self):self.temp.cleanup()
    def request(self):self.fpp.requests=[{'id':7,'song_id':self.sid}]
    def test_individual_songs_from_multi_song_program(self):
        self.assertEqual(len(self.c.songs),2)
        self.assertEqual(self.c.allowed[self.sid]['sequence'],'Good.fseq')
        self.assertEqual(len(self.fpp.programs[REQUEST_PROGRAM]['mainPlaylist']),2)
    def test_catalog_excludes_unselected_and_path_traversal(self):
        self.cfg['songs']=['../secret.mp3'];self.c.catalog();self.assertEqual(self.c.songs,[])
    def test_operator_must_enable_requests(self):
        self.cfg['acceptRequests']=False;self.request();self.c.tick();self.assertEqual(self.fpp.commands,[])
    def test_next_selects_exactly_one_track(self):
        self.request();self.c.tick();cmd=self.fpp.commands[0];self.assertEqual(cmd['command'],'Insert Playlist After Current');self.assertEqual(cmd['args'][1:3],['1','1'])
    def test_immediate_uses_fpp_insertion(self):
        self.cfg['requestMode']='immediate';self.request();self.c.tick();self.assertEqual(self.fpp.commands[0]['command'],'Insert Playlist Immediate')
    def test_queue_waits_until_final_item(self):
        self.cfg['requestMode']='queue';self.request();self.c.tick();self.assertEqual(self.fpp.commands,[])
        self.fpp.position=2;self.c.tick();self.assertEqual(len(self.fpp.commands),1)
    def test_idle_never_starts_even_with_legacy_setting(self):
        self.fpp.playing=False;self.cfg['allowIdleRequests']=True;self.request();self.c.tick()
        self.assertEqual(self.fpp.commands,[]);self.assertFalse(self.fpp.heartbeats[-1]['accepting'])
        self.assertFalse(self.fpp.heartbeats[-1]['showActive'])
    def test_audio_only_is_not_an_active_lightshow(self):
        base=self.fpp.__call__
        def transport(url,payload=None,timeout=3):
            result=base(url,payload,timeout)
            if url==FPP+'/api/fppd/status':result['current_sequence']=''
            return result
        self.c.transport=transport;self.request();self.c.tick()
        self.assertEqual(self.fpp.commands,[]);self.assertFalse(self.fpp.heartbeats[-1]['accepting'])
    def test_stop_between_heartbeat_and_command_does_not_start_song(self):
        base=self.fpp.__call__;calls=[0]
        def transport(url,payload=None,timeout=3):
            if url==FPP+'/api/fppd/status':
                calls[0]+=1
                if calls[0]>1:return {'status':0,'current_sequence':''}
            return base(url,payload,timeout)
        self.c.transport=transport;self.request();self.c.tick();self.assertEqual(self.fpp.commands,[])
        self.assertEqual(self.c.state['pending']['phase'],'failed')
    def test_stopping_or_paused_does_not_accept(self):
        from connector import show_active
        for status in [0,2,3,4,5]:self.assertFalse(show_active({'status':status,'current_sequence':'Good.fseq'}))
        self.assertTrue(show_active({'status':1,'current_sequence':'Good.fseq'}))
    def test_website_cannot_inject_unlisted_song(self):
        self.fpp.requests=[{'id':7,'song_id':'f'*64}];self.c.tick();self.assertEqual(self.fpp.commands,[])
    def test_pending_is_not_sent_twice(self):
        self.request();self.c.tick();again=Connector(self.cfg,self.path,self.fpp);again.tick();self.assertEqual(len(self.fpp.commands),1)
        self.fpp.media='Good.mp3';again.tick();self.assertEqual(self.fpp.heartbeats[-1]['ack'],{'id':7,'ok':True})
    def test_uncertain_command_is_not_retried(self):
        self.fpp.fail=True;self.request();self.c.tick();self.c.tick();self.assertEqual(len(self.fpp.commands),1)
    def test_changed_pairing_drops_previous_request(self):
        self.request();self.c.tick();again=Connector(dict(self.cfg,showId=2),self.path,self.fpp);self.assertNotIn('pending',again.state)
    def test_expired_state_is_purged(self):
        self.c.state['pending']={'id':7,'time':time.time()-90000};self.c.save();Connector(self.cfg,self.path,self.fpp);self.assertNotIn('pending',json.loads(self.path.read_text()))
    def test_status_never_contains_token(self):
        self.c.tick();raw=(self.path.parent/'status.json').read_text();self.assertNotIn(self.cfg['token'],raw)
