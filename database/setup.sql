-- SpamGuard AI: manual MySQL setup script (phpMyAdmin > SQL tab, or `mysql -u root < database/setup.sql`).
-- Alternative: create only the database and run `flask db upgrade` / `flask init-db`.

CREATE DATABASE IF NOT EXISTS spam_detection_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE spam_detection_db;

CREATE TABLE IF NOT EXISTS users (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(100) NOT NULL,
  email         VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role          VARCHAR(20)  NOT NULL DEFAULT 'user',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS messages (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  user_id          INT NULL,
  message_text     TEXT        NOT NULL,
  prediction       VARCHAR(10) NOT NULL,
  confidence_score FLOAT       NOT NULL,
  created_at       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_messages_user_created (user_id, created_at),
  KEY ix_messages_prediction (prediction),
  KEY ix_messages_created_at (created_at),
  CONSTRAINT fk_messages_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS model_logs (
  id         INT AUTO_INCREMENT PRIMARY KEY,
  model_name VARCHAR(100) NOT NULL,
  accuracy   DOUBLE NOT NULL,
  `precision` DOUBLE NOT NULL,
  recall     DOUBLE NOT NULL,
  f1_score   DOUBLE NOT NULL,
  trained_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS feedback (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  message_id    INT NOT NULL,
  user_feedback VARCHAR(20) NOT NULL,
  comments      TEXT NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_feedback_message_id (message_id),
  CONSTRAINT fk_feedback_message FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
