# LEDshows Connector for FPP

Connect your FPP 10 show to [LEDshows.nl](https://kaart.ledshows.nl/nieuw/). Version 0.3.

## Install or update

Set FPP Settings → UI Level to Developer, then open Content Setup → Plugin Manager. Paste:

`https://raw.githubusercontent.com/Kingshome0317/fpp-ledshows/main/pluginInfo.json`

Install LEDshows Connector, or use Update on the installed card. This plugin is not yet in FPP's official catalog. Open Content Setup → LEDshows Connector.

## Configure

Enter your LEDshows show ID and pairing key (website: Beheer → FPP koppelen). Select individual music files from FPP; no per-song program needs to be created by hand. Existing FPP sequence/media pairings are reused. Select up to 100 songs.

Choose how requests play:

- Next: after the current item, then the normal show resumes.
- Queue: wait until the last item of the current program before inserting the request.
- Immediate: interrupt the current item, then resume through FPP's insertion behavior.

An independent setting allows a request to start music when FPP is idle. Requests are serialized; uncertain commands are not blindly retried. The connector maintains reserved programs named LEDshows Connector Requests and LEDshows Connector Single Request. It does not edit your existing programs.

## Listening

Enable audio publication to offer the selected tracks on your public show page. The connector uses FPP’s installed FFmpeg to extract and normalize only the audio of selected media into AAC/M4A, then publishes it to kaart.ledshows.nl (maximum 50 MB per converted track). Large MP4 videos stay on the Pi; only their audio is uploaded. Visitors tap Luister mee to join the currently active track; timing follows FPP automatically, with small drift corrections.

This is synchronized playback of the same source audio, not microphone recognition or a capture of speakers, live announcements or hardware mixer output. Browser, speaker and network delays limit precision. No microphone permission is requested.

Audio is stored outside the public web root and served through the show API only while that song is selected and listening remains enabled. Old cached files are removed during uploads after seven days; inactive copies may remain in private server storage until maintenance. The plugin has no listening port and needs no port forwarding.

## Operation and privacy

Private settings and transient request state: `<mediadir>/plugindata/fpp-ledshows/`, directory 0700, files 0600. Pairing keys are never displayed or logged. Log: FPP's log directory, `plugin-fpp-ledshows.log`. FPP lifecycle hooks run one connector as user fpp. Audio transfers happen in a background worker so they do not stop status updates. No extra Python packages. Audio conversion uses the FFmpeg executable included with FPP, one background conversion at a time.

Before uninstalling, disable the connector in its page and revoke the key on the website. Uninstall stops its process and removes private configuration; source songs and your own programs stay.

## Tests

`python3 -m unittest discover -s tests -v`

Report issues without keys or private configuration.
