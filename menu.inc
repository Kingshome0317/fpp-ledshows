<?php
if ($menu === 'content') {
    printf('<li><a href="plugin.php?plugin=%s&amp;page=content.php">LEDshows Connector</a></li>', htmlspecialchars($plugin, ENT_QUOTES, 'UTF-8'));
}
