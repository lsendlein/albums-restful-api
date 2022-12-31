from google.cloud import datastore
from flask import Blueprint, Flask, request
import json
import constants

app = Flask(__name__)
client = datastore.Client()

bp = Blueprint('users', __name__, url_prefix='/users')

@bp.route('', methods=['GET'])
def users_get():
    
    if request.method != 'GET':
        return ({"Error": "Method not allowed. Allowed methods: GET"}, 405)
    
    if request.method == 'GET':
        query = client.query(kind=constants.users)
        results = list(query.fetch())

        for e in results:
            new_user_url = request.base_url + '/' + str(e.key.id)
            e["id"] = int(e.key.id)
            e["self"] = new_user_url
        
        return json.dumps(results)
    
@bp.route('/<user_id>', methods=['DELETE'])
def users_delete(user_id):
    
    if request.method != 'DELETE':
        return ({"Error": "Method not allowed. Allowed methods: DELETE"}, 405)   
    
    if request.method == 'DELETE':
        user_key = client.key(constants.users, int(user_id))
        user  = client.get(key=user_key)
        
        if not user:
            return({"Error": "No user with this user_id exists"}, 404)
        
        client.delete(user_key)
        return ('', 204)