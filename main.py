import albums
import photos
import users
import constants

import json
from os import environ as env
from urllib.parse import quote_plus, urlencode

from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, session, url_for, request

from app_auth import verify_jwt


from google.cloud import datastore

app = Flask(__name__)
app.register_blueprint(albums.bp)
app.register_blueprint(photos.bp)
app.register_blueprint(users.bp)

client = datastore.Client()

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)


app.secret_key = env.get("APP_SECRET_KEY")
ALGORITHMS = ["RS256"]

oauth = OAuth(app)

oauth.register(
    "auth0",
    client_id=env.get("AUTH0_CLIENT_ID"),
    client_secret=env.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{env.get("AUTH0_DOMAIN")}/.well-known/openid-configuration'
)

@app.route('/')
def home():
    return render_template("home.html", session=session.get('user'), pretty=json.dumps(session.get('user'), indent=4))

# Decode the JWT supplied in the Authorization header
@app.route('/decode', methods=['GET'])
def decode_jwt():
    payload = verify_jwt(request)
    return payload     

@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )

@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token

    # if this is a new user, add them to the list of registered users
    query = client.query(kind=constants.users)
    query.add_filter("user_id", "=", session["user"]["userinfo"]["sub"])
    results = list(query.fetch())
    if len(results) == 0:
        new_user = datastore.entity.Entity(key=client.key(constants.users))
        new_user_object = {"user_id": session["user"]["userinfo"]["sub"]}
        new_user.update(new_user_object)
        client.put(new_user)
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://" + env.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("home", _external=True),
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)