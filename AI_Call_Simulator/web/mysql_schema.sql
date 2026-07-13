-- Base de données pour le simulateur d'appels (simulation.html)
CREATE DATABASE IF NOT EXISTS call_simulator
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE call_simulator;

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
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS conversation_messages (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  conversation_id BIGINT UNSIGNED NOT NULL,
  seq INT UNSIGNED NOT NULL,
  speaker ENUM('agent', 'prospect') NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_messages_conversation
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
    ON DELETE CASCADE,
  INDEX idx_messages_conversation (conversation_id, seq)
) ENGINE=InnoDB;
