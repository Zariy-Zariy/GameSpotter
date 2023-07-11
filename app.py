from flask import Flask, render_template, redirect, request, session
from flask_session import Session
from functools import wraps
import requests
import constant
import sqlite3

app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies) - from problem set 9 (Finance)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

Session(app)

db = sqlite3.connect("database.db", check_same_thread=False)
cur = db.cursor()

# From https://flask.palletsprojects.com/en/2.3.x/patterns/viewdecorators/
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("steam_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login")
def login():
    session.clear()
    # Helped myself with https://stackoverflow.com/questions/53573820/steam-openid-signature-validation to get the api url
    steam_url = f"https://steamcommunity.com/openid/login?openid.ns=http://specs.openid.net/auth/2.0&openid.mode=checkid_setup&openid.claimed_id=http://specs.openid.net/auth/2.0/identifier_select&openid.identity=http://specs.openid.net/auth/2.0/identifier_select&openid.return_to=http://{request.headers.get('Host')}/connect&openid.realm=http://{request.headers.get('Host')}"
    print(steam_url)
    return render_template("login.html", steam_url=steam_url)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/connect")
def connect():
    # Create a session for the user
    session["steam_id"] = request.args["openid.claimed_id"][37:]

    # Check if the user is in the database
    user_account = cur.execute("SELECT * FROM users WHERE id = ?", [session["steam_id"]])
    user_account = user_account.fetchone()

    # Create a user account for him if he doesn't exist in the db
    if user_account is None:

        cur.execute("INSERT INTO users(id) VALUES(?)", [session["steam_id"]])

        #Apply the changes
        db.commit()

    return redirect("/refresh")

@app.route("/")
@login_required
def home():
    # Get the list of games owned by the user
    user_library = cur.execute("SELECT games.* FROM games JOIN user_library ON user_library.game_id = games.id WHERE user_library.user_id = ?", [session["steam_id"]])
    user_library = user_library.fetchall()
    return render_template("home.html", user_library = user_library)

@app.route("/refresh")
@login_required
def refresh():
    # Get all the games
    response = requests.get(f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1?include_appinfo=true&include_played_free_games=true&steamid={session['steam_id']}&key={constant.STEAM_KEY}")
    response = response.json()["response"]

    for game in response["games"]:
        game_info = requests.get(f"https://store.steampowered.com/api/appdetails?appids={game['appid']}")
        game_info = game_info.json()
        game_info = game_info[str(game["appid"])]["data"]

        game_exist = cur.execute("SELECT * FROM games WHERE id = ?", [game["appid"]])
        game_exist = game_exist.fetchone()

        if "metacritic" not in game_info:
            game_info.update({"metacritic": {"score": None}})

        if game_exist is None:

            cur.execute("INSERT INTO games(id,name,img,review) VALUES(?,?,?,?)",
                        [game["appid"], game_info["name"], game_info["header_image"], game_info["metacritic"]["score"]])
            db.commit()
            # Link the genre
            for genre in game_info["genres"]:
                print(genre["description"])


        # Link the game to the user
        link_exist = cur.execute("SELECT * FROM user_library WHERE user_id = ? AND game_id = ?", 
                                [session["steam_id"], game["appid"]])
        link_exist = link_exist.fetchone()

        if link_exist is None:
            cur.execute("INSERT INTO user_library(user_id, game_id) VALUES(?,?)",
                        [session["steam_id"], game["appid"]])
            db.commit()

    return redirect("/")


@app.route("/quiz")
@login_required
def quiz():
    return render_template("quiz.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)