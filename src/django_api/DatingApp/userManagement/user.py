from pymongo import MongoClient
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
import sys
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from werkzeug.security import generate_password_hash, check_password_hash

sys.path.append('../../') # assuming working dir is DatingApp (with manage.py), this adds the core directory to PATH

from core.profile import UserProfile
from dataclasses import dataclass, asdict

# defining a decorator to check if an user is authenticated
from functools import wraps
from urllib.parse import urlencode
from django.shortcuts import redirect

def login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check if the user is authenticated
        if not request.session.get("user_id"):
            # Capture the origin URL (current path and query string)
            origin = request.get_full_path()

            # Add the `next` parameter with the origin URL
            query_params = urlencode({"next": origin})
            login_url = f"/login/?{query_params}"

            # Redirect to the login URL with the `next` parameter
            return redirect(login_url)

        return view_func(request, *args, **kwargs)
    return wrapper


# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client["user_management"]
users_collection = db["users"]
#"mongodb://localhost:27017/"

# this app was specifically made to test the database interactions of Django with the mongodb DB
@dataclass
class User(UserProfile):
    """A custom User class for MongoDB interaction using pymongo."""

    def __init__(self, db_uri="mongodb://localhost:27017", db_name="user_management", collection_name="users"):
        self.client = MongoClient(db_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def create_user(self,user_data:dict):
        """
        Input : a dict of user data (json like)
        Output: the user mongodb ID
        Creates a new user in the database."""
        if not user_data["email"] or not user_data["password"]:
            raise ValueError("Email and password are required")

        user_data["password"] = generate_password_hash(user_data["password"]) # hash the password

        try:
            # Insert the user data into the collection
            result = self.collection.insert_one(user_data)
            return result.inserted_id  # Return the ID of the inserted document
        except Exception as e:
            print(f"Error inserting user: {e}")
            return None

    def get_user_by_id(self, user_id):
        """Fetches a user by their ID."""
        return self.collection.find_one({"_id": ObjectId(user_id)})

    def authenticate_user(self, email, password):
        """Authenticates a user with email and password."""
        user = self.collection.find_one({"email": email})
        if user and check_password_hash(user["password"], password):
            return user # collection with all attributes etc
        return None

    def reset_password(self, email):
        # no implementation yet : add email token reset ? Or security question ?
        pass

    def update_user(self, user_id, updates):
        """Updates user details.
        Input : a user_id (unique to every user) and a dictionary of updates (python-like)
        Output : result of the update
        """
        return self.collection.update_one({"_id": ObjectId(user_id)}, {"$set": updates})

    def delete_user(self, user_id):
        """Deletes a user from the database."""
        return self.collection.delete_one({"_id": ObjectId(user_id)})

    def to_dict(self):
        return asdict(self) # function that returns a dict : very useful for mongoDB implementation

    def __str__(self):
        return f"MongoDB User Collection: {self.collection.name}"


#TODO Implement the UserManager for login and signup views
