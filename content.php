<?php
// Loaded through FPP's plugin.php wrapper; no independent web entry point.
if (!isset($settings['mediaDirectory'], $pluginName) || $pluginName !== 'fpp-ledshows') { http_response_code(403); return; }
$dataDir = rtrim($settings['mediaDirectory'], '/') . '/plugindata/fpp-ledshows';
$configFile = $dataDir . '/config.json';
$message = ''; $error = '';
function lns_escape($value) { return htmlspecialchars((string)$value, ENT_QUOTES, 'UTF-8'); }
function lns_store($path, $value) {
    $tmp = $path . '.tmp';
    $old = umask(0077);
    $written = file_put_contents($tmp, json_encode($value, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES), LOCK_EX);
    if ($written === false || !chmod($tmp, 0600) || !rename($tmp, $path)) { umask($old); throw new RuntimeException('Opslaan mislukt. Controleer de bestandsrechten.'); }
    umask($old);
}
function lns_local_api($path) {
    $context = stream_context_create(['http' => ['timeout' => 3, 'follow_location' => 0]]);
    $raw = @file_get_contents('http://127.0.0.1/api/' . $path, false, $context);
    return $raw === false ? null : json_decode($raw, true);
}
if (!is_dir($dataDir)) { echo '<p>Voer eerst het installatiescript van de plugin uit.</p>'; return; }
$cfg = is_file($configFile) ? json_decode(file_get_contents($configFile), true) : [];
if (!is_array($cfg)) $cfg = [];
$nonceFile = $dataDir . '/csrf';
if (!is_file($nonceFile)) {
    $old = umask(0077); $handle = @fopen($nonceFile, 'x');
    if ($handle) { fwrite($handle, bin2hex(random_bytes(32))); fclose($handle); }
    umask($old);
}
$nonce = is_file($nonceFile) ? trim(file_get_contents($nonceFile)) : '';
$playlists = lns_local_api('playlists');
if (!is_array($playlists)) $playlists = [];
$playlists = array_values(array_filter($playlists, 'is_string'));
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        if (strlen($nonce) !== 64 || !hash_equals($nonce, (string)($_POST['csrf'] ?? ''))) throw new RuntimeException('Ververs deze pagina en probeer opnieuw.');
        $action = $_POST['action'] ?? '';
        if ($action === 'save') {
            $id = filter_var($_POST['showId'] ?? '', FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
            if (!$id) throw new RuntimeException('Vul een geldig show-ID in.');
            $token = trim((string)($_POST['ConnectorToken'] ?? ''));
            if ($token === '') $token = $cfg['token'] ?? '';
            if (!preg_match('/^[a-f0-9]{64}$/D', $token)) throw new RuntimeException('Vul de koppelsleutel uit je showbeheer in.');
            $selected = $_POST['playlists'] ?? [];
            if (!is_array($selected) || count($selected) > 150 || array_diff($selected, $playlists)) throw new RuntimeException('Kies bestaande playlists uit de lijst.');
            $audio = [];
            foreach ($selected as $name) {
                $url = trim((string)(($_POST['audio'] ?? [])[hash('sha256', $name)] ?? ''));
                if ($url !== '' && (strlen($url) > 2000 || !filter_var($url, FILTER_VALIDATE_URL) || parse_url($url, PHP_URL_SCHEME) !== 'https')) throw new RuntimeException('Audio-URLs moeten geldige HTTPS-links zijn.');
                if ($url !== '') $audio[$name] = $url;
            }
            $cfg = ['enabled' => isset($_POST['enabled']), 'endpoint' => 'https://kaart.ledshows.nl/nieuw/?api=fpp-heartbeat', 'showId' => (int)$id,
                    'token' => $token, 'playlists' => array_values($selected), 'audio' => (object)$audio, 'acceptRequests' => isset($_POST['acceptRequests'])];
            lns_store($configFile, $cfg);
            $scripts = __DIR__ . '/scripts/';
            exec('bash ' . escapeshellarg($scripts . 'preStop.sh') . ' 2>/dev/null', $output, $result);
            if ($result !== 0) throw new RuntimeException('Instellingen opgeslagen, maar stoppen van de connector is mislukt.');
            if ($cfg['enabled']) {
                exec('bash ' . escapeshellarg($scripts . 'postStart.sh') . ' 2>/dev/null', $output, $result);
                if ($result !== 0) throw new RuntimeException('Instellingen opgeslagen, maar starten van de connector is mislukt.');
            }
            $message = 'Instellingen opgeslagen. ' . ($cfg['enabled'] ? 'De connector maakt verbinding.' : 'De connector staat uit.');
        } else { throw new RuntimeException('Onbekende actie.'); }
    } catch (Throwable $exception) { $error = $exception->getMessage(); }
}
$status = is_file($dataDir . '/status.json') ? json_decode(file_get_contents($dataDir . '/status.json'), true) : [];
$online = !empty($cfg['enabled']) && (int)($status['showId'] ?? 0) === (int)($cfg['showId'] ?? 0) && (int)($status['lastHeartbeat'] ?? 0) > time() - 30;
$audioCfg = (array)($cfg['audio'] ?? []);
?>
<div class="row"><div class="col-lg-9">
<p>Koppel deze FPP aan je lichtshow op LEDshows.nl. Alleen de gekozen playlistnamen en afspeelstatus gaan naar de website. Er is geen poort-forwarding nodig.</p>
<p><strong>Status:</strong> <?= $online ? 'Verbonden met LEDshows.nl' : (!empty($cfg['enabled']) ? 'Wacht op verbinding' : 'Uitgeschakeld') ?> · <?= (int)($status['songs'] ?? 0) ?> selecteerbare nummers. <a href="plugin.php?plugin=fpp-ledshows&amp;page=content.php">Ververs status</a></p>
<?php if ($message): ?><div class="alert alert-success"><?= lns_escape($message) ?></div><?php endif ?>
<?php if ($error): ?><div class="alert alert-danger"><?= lns_escape($error) ?></div><?php endif ?>
<form method="post" action="plugin.php?plugin=fpp-ledshows&amp;page=content.php" autocomplete="off">
<input type="hidden" name="csrf" value="<?= lns_escape($nonce) ?>"><input type="hidden" name="action" value="save">
<div class="mb-3"><label for="showId" class="form-label">Show-ID op LEDshows.nl</label><input class="form-control" id="showId" name="showId" type="number" min="1" required value="<?= (int)($cfg['showId'] ?? 0) ?: '' ?>"></div>
<div class="mb-3"><label for="ConnectorToken" class="form-label">Koppelsleutel</label><input class="form-control" id="ConnectorToken" name="ConnectorToken" type="password" autocomplete="new-password" placeholder="<?= !empty($cfg['token']) && strlen($cfg['token']) === 64 ? 'Opgeslagen; leeg laten om te behouden' : 'Plak de sleutel uit je showbeheer' ?>"><div class="form-text">Maak de sleutel bij jouw show via Beheer → FPP koppelen. De opgeslagen sleutel wordt hier nooit getoond.</div></div>
<div class="form-check mb-3"><input class="form-check-input" type="checkbox" name="enabled" id="enabled" <?= !empty($cfg['enabled']) ? 'checked' : '' ?>><label class="form-check-label" for="enabled">Connector inschakelen en status delen met LEDshows.nl</label></div>
<h2>Beschikbare nummers</h2><p>Maak in FPP per nummer een playlist met één media-, sequence- of gecombineerd item, zonder lead-in/out of opdrachten. Alleen geschikte playlists worden aangeboden.</p>
<?php if (!$playlists): ?><div class="alert alert-info">Er zijn nog geen playlists. Maak ze eerst via Content Setup → Playlists en ververs deze pagina.</div><?php endif ?>
<?php foreach ($playlists as $name): $key = hash('sha256', $name); ?>
<div class="border rounded p-3 mb-2"><div class="form-check"><input class="form-check-input" type="checkbox" name="playlists[]" id="song-<?= $key ?>" value="<?= lns_escape($name) ?>" <?= in_array($name, $cfg['playlists'] ?? [], true) ? 'checked' : '' ?>><label class="form-check-label" for="song-<?= $key ?>"><?= lns_escape($name) ?></label></div><label class="form-label mt-2" for="audio-<?= $key ?>">Optionele openbare HTTPS-audiolink</label><input class="form-control" type="url" id="audio-<?= $key ?>" name="audio[<?= $key ?>]" value="<?= lns_escape($audioCfg[$name] ?? '') ?>"></div>
<?php endforeach ?>
<div class="form-check my-3"><input class="form-check-input" type="checkbox" name="acceptRequests" id="acceptRequests" <?= !empty($cfg['acceptRequests']) ? 'checked' : '' ?>><label class="form-check-label" for="acceptRequests">Bezoekers mogen gekozen nummers aanvragen</label></div>
<p class="text-muted">Een aanvraag volgt na het huidige nummer. De gewone playlist gaat daarna verder. De connector start geen stilstaande show. Meeluisteren via een openbare audiolink is bij benadering gesynchroniseerd; dit is geen realtime audiostream.</p>
<button class="btn btn-primary" type="submit">Opslaan en toepassen</button>
</form><p class="mt-3"><a href="https://github.com/Kingshome0317/fpp-ledshows" target="_blank" rel="noopener noreferrer">Handleiding en broncode</a> · Logboek: plugin-fpp-ledshows.log</p>
</div></div>
