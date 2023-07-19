from flask import Flask, render_template, redirect, request, session
from flask_session import Session
from functools import wraps
import requests
import constant
import sqlite3
import time

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

        game_exist = cur.execute("SELECT * FROM games WHERE id = ?", [game["appid"]])
        game_exist = game_exist.fetchone()

        if game_exist is None:
            game_info = requests.get(f"https://store.steampowered.com/api/appdetails?appids={game['appid']}&l=english")
            game_info = game_info.json()
            game_info = game_info[str(game["appid"])]["data"]

            if "metacritic" not in game_info:
                game_info.update({"metacritic": {"score": None}})

            cur.execute("INSERT INTO games(id,name,img,review) VALUES(?,?,?,?)",
                        [game["appid"], game_info["name"], game_info["header_image"], game_info["metacritic"]["score"]])
            db.commit()
            # Link the genre
            for genre in game_info["genres"]:
                genre_exist = cur.execute("SELECT * FROM genres WHERE game_id = ? AND genre = ?", [game["appid"], genre["description"]])
                genre_exist = genre_exist.fetchone()

                if genre_exist is None:
                    cur.execute("INSERT INTO genres(game_id, genre) VALUES(?, ?)", [game["appid"], genre["description"]])
                    db.commit()


        # Link the game to the user
        link_exist = cur.execute("SELECT * FROM user_library WHERE user_id = ? AND game_id = ?", 
                                [session["steam_id"], game["appid"]])
        link_exist = link_exist.fetchone()

        if link_exist is None:
            cur.execute("INSERT INTO user_library(user_id, game_id) VALUES(?,?)",
                        [session["steam_id"], game["appid"]])
            db.commit()

        cur.execute("UPDATE user_library SET playtime = ?, time_last_played = ? WHERE user_id = ? AND game_id = ?", [game["playtime_forever"], game["rtime_last_played"], session["steam_id"], game["appid"]])
        db.commit()

    return redirect("/")


@app.route("/quiz", methods=["GET", "POST"])
@login_required
def quiz():
    if request.method == "POST":
        #Get the list of games that a user have with their genres
        games_never_played = cur.execute("SELECT name, img, review, id FROM user_library JOIN games ON user_library.game_id = games.id WHERE user_id = ? AND playtime < 5", [session["steam_id"]])
        games_never_played = games_never_played.fetchall()
        for i in range(len(games_never_played)):
            games_never_played[i] += tuple([cur.execute("SELECT genre FROM genres WHERE game_id = ?", [games_never_played[i][3]]).fetchall()])

        games_played_in_past = cur.execute("SELECT * FROM user_library WHERE user_id = ? AND playtime > 5 AND time_last_played < ?", [session["steam_id"], time.time() - 63113852]) #current time minus 2 years in UNIX
        games_played_in_past = games_played_in_past.fetchall()
        for i in range(len(games_played_in_past)):
            games_played_in_past[i] += tuple([cur.execute("SELECT genre FROM genres WHERE game_id = ?", [games_played_in_past[i][3]]).fetchall()])

        #Non-exaustive list of steam genres
        interested_genres = {
            "Action" : 0,
            "Strategy" : 0,
            "Adventure" : 0,
            "Indie" : 0,
            "RPG" : 0,
            "Casual" : 0,
            "Simulation" : 0,
            "Racing" : 0,
            "Violent" : 0,
            "Massively Multiplayer" : 0,
            "Sports" : 0,
            "Short" : 0
        }
        gaming_experience = request.form.get("gaming_experience")
        if gaming_experience == "Casual":

            interested_genres["Adventure"] += 1
            interested_genres["Casual"] += 1
            interested_genres["Short"] += 1

        elif gaming_experience == "Intensive":
            interested_genres["Action"] += 1
            interested_genres["RPG"] += 1
            interested_genres["Violent"] += 1
            interested_genres["Massively Multiplayer"] += 1
        
        else:
            return render_template("quiz.html", error="You didnt finish the quiz :(")

        gaming_level = request.form.get("gaming_level")
        if gaming_level == "Roockie":
            interested_genres["Casual"] += 1
            interested_genres["Short"] += 1

        elif gaming_level == "Below Average":
            interested_genres["Adventure"] += 1
            interested_genres["Casual"] += 1

        elif gaming_level == "Average":
            interested_genres["Racing"] += 1
            interested_genres["Simulation"] += 1
            interested_genres["Sports"] += 1

        elif gaming_level ==  "Expert":
            interested_genres["Massively Multiplayer"] += 1
            interested_genres["RPG"] += 1
            interested_genres["Strategy"] += 1
            interested_genres["Violent"] += 1

        else:
            return render_template("quiz.html", error="You didnt finish the quiz :(")

        playtime = request.form.get("Playtime")
        if playtime == "1-2 hours":
            interested_genres["Adventure"] += 1
            interested_genres["Short"] += 1
            interested_genres["Casual"] += 1

        elif playtime == "3-4 hours":
            interested_genres["Racing"] += 1

        elif playtime == "5+ hours":
            interested_genres["Violent"] += 1
            interested_genres["RPG"] += 1
            interested_genres["Massively Multiplayer"] += 1
        
        else:
            return render_template("quiz.html", error="You didnt finish the quiz :(")

        indie = request.form.get("Indie")
        if indie == "Yes":
            interested_genres["Indie"] += 1
        
        elif indie != "No":
            return render_template("quiz.html", error="You didnt finish the quiz :(")

        favorite_game = request.form.get("favorite_game")
        if favorite_game == "Minecraft":
            interested_genres["Adventure"] += 1
            interested_genres["Simulation"] += 1

        elif favorite_game == "Doom":
            interested_genres["Violent"] += 1
            interested_genres["Action"] += 1

        elif favorite_game == "Overwatch":
            interested_genres["Massively Multiplayer"] += 1
            interested_genres["Sports"] += 1

        elif favorite_game == "Roller coaster tycoon":
            interested_genres["Strategy"] += 1
            interested_genres["Simulation"] += 1
        
        else:
            return render_template("quiz.html", error="You didnt finish the quiz :(")

        for genre in interested_genres:
            interested_genres[genre] = interested_genres[genre] / sum(interested_genres.values())

        print(interested_genres)  
        return render_template("answer.html")
    
    return render_template("quiz.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)