-- database/init_db.sql
-- SQL-скрипт для создания базы данных CatCorp и основных таблиц

CREATE DATABASE IF NOT EXISTS catcorp
CHARACTER SET utf8mb4
COLLATE utf8mb4_general_ci;

USE catcorp;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'user') DEFAULT 'user',
    created_at DATETIME DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT NOT NULL,
    receiver_id INT NOT NULL,
    content TEXT NOT NULL,
    sent_at DATETIME DEFAULT NOW(),

    FOREIGN KEY (sender_id) REFERENCES users(id)
        ON DELETE CASCADE,

    FOREIGN KEY (receiver_id) REFERENCES users(id)
        ON DELETE CASCADE
);