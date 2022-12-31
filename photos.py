from app_auth import verify_jwt
from google.cloud import datastore
from flask import Blueprint, Flask, request, make_response
import json
import constants

app = Flask(__name__)
client = datastore.Client()

bp = Blueprint('photos', __name__, url_prefix='/photos')

allowed_chars = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
'-', '_', ' ', '/', '\'', '!', '.', ',', '?']

date_allowed_chars = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '/']

# Create a Photo and Get all Photos
@bp.route('', methods=['POST', 'GET'])
def photos_post_get():

    if request.method == 'PUT' or request.method == 'DELETE' or request.method == 'PATCH':
        return ({"Error": "Method not allowed. Allowed methods: POST, GET"}, 405)

    if request.method == 'POST':

        payload = verify_jwt(request)

        # if we get back an error message, return 401
        if isinstance(payload, str): return ({"Error": "Missing or invalid JWT"}, 401)

        if request.content_type != 'application/json':
            return({"Error": "The request Content-Type is not ‘application/json’"}, 415)
        if 'application/json' not in request.accept_mimetypes:
            return({"Error": "The Accept header for this request is not ‘application/json’" }, 406)
        
        content = request.get_json()
        
        # if the object is missing an attribute
        if len(content) < 3:
            new_photo_object = {"Error": "The request object is missing at least one of the required attributes"}
            return (new_photo_object, 400)
        # if object contains an invalid attribute
        if len(content) > 3 or "name" not in content.keys() or "description" not in content.keys() or "date_added" not in content.keys():
            return({"Error": "At least one of the request attributes is invalid."}, 400)
        
        # if name of photo is too long or contains characters that are not allowed or is not a string
        if type(content["name"]) is not str:
            return({"Error": "Photo name is invalid format: Allowed formats: str"}, 400)
        if len(content["name"]) > 50:
            return({"Error": "Photo name is invalid length. Max length: 50 chars"}, 400)
        for char in content["name"]:
            if char not in allowed_chars:
                return ({"Error": "Photo name used invalid char. Allowed chars:  A-Z, a-z, 0-9, [-, _, ' ', \', !, ?, ., ,]"}, 400)

        # if description of photo is too long or contains characters that are not allowed or is not a string
        if type(content["description"]) is not str:
            return({"Error": "Photo description is invalid format: Allowed formats: str"}, 400)
        if len(content["description"]) > 500:
            return({"Error": "Photo description is invalid length. Max length: 500 chars"}, 400)
        for char in content["description"]:
            if char not in allowed_chars:
                return ({"Error": "Photo description used invalid char. Allowed chars:  A-Z, a-z, 0-9, [-, _, ' ', \', !, ?, ., ,]"}, 400)

        # if date_added of photo is too long or contains characters that are not allowed or is not a string
        if type(content["date_added"]) is not str:
            return({"Error": "Photo date_added is invalid format: Allowed formats: str"}, 400)
        if len(content["date_added"]) > 10:
            return({"Error": "Photo date_added is invalid length. Max length: 10 chars (MM/DD/YYYY)"}, 400)
        for char in content["date_added"]:
            if char not in date_allowed_chars:
                return ({"Error": "Photo date_added used invalid char. Allowed chars:  0-9, /"}, 400)
        
        # name of the photo should be unique
        query = client.query(kind=constants.photos)
        query.add_filter("owner", "=", payload["sub"])
        results = list(query.fetch())

        for e in results:
            if e["name"].lower() == content["name"].lower():
                return({"Error": "This photo name is already in use"}, 403)

        new_photo = datastore.entity.Entity(key=client.key(constants.photos))
        new_photo_object = {"name": content["name"], "description": content["description"], "date_added": content["date_added"], "album": None, "owner": payload["sub"]}
        new_photo.update(new_photo_object)
        client.put(new_photo)
        new_photo_url = request.base_url + '/' + str(new_photo.key.id)
        new_photo_object["id"] = new_photo.key.id
        new_photo_object["self"] = new_photo_url
        return (new_photo_object, 201)
    elif request.method == 'GET':

        if 'application/json' not in request.accept_mimetypes:
            return({"Error": "The Accept header for this request is not ‘application/json’" }, 406)

        payload = verify_jwt(request)

        # if JWT is missing or invalid, return an error message
        if isinstance(payload, str): return ({"Error": "Missing or invalid JWT"}, 401)
        
        # otherwise print that person's photos
        query = client.query(kind=constants.photos)
        query.add_filter("owner", "=", payload["sub"])
        results = list(query.fetch())

        # only show 5 per page
        q_limit = int(request.args.get('limit', '5'))
        q_offset = int(request.args.get('offset', '0'))
        l_iterator = query.fetch(limit=q_limit, offset=q_offset)
        pages = l_iterator.pages
        results = list(next(pages))
        if l_iterator.next_page_token:
            next_offset = q_offset + q_limit
            next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
        else:
            next_url = None

        if len(results) > 0:
            for e in results:
                new_photo_url = request.base_url + '/' + str(e.key.id)
                e["id"] = int(e.key.id)
                e["self"] = new_photo_url
        
        output = {"photos": results}
        if next_url:
            output["next"] = next_url
    
        return json.dumps(output)
    else:
        return "Method not recognized"

# Get a Photo, Delete a Photo, and Edit a Photo
@bp.route('<photo_id>', methods=['GET', 'DELETE', 'PUT', 'PATCH'])
def photos_get_delete_put_patch(photo_id):
    if request.method == 'GET':

        payload = verify_jwt(request)

        # if JWT is missing or invalid
        if isinstance(payload, str): return ({"Error": "Missing or invalid JWT"}, 401)
        
        if 'application/json' not in request.accept_mimetypes:
            return({"Error": "The Accept header for this request is not ‘application/json’" }, 406)

        photo_key = client.key(constants.photos, int(photo_id))
        photo = client.get(key=photo_key)
        
        if not photo or photo["owner"] != payload["sub"]:
            return ({"Error": "This photo is owned by someone else or the photo_id is invalid"}, 403)
        
        photo_url = request.host_url + 'photos/' + str(photo.key.id)
        if photo["album"]:
            album_url = request.host_url + 'albums/' + str(photo["album"]["id"])
            photo["album"]["self"] = album_url
        photo["id"] = int(photo_id)
        photo["self"] = photo_url
        return (json.dumps(photo), 200)

    elif request.method == 'PATCH':

        payload = verify_jwt(request)

        # if we get back an error message, return 401
        if isinstance(payload, str): return ({"Error": "Missing or invalid JWT"}, 401)
        
        if request.content_type != 'application/json':
            return({"Error": "The request Content-Type is not ‘application/json’"}, 415)
        if 'application/json' not in request.accept_mimetypes:
            return({"Error": "The Accept header for this request is not ‘application/json’" }, 406)

        content = request.get_json()
        
        # we are not allowed to change id
        if "id" in content.keys(): return ({"Error": "At least one of the request attributes is invalid."}, 400)
        
        photo_key = client.key(constants.photos, int(photo_id))
        photo = client.get(key=photo_key)
        
        if not photo or photo["owner"] != payload["sub"]:
            return ({"Error": "This photo is owned by someone else or the photo_id is invalid"}, 403)
        
        # if patch body contains an invalid attribute
        for key in content.keys():
            if key not in photo.keys():
                return({"Error": "At least one of the request attributes is invalid."}, 400)
            # if name of photo is too long or contains characters that are not allowed or is not a string
            if key == "name":
                if type(content["name"]) is not str:
                    return({"Error": "Photo name is invalid format: Allowed formats: str"}, 400)
                if len(content["name"]) > 50:
                    return({"Error": "Photo name is invalid length. Max length: 50 chars"}, 400)
                for char in content["name"]:
                    if char not in allowed_chars:
                        return ({"Error": "Photo name used invalid char. Allowed chars:  A-Z, a-z, 0-9, [-, _, ' ', \', !, ?, ., ,]"}, 400)

            elif key == "description":
                # if description of photo is too long or contains characters that are not allowed or is not a string
                if type(content["description"]) is not str:
                    return({"Error": "Photo description is invalid format: Allowed formats: str"}, 400)
                if len(content["description"]) > 500:
                    return({"Error": "Photo description is invalid length. Max length: 500 chars"}, 400)
                for char in content["description"]:
                    if char not in allowed_chars:
                        return ({"Error": "Photo description used invalid char. Allowed chars:  A-Z, a-z, 0-9, [-, _, ' ', \', !, ?, ., ,]"}, 400)

            elif key == "date_added":
                # if date_added of photo is too long or contains characters that are not allowed or is not a string
                if type(content["date_added"]) is not str:
                    return({"Error": "Photo date_added is invalid format: Allowed formats: str"}, 400)
                if len(content["date_added"]) > 10:
                    return({"Error": "Photo date_added is invalid length. Max length: 10 chars (MM/DD/YYYY)"}, 400)
                for char in content["date_added"]:
                    if char not in date_allowed_chars:
                        return ({"Error": "Photo date_added used invalid char. Allowed chars:  0-9, /"}, 400)

        # name of the photo should be unique
        query = client.query(kind=constants.photos)
        query.add_filter("owner", "=", payload["sub"])
        results = list(query.fetch())
        
        for e in results:
            if (e["name"].lower() == content["name"].lower()) and (int(e.key.id) != int(photo_id)):
                return({"Error": "This photo name is already in use"}, 403)
        
        name = content["name"] if "name" in content.keys() else photo["name"]
        description = content["description"] if "description" in content.keys() else photo["description"]
        date_added = content["date_added"] if "date_added" in content.keys() else photo["date_added"]
        photo.update({"name": name, "description": description, "date_added": date_added})
        photo_url = request.host_url + 'photos/' + str(photo.key.id)
        photo["id"] = int(photo_id)
        photo["self"] = photo_url
        client.put(photo)
        return (photo, 200)
    elif request.method == 'PUT':

        payload = verify_jwt(request)

        # if we get back an error message, return 401
        if isinstance(payload, str): return ({"Error": "Missing or invalid JWT"}, 401)
        
        if request.content_type != 'application/json':
            return({"Error": "The request Content-Type is not ‘application/json’"}, 415)
        if 'application/json' not in request.accept_mimetypes:
            return({"Error": "The Accept header for this request is not ‘application/json’" }, 406)

        content = request.get_json()
        
        # we are not allowed to change the id
        if "id" in content.keys(): return ({"Error": "At least one of the request attributes is invalid."}, 400)

        # if the photo doesn't exist or belongs to someone else
        photo_key = client.key(constants.photos, int(photo_id))
        photo = client.get(key=photo_key)

        if not photo or photo["owner"] != payload["sub"]:
            return ({"Error": "This photo is owned by someone else or the photo_id is invalid"}, 403)
        
        # if the object is missing an attribute
        if len(content) < 3:
            new_photo_object = {"Error": "The request object is missing at least one of the required attributes"}
            return (new_photo_object, 400)
        # if the object contains an invalid attribute
        if len(content) > 3 or "name" not in content.keys() or "description" not in content.keys() or "date_added" not in content.keys():
            return({"Error": "At least one of the request attributes is invalid."}, 400)

        # if name of photo is too long or contains characters that are not allowed or is not a string
        if type(content["name"]) is not str:
            return({"Error": "Photo name is invalid format: Allowed formats: str"}, 400)
        if len(content["name"]) > 50:
            return({"Error": "Photo name is invalid length. Max length: 50 chars"}, 400)
        for char in content["name"]:
            if char not in allowed_chars:
                return ({"Error": "Photo name used invalid char. Allowed chars:  A-Z, a-z, 0-9, [-, _, ' ']"}, 400)

        # if description of photo is too long or contains characters that are not allowed or is not a string
        if type(content["description"]) is not str:
            return({"Error": "Photo description is invalid format: Allowed formats: str"}, 400)
        if len(content["description"]) > 500:
            return({"Error": "Photo description is invalid length. Max length: 500 chars"}, 400)
        for char in content["description"]:
            if char not in allowed_chars:
                return ({"Error": "Photo description used invalid char. Allowed chars:  A-Z, a-z, 0-9, [-, _]"}, 400)

        # if date_added of photo is too long or contains characters that are not allowed or is not a string
        if type(content["date_added"]) is not str:
            return({"Error": "Photo date_added is invalid format: Allowed formats: str"}, 400)
        if len(content["date_added"]) > 10:
            return({"Error": "Photo date_added is invalid length. Max length: 10 chars (MM/DD/YYYY)"}, 400)
        for char in content["date_added"]:
            if char not in allowed_chars:
                return ({"Error": "Photo date_added used invalid char. Allowed chars:  0-9, /"}, 400)
        
        # name of the photo should be unique
        query = client.query(kind=constants.photos)
        query.add_filter("owner", "=", payload["sub"])
        results = list(query.fetch())

        for e in results:
            if (e["name"].lower() == content["name"].lower()) and (int(e.key.id) != int(photo_id)):
                return({"Error": "This photo name is already in use"}, 403)
        
        photo.update({"name": content["name"], "description": content["description"], "date_added": content["date_added"]})
        photo_url = request.host_url + 'photos/' + str(photo.key.id)
        photo["id"] = int(photo_id)
        photo["self"] = photo_url
        client.put(photo)
        res = make_response(json.dumps(photo))
        res.headers.set('Location', photo_url)
        res.status_code = 303
        return res
    elif request.method == 'DELETE':

        payload = verify_jwt(request)

        # if we get back an error message, return 401
        if isinstance(payload, str): return ({"Error": "Missing or invalid JWT"}, 401)

        photo_key = client.key(constants.photos, int(photo_id))
        photo = client.get(key=photo_key)
        
        # if the photo doesn't exist or is owned by someone else
        if not photo or photo["owner"] != payload["sub"]:
            return ({"Error": "This photo is owned by someone else or the photo_id is invalid"}, 403)

        # if photo is currently in an album, remove the photo from the album's list of photos
        if photo["album"]:
            album_key = client.key(constants.albums, photo["album"]["id"])
            album = client.get(key=album_key)
            if album is None:
                return ({"Error": "No album with this album_id exists"}, 404)
            album["photos"].remove({"id": photo.key.id})
            album.update({"name": album["name"], "description": album["description"], "date_added": album["date_added"], "public": album["public"], "photos": album["photos"]})
            client.put(album)
        
        client.delete(photo_key)
        return ('', 204)
    else:
        return 'Method not recognized'