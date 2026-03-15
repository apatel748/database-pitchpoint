CREATE DATABASE IF NOT EXISTS sports_predictions;
USE sports_predictions;

CREATE TABLE IF NOT EXISTS games (
    game_id INT PRIMARY KEY,
    competition_code VARCHAR(20),
    competition_name VARCHAR(100),
    home_team VARCHAR(100) NOT NULL,
    away_team VARCHAR(100) NOT NULL,
    match_datetime DATETIME NOT NULL,
    status VARCHAR(30) NOT NULL,
    home_score INT NULL,
    away_score INT NULL,
    winner VARCHAR(10) NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);