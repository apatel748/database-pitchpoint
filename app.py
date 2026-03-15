import os
from datetime import datetime, timedelta, timezone

import mysql.connector
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, flash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

API_TOKEN = os.getenv("FOOTBALL_API_TOKEN")

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "sports_predictions"),
}


def get_db_connection():
    return mysql.connector.connect(**MYSQL_CONFIG)


def ensure_games_table_exists():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
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
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()


def fetch_matches_from_api():
    if not API_TOKEN:
        raise ValueError("FOOTBALL_API_TOKEN is missing from .env")

    today = datetime.now(timezone.utc).date()
    date_from = today - timedelta(days=2)
    date_to = today + timedelta(days=7)

    url = "https://api.football-data.org/v4/matches"
    headers = {"X-Auth-Token": API_TOKEN}
    params = {
        "dateFrom": date_from.isoformat(),
        "dateTo": date_to.isoformat()
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    return data.get("matches", [])


def get_winner(score_data):
    winner = score_data.get("winner")
    if winner == "HOME_TEAM":
        return "HOME"
    if winner == "AWAY_TEAM":
        return "AWAY"
    if winner == "DRAW":
        return "DRAW"
    return None


def save_matches(matches):
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        INSERT INTO games (
            game_id,
            competition_code,
            competition_name,
            home_team,
            away_team,
            match_datetime,
            status,
            home_score,
            away_score,
            winner
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            competition_code = VALUES(competition_code),
            competition_name = VALUES(competition_name),
            home_team = VALUES(home_team),
            away_team = VALUES(away_team),
            match_datetime = VALUES(match_datetime),
            status = VALUES(status),
            home_score = VALUES(home_score),
            away_score = VALUES(away_score),
            winner = VALUES(winner)
    """

    for match in matches:
        game_id = match["id"]
        competition_code = match.get("competition", {}).get("code")
        competition_name = match.get("competition", {}).get("name")
        home_team = match.get("homeTeam", {}).get("name")
        away_team = match.get("awayTeam", {}).get("name")
        status = match.get("status")

        utc_date = match.get("utcDate")
        if utc_date:
            match_datetime = datetime.fromisoformat(
                utc_date.replace("Z", "+00:00")
            ).strftime("%Y-%m-%d %H:%M:%S")
        else:
            match_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        full_time = match.get("score", {}).get("fullTime", {})
        home_score = full_time.get("home")
        away_score = full_time.get("away")
        winner = get_winner(match.get("score", {}))

        values = (
            game_id,
            competition_code,
            competition_name,
            home_team,
            away_team,
            match_datetime,
            status,
            home_score,
            away_score,
            winner
        )

        cursor.execute(sql, values)

    conn.commit()
    cursor.close()
    conn.close()


def get_all_games():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            game_id,
            competition_code,
            competition_name,
            home_team,
            away_team,
            match_datetime,
            status,
            home_score,
            away_score,
            winner,
            last_updated
        FROM games
        ORDER BY match_datetime ASC
    """)

    games = cursor.fetchall()
    cursor.close()
    conn.close()
    return games


@app.route("/")
def home():
    ensure_games_table_exists()
    games = get_all_games()
    return render_template("index.html", games=games)


@app.route("/sync", methods=["POST"])
def sync_matches():
    try:
        ensure_games_table_exists()
        matches = fetch_matches_from_api()
        save_matches(matches)
        flash(f"Sync complete. {len(matches)} matches inserted/updated.", "success")
    except Exception as e:
        flash(f"Error syncing matches: {e}", "error")

    return redirect(url_for("home"))


if __name__ == "__main__":
    ensure_games_table_exists()
    app.run(debug=True)