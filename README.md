# LEDshows Connector for FPP

Connect a Falcon Player show to [LEDshows.nl](https://kaart.ledshows.nl/nieuw/).
Visitors see the current song and can request songs from the operator's selected
catalog. The connector makes outbound HTTPS requests; no port forwarding is needed.

**Development preview, 0.2.** Targets FPP 10. API command compatibility was checked
on FPP 10.2 / Raspberry Pi 5; a complete hardware playback test is still pending.
This repository is not yet included in FPP's official plugin catalog.

## Install through FPP 10's Plugin Manager

1. Set FPP's UI level to **Developer** in FPP Settings. Custom plugin URL entry
   is hidden at other UI levels in FPP 10.2.
2. Open **Content Setup → Plugin Manager**.
3. Paste this URL into the plugin search box:

   `https://raw.githubusercontent.com/Kingshome0317/fpp-ledshows/main/pluginInfo.json`

4. Open **LEDshows Connector**, read its disclosure and install it.
5. Open **Content Setup → LEDshows Connector** to configure it.

FPP installs the Git repository and offers updates through its Plugin Manager.
A standalone ZIP upload is not this install method. To appear in the normal
plugin list, this plugin must first be submitted to and accepted by FPP's maintainers.

## Configure

1. Log in to LEDshows.nl and open your show's management page, then **FPP koppelen**.
2. Generate a private pairing key. In the FPP plugin page, enter your show ID and
   paste the key into the password field. Never publish the key or commit it.
3. Create one FPP playlist per requestable song. Each must contain exactly one
   enabled media, sequence, or combined item, with no lead-in/out, script or command.
4. Select those playlists in the connector page.
5. Enable the connector; optionally allow visitor requests. Save.
6. Refresh the connector page after a few seconds and check the connection status.

Start your normal background playlist in FPP. A request is inserted after the
current item; the original playlist resumes afterwards. The connector never starts
an idle show. It offers only one pending request to FPP at a time and does not
blindly retry an uncertain playback command. Website requests expire after ten minutes.

## Optional listening

Each selected song may have a public HTTPS audio URL supplied by the operator.
The website's browser player approximately follows FPP's reported position.
This is not realtime audio transport or sample-accurate synchronization like PulseMesh.
No audio file is uploaded from the Pi. Make publicly accessible audio available
only when you are entitled to do so.

## Manual fallback

If the Plugin Manager cannot be used, run these commands in FPP's SSH shell:

```sh
. /opt/fpp/scripts/common
git clone --branch main https://github.com/Kingshome0317/fpp-ledshows.git "$MEDIADIR/plugins/fpp-ledshows"
bash "$MEDIADIR/plugins/fpp-ledshows/scripts/fpp_install.sh"
```

This refuses to clone over an existing directory. Configuration then takes place
on the same FPP plugin page. Do not extract a ZIP over an existing installation.

## Storage, operation and removal

Private configuration, pairing key, transient request ID, heartbeat status and lock:
`<mediadir>/plugindata/fpp-ledshows/` (directory 0700; files 0600).
FPP's `config/` backup does not contain this pairing key. Re-pair after reinstalling
on another SD card. An older 0.1 configuration is migrated during installation.

Log: FPP's normal log directory, `plugin-fpp-ledshows.log`; secrets are never logged.
Only Python's standard library and FPP's installed `flock` utility are used.
Startup/shutdown hooks manage a single connector process as the `fpp` user. There
are no extra system services, listeners or arbitrary remote commands. FPP's show,
network and output configuration are untouched.

Disable the connector in its page before removal, then uninstall in Plugin Manager.
The uninstall hook stops it and deletes its private configuration and transient
state. Revoke the pairing key from the website too. Shows, sequences and media stay.

## Development checks

```sh
python3 -m unittest discover -s tests -v
```

Please report problems using GitHub Issues without tokens or private configuration.
