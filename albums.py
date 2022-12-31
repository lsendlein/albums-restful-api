from google.cloud import datastore
from flask import Blueprint, Flask, request, make_response
import json
import constants
from app_auth import verify_jwt

app = Flask(__name__)
client = datastore.Client()

bp = Blueprint('albums', __name__, url_prefix='/albums')

allowed_chars = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
'-', '_', ' ', '/', '\'', '!', '.', ',', '?']

date_allowed_chars = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '/']


# Get all albums and Create an Album
@bp.route('', methods=['POST', 'GET'])
def albums_get_post():
    
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
        if len(content) < 4:
            new_album_object = {"Error": "The request object is missing at least one of the required attributes"}
            return (new_album_object, 400)
        # if object contains an invalid attribute
        if len(content) > 4 or "name" not in content.keys() or "description" not in content.keys() or "date_added" not in content.keys() or "public" not in content.keys():
            return({"Error": "At least one of the request attributes is invalid."}, 400)
        
        # if name of album is too long or contains characters that are not allowed or is not a string
        if type(content["name"]) is not str:
            return({"Error": "Album name is invalid format: Allowed formats: str"}, 400)
        if len(content["name"]) > 50:
            return({"Error": "Album name is invalid length. Max length: 50 chars"}, 400)
        for char in content["name"]:
            if char not in allowed_chars:
                return ({"Error": "Album name used invalid char. Allowed chars:  A-Z, a-z, 0-9, [-, _, ' ', \', !, ?, ., ,]"}, 400)

        # if description of album is too long or contains characters that are not allowed or is not a string
        if type(content["description"]) is not str:
            return({"Error": "Album description is invalid format: Allowed formats: str"}, 400)
        if len(content["description"]) > 500:
            return({"Error": "Album description is invalid length. Max length: 500 chars"}, 400)
        for char in content["description"]:
            if char not in allowed_chars:
                return ({"Error": "Album description used invalid char. Allowed chars:  A-Z, a-z, 0-9, [-, _, ' ', \', !, ?, ., ,]"}, 400)

        # if date_added of album is too long or contains characters that are not allowed or is not a string
        if type(content["date_added"]) is not str:
            return({"Error": "Album date_added is invalid format: Allowed formats: str"}, 400)
        if len(content["date_added"]) > 10:
            return({"Error": "Album date_added is invalid length. Max length: 10 chars (MM/DD/YYYY)"}, 400)
        for char in content["date_added"]:
            if char not in date_allowed_chars:
                return ({"Error": "Album date_added used invalid char. Allowed chars:  0-9, /"}, 400)

        # if album's public attribute is not a bool
        if type(content["public"]) is not bool:
            return ({"Error": "The album 'public' attribute is an invalid format. Allowed formats: bool"}, 400)
        
        # name of the album should be unique
        query = client.query(kind=constants.albums)
        query.add_filter("owner", "=", payload["sub"])
        results = list(query.fetch())

        for e in results:
            if e["name"].lower() == content["name"].lower():
                return({"Error": "This album name is already in use"}, 403)

        new_album = datastore.entity.Entity(key=client.key(constants.albums))
        new_album_object = {"name": content["name"], "description": content["description"], "date_added": content["date_added"], "public": content["public"], "photos": [], "owner": payload["sub"]}
        new_album.update(new_album_object)
        client.put(new_album)
        new_album_url = request.base_url + '/' + str(new_album.key.id)
        new_album_object["id"] = int(new_album.key.id)
        new_album_object["self"] = new_album_url
        return (new_album_object, 201)
    elif request.method == 'GET':

        if 'application/json' not in request.accept_mimetypes:
            return({"Error": "The Accept header for this request is not ‘application/json’" }, 406)

        payload = verify_jwt(request)
        
        # if we got back an error message just print all public albums
        if isinstance(payload, str):
            query = client.query(kind=constants.albums)
            results = list(query.fetch())
            total_length = len(results)
            public_results = []

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

            for e in results:
                if e["public"]:
                    new_album_url = request.base_url + '/' + str(e.key.id)
                    for idx, photo in enumerate(e["photos"]):
                        photo_url = request.host_url + 'photos/' + str(photo["id"])
                        e["photos"][idx]["self"] = photo_url
                    e["id"] = int(e.key.id)
                    e["self"] = new_album_url
                    public_results.append(e)
        
            output = {"albums": public_results}
            if next_url:
                output["next"] = next_url
            output["total_items"] = total_length
        
            return json.dumps(output)
        # otherwise print that person's albums
        else:
            query = client.query(kind=constants.albums)
            query.add_filter("owner", "=", payload["sub"])
            results = list(query.fetch())
            total_length = len(results)

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

            # if the token matches user id, print that person's albums
            if len(results) > 0:
                for e in results:
                    new_album_url = request.base_url + '/' + str(e.key.id)
                    for idx, photo in enumerate(e["photos"]):
                        photo_url = request.host_url + 'photos/' + str(photo["id"])
                        e["photos"][idx]["self"] = photo_url
                    e["id"] = int(e.key.id)
                    e["self"] = new_album_url
            
            output = {"albums": results}
            if next_url:
                output["next"] = next_url
            output["total_items"] = total_length
        
            return json.dumps(output)
    else:
        return "Method not recognized"

# Get an album, Delete an album, and Edit an Album
@bp.route('<album_id>', methods=['GET', 'DELETE', 'PUT', 'PATCH'])
def albums_get_delete_put_patch(album_id):
    if request.method == 'GET':

        payload = verify_jwt(request)

        album_key = client.key(constants.albums, int(album_id))
        album  = client.get(key=album_key)
        
        # if JWT is missing or invalid
        if isinstance(payload, str): 
            # if the album is public, return it regardless
            if album['public']:
                album_url = request.host_url + 'albums/' + str(album.key.id)
                album["id"] = int(album_id)
                album["self"] = album_url
                return (album, 200)
            # otherwise send back an error message
            else:
                return ({"Error": "Missing or invalid JWT"}, 401)

        if 'application/json' not in request.accept_mimetypes:
            return({"Error": "The Accept header for this request is not ‘application/json’" }, 406)
        
        if not album: return ({"Error": "This  album_id is invalid"}, 403)
        
        if album["owner"] != payload["sub"]:
            if album["public"]:
                album_url = request.host_url + 'albums/' + str(album.key.id)
                album["id"] = int(album_id)
                album["self"] = album_url
                return (album, 200)
            return ({"Error": "This album is owned by someone else or the album_id is invalid"}, 403)

        album_url = request.host_url + 'albums/' + str(album.key.id)
        for idx, photo in enumerate(album["photos"]):
            photo_url = request.host_url + 'photos/' + str(photo["id"])
            album["photos"][idx]["id"] = photo["id"]
            album["photos"][idx]["self"] = photo_url
        album["id"] = int(album_id)
        album["self"] = album_url
        return album
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
        
        album_key = client.key(constants.albums, int(album_id))
        album = client.get(key=album_key)
        
        if not album or album["owner"] != payload["sub"]:
            return ({"Error": "This album is owned by someone else or the album_id is invalid"}, 403)
        
        # if patch body contains an invalid attribute
        for key in content.keys():
            if key not in album.keys():
                return({"Error": "At least one of the request attributes is invalid."}, 400)
            # if name of album is too long or contains characters that are not allowed or is not a string
            if key == "name":
                if type(content["name"]) is not str:
                    return({"Error": "Album name is invalid format: Allowed formats: str"}, 400)
                if len(content["name"]) > 50:
                    return({"Error": "Album name is invalid length. Max length: 50 chars"}, 400)
                for char in content["name"]:
                    if char not in allowed_chars:
                        return ({"Error": "Album name used invalid char. Allowed chars:  A-Z, a-z, 0-9, [-, _, ' ', \', !, ?, ., ,]"}, 400)

            elif key == "description":
                # if description of album is too long or contains characters that are not allowed or is not a string
                if type(content["description"]) is not str:
                    return({"Error": "Album description is invalid format: Allowed formats: str"}, 400)
                if len(content["description"]) > 500:
                    return({"Error": "Album description is invalid length. Max length: 500 chars"}, 400)
                for char in content["description"]:
                    if char not in allowed_chars:
                        return ({"Error": "Album description used invalid char. Allowed chars:  A-Z, a-z, 0-9, [-, _, ' ', \', !, ?, ., ,]"}, 400)

            elif key == "date_added":
                # if date_added of album is too long or contains characters that are not allowed or is not a string
                if type(content["date_added"]) is not str:
                    return({"Error": "Album date_added is invalid format: Allowed formats: str"}, 400)
                if len(content["date_added"]) > 10:
                    return({"Error": "Album date_added is invalid length. Max length: 10 chars (MM/DD/YYYY)"}, 400)
                for char in content["date_added"]:
                    if char not in date_allowed_chars:
                        return ({"Error": "Album date_added used invalid char. Allowed chars:  0-9, /"}, 400)

            elif key == "public":
                # if public is not a bool, reject
                if type(content["public"]) is not bool:
                    return ({"Error": "The album 'public' attribute is an invalid format. Allowed formats: bool"}, 400)

        # name of the album should be unique
        query = client.query(kind=constants.albums)
        query.add_filter("owner", "=", payload["sub"])
        results = list(query.fetch())
        
        for e in results:
            if (e["name"].lower() == content["name"].lower()) and (int(e.key.id) != int(album_id)):
                return({"Error": "This album name is already in use"}, 403)
        
        name = content["name"] if "name" in content.keys() else album["name"]
        description = content["description"] if "description" in content.keys() else album["description"]
        date_added = content["date_added"] if "date_added" in content.keys() else album["date_added"]
        public = content["public"] if "public" in content.keys() else album["public"]
        album.update({"name": name, "description": description, "date_added": date_added, "public": public, "owner": album["owner"]})
        album_url = request.host_url + 'albums/' + str(album.key.id)
        album["id"] = int(album_id)
        album["self"] = album_url
        client.put(album)
        return (album, 200)
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

        # if the album doesn't exist
        album_key = client.key(constants.albums, int(album_id))
        album = client.get(key=album_key)
        
        if not album or album["owner"] != payload["sub"]:
            return ({"Error": "This album is owned by someone else or the album_id is invalid"}, 403)
        
        # if the object is missing an attribute
        if len(content) < 4:
            new_album_object = {"Error": "The request object is missing at least one of the required attributes"}
            return (new_album_object, 400)
        # if the object contains an invalid attribute
        if len(content) > 4 or "name" not in content.keys() or "description" not in content.keys() or "date_added" not in content.keys() or "public" not in content.keys():
            return({"Error": "At least one of the request attributes is invalid."}, 400)

        # if name of album is too long or contains characters that are not allowed or is not a string
        if type(content["name"]) is not str:
            return({"Error": "Album name is invalid format: Allowed formats: str"}, 400)
        if len(content["name"]) > 50:
            return({"Error": "Album name is invalid length. Max length: 50 chars"}, 400)
        for char in content["name"]:
            if char not in allowed_chars:
                return ({"Error": "Album name used invalid char. Allowed chars:  A-Z, a-z, 0-9, [-, _, ' ']"}, 400)

        # if description of album is too long or contains characters that are not allowed or is not a string
        if type(content["description"]) is not str:
            return({"Error": "Album description is invalid format: Allowed formats: str"}, 400)
        if len(content["description"]) > 500:
            return({"Error": "Album description is invalid length. Max length: 500 chars"}, 400)
        for char in content["description"]:
            if char not in allowed_chars:
                return ({"Error": "Album description used invalid char. Allowed chars:  A-Z, a-z, 0-9, [-, _]"}, 400)

        # if date_added of album is too long or contains characters that are not allowed or is not a string
        if type(content["date_added"]) is not str:
            return({"Error": "Album date_added is invalid format: Allowed formats: str"}, 400)
        if len(content["date_added"]) > 10:
            return({"Error": "Album date_added is invalid length. Max length: 10 chars (MM/DD/YYYY)"}, 400)
        for char in content["date_added"]:
            if char not in allowed_chars:
                return ({"Error": "Album date_added used invalid char. Allowed chars:  0-9, /"}, 400)

        # if public is not a bool, reject
        if type(content["public"]) is not bool:
            return ({"Error": "The album 'public' attribute is an invalid format. Allowed formats: bool"}, 400)
        
        # name of the album should be unique
        query = client.query(kind=constants.albums)
        query.add_filter("owner", "=", payload["sub"])
        results = list(query.fetch())

        for e in results:
            if (e["name"].lower() == content["name"].lower()) and (int(e.key.id) != int(album_id)):
                return({"Error": "This album name is already in use"}, 403)
        
        album.update({"name": content["name"], "description": content["description"], "date_added": content["date_added"], "public": content["public"], "owner": album["owner"]})
        album_url = request.host_url + 'albums/' + str(album.key.id)
        album["id"] = int(album_id)
        album["self"] = album_url
        client.put(album)
        res = make_response(json.dumps(album))
        res.headers.set('Location', album_url)
        res.status_code = 303
        return res
    elif request.method == 'DELETE':

        payload = verify_jwt(request)

        # if we get back an error message, return 401
        if isinstance(payload, str): return ({"Error": "Missing or invalid JWT"}, 401)

        album_key = client.key(constants.albums, int(album_id))
        album  = client.get(key=album_key)
        
        if not album or album["owner"] != payload["sub"]:
            return ({"Error": "This album is owned by someone else or the album_id is invalid"}, 403)
        
        # if the album has photos
        if album["photos"]:
            for photo in album["photos"]:
                photo_key = client.key(constants.photos, photo["id"])
                photo = client.get(key=photo_key)
                if photo is None:
                    return ({"Error": "No photo with this photo_id exists"}, 404)
                photo.update({"name": photo["name"], "description": photo["description"], "date_added": photo["date_added"], "album": None})
                client.put(photo)
        
        client.delete(album_key)
        return ('', 204)
    else: 
        return "Method not recognized"

# Assign a Photo to an Album and Remove a Photo from an Album
@bp.route('<album_id>/photos/<photo_id>', methods=['PUT', 'DELETE'])
def photo_put_delete(album_id, photo_id):
    
    if request.method == 'GET' or request.method == 'PATCH':
        return ({"Error": "Method not allowed. Allowed methods: PUT, DELETE"}, 405)
    
    if request.method == 'PUT':
        payload = verify_jwt(request)

        # if JWT is missing or invalid
        if isinstance(payload, str): return ({"Error": "Missing or invalid JWT"}, 401)

        album_key = client.key(constants.albums, int(album_id))
        album = client.get(key=album_key)
        if not album or album["owner"] != payload["sub"]:
            return ({"Error": "This album is owned by someone else or the album_id is invalid"}, 403)
        
        photo_key = client.key(constants.photos, int(photo_id))
        photo  = client.get(key=photo_key)
        if not photo or photo["owner"] != payload["sub"]:
            return ({"Error": "This photo is owned by someone else or the photo_id is invalid"}, 403)
        
        # if the photo is not already assigned to a different album, assign the photo to the album
        if photo["album"] is None:
            photo.update({"name": photo["name"], "description": photo["description"], "date_added": photo["date_added"], "album": {"id": album.key.id, "name": album["name"]}})
            album["photos"].append({"id": photo.key.id})
            album.update({"name": album["name"], "description": album["description"], "date_added": album["date_added"], "public": album["public"], "photos": album["photos"], "owner": album["owner"]})
            client.put(photo)
            client.put(album)
            return ('', 204)
        else:
            return ({"Error": "The photo is already in another album"}, 403)
    elif request.method == 'DELETE':
        payload = verify_jwt(request)

        # if JWT is missing or invalid
        if isinstance(payload, str): return ({"Error": "Missing or invalid JWT"}, 401)

        photo_key = client.key(constants.photos, int(photo_id))
        photo = client.get(key=photo_key)
        
        # if photo doesn't exist or photo in not on specified album
        if photo is None or photo["album"] is None or photo["owner"] != payload["sub"]:
            return({"Error": "No album with this album_id contains the photo with this photo_id"}, 403)

        # if the photo is owned by someone else
        if photo["owner"] != payload["sub"]:
            return ({"Error": "This album is owned by someone else"}, 403)
        
        album_key = client.key(constants.albums, int(album_id))
        album  = client.get(key=album_key)
        
        # if album doesn't exist or photo not in album photos list
        if album is None or {"id": photo.key.id} not in album["photos"] or album["owner"] != payload["sub"]:
            return ({"Error": "No album with this album_id contains the photo with this photo_id"}, 403)

        # if the album is owned by someone else
        if album["owner"] != payload["sub"]:
            return ({"Error": "This album is owned by someone else or the album_id is invalid"}, 403)
        
        # if the photo is in the album, remove the album from the photo's album value and take the photo off the album's list of photos
        if photo["album"]["id"] == album.key.id:
            photo.update({"name": photo["name"], "description": photo["description"], "date_added": photo["date_added"], "album": None})
            album["photos"].remove({"id": photo.key.id})
            album.update({"name": album["name"], "description": album["description"], "date_added": album["date_added"], "public": album["public"], "photos": album["photos"], "owner": album["owner"]})
            client.put(photo)
            client.put(album)
            return ('', 204)
        else:
            return ({"Error": "No album with this album_id contains the photo with this photo_id"}, 404)
    else:
        return 'Method not recognized'