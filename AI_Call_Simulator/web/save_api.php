<?php
/**
 * API MySQL pour simulateur d'appels — hébergement mutualisé (cPanel).
 * Upload : public_html/conv-api/index.php (ou /api/simulator/index.php)
 *
 * Variables à adapter ci-dessous selon votre cPanel.
 */
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// --- Configuration MySQL (localhost = même serveur que le site) ---
$DB_HOST = getenv('MYSQL_HOST') ?: 'localhost';
$DB_PORT = getenv('MYSQL_PORT') ?: '3306';
$DB_USER = getenv('MYSQL_USER') ?: 'zetvyznnvz_simulator';
$DB_PASS = getenv('MYSQL_PASSWORD') ?: 'CHANGE_ME';
$DB_NAME = getenv('MYSQL_DATABASE') ?: 'zetvyznnvz_simulator';

function json_response(int $code, array $payload): void {
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE);
    exit;
}

function db(): PDO {
    global $DB_HOST, $DB_PORT, $DB_USER, $DB_PASS, $DB_NAME;
    static $pdo = null;
    if ($pdo !== null) {
        return $pdo;
    }
    $dsn = "mysql:host={$DB_HOST};port={$DB_PORT};dbname={$DB_NAME};charset=utf8mb4";
    $pdo = new PDO($dsn, $DB_USER, $DB_PASS, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
    return $pdo;
}

function ensure_schema(PDO $pdo): void {
    $pdo->exec("
        CREATE TABLE IF NOT EXISTS conversations (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          profile_key VARCHAR(64) NOT NULL,
          level_key VARCHAR(32) NOT NULL,
          model VARCHAR(128) NULL,
          prospect_first_name VARCHAR(64) NULL,
          prospect_last_name VARCHAR(64) NULL,
          started_at DATETIME NULL,
          ended_at DATETIME NULL,
          score_total INT NULL,
          score_level VARCHAR(64) NULL,
          evaluation_json JSON NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_conversations_created (created_at),
          INDEX idx_conversations_profile (profile_key, level_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    ");
    $pdo->exec("
        CREATE TABLE IF NOT EXISTS conversation_messages (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          conversation_id BIGINT UNSIGNED NOT NULL,
          seq INT UNSIGNED NOT NULL,
          speaker ENUM('agent', 'prospect') NOT NULL,
          content TEXT NOT NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_messages_conversation (conversation_id, seq)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    ");
}

function parse_dt(?string $value): ?string {
    if (!$value) return null;
    $value = str_replace('Z', '+00:00', trim($value));
    $ts = strtotime($value);
    return $ts ? date('Y-m-d H:i:s', $ts) : null;
}

$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$uri = rtrim($uri, '/');

// Support /conv-api/health, /conv-api/api/conversations, /health, /api/conversations
$is_health = (bool) preg_match('#/(health|conv-api/health)$#', $uri);
$is_save = (bool) preg_match('#/api/conversations$#', $uri);

if ($_SERVER['REQUEST_METHOD'] === 'GET' && $is_health) {
    try {
        $pdo = db();
        json_response(200, ['ok' => true, 'database' => $DB_NAME]);
    } catch (Throwable $e) {
        json_response(503, ['ok' => false, 'error' => $e->getMessage()]);
    }
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && $is_save) {
    $raw = file_get_contents('php://input') ?: '{}';
    $payload = json_decode($raw, true);
    if (!is_array($payload)) {
        json_response(400, ['ok' => false, 'error' => 'JSON invalide']);
    }

    try {
        $pdo = db();
        ensure_schema($pdo);

        $profile = trim($payload['profile'] ?? '') ?: 'unknown';
        $level = trim($payload['level'] ?? '') ?: 'unknown';
        $model = trim($payload['model'] ?? '') ?: null;
        $persona = $payload['persona'] ?? [];
        $evaluation = $payload['evaluation'] ?? [];
        $messages = $payload['messages'] ?? [];

        $stmt = $pdo->prepare("
            INSERT INTO conversations (
              profile_key, level_key, model,
              prospect_first_name, prospect_last_name,
              started_at, ended_at,
              score_total, score_level, evaluation_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ");
        $stmt->execute([
            $profile,
            $level,
            $model,
            $persona['firstName'] ?? $persona['first_name'] ?? null,
            $persona['lastName'] ?? $persona['last_name'] ?? null,
            parse_dt($payload['started_at'] ?? null),
            parse_dt($payload['ended_at'] ?? null),
            $evaluation['score_total'] ?? null,
            $evaluation['niveau'] ?? null,
            $evaluation ? json_encode($evaluation, JSON_UNESCAPED_UNICODE) : null,
        ]);
        $conversationId = (int) $pdo->lastInsertId();

        $msgStmt = $pdo->prepare("
            INSERT INTO conversation_messages (conversation_id, seq, speaker, content)
            VALUES (?, ?, ?, ?)
        ");
        foreach ($messages as $idx => $msg) {
            $role = strtolower($msg['role'] ?? '');
            $speaker = in_array($role, ['user', 'agent'], true) ? 'agent' : 'prospect';
            $content = trim($msg['content'] ?? '');
            if ($content === '') continue;
            $msgStmt->execute([$conversationId, $idx, $speaker, $content]);
        }

        json_response(201, ['ok' => true, 'conversation_id' => $conversationId]);
    } catch (Throwable $e) {
        json_response(500, ['ok' => false, 'error' => $e->getMessage()]);
    }
}

json_response(404, ['ok' => false, 'error' => 'Not found']);
