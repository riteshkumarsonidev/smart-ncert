import json
import os
from datetime import datetime
from bson.objectid import ObjectId

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
PDFS_FILE = os.path.join(DATA_DIR, "pdfs.json")
QUIZZES_FILE = os.path.join(DATA_DIR, "quizzes.json")

# Ensure data directory exists
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def _load_data(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def _save_data(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, default=str)

class LocalDB:
    def __init__(self):
        self.users = self.Collection(USERS_FILE)
        self.pdfs = self.Collection(PDFS_FILE)
        self.quizzes = self.Collection(QUIZZES_FILE)

    class Collection:
        def __init__(self, file_path):
            self.file_path = file_path

        def find(self, query=None):
            data = _load_data(self.file_path)
            if not query:
                return data
            
            result = []
            for item in data:
                match = True
                for key, value in query.items():
                    # Handle ObjectId conversion by comparing as strings
                    if str(item.get(key)) != str(value):
                        match = False
                        break
                if match:
                    result.append(item)
            return result

        def find_one(self, query):
            data = self.find(query)
            return data[0] if data else None

        def insert_one(self, document):
            data = _load_data(self.file_path)
            if "_id" not in document:
                document["_id"] = str(ObjectId())
            if "date" in document and isinstance(document["date"], datetime):
                document["date"] = document["date"].isoformat()
            
            data.append(document)
            _save_data(self.file_path, data)
            return document

        def delete_one(self, query):
            data = _load_data(self.file_path)
            new_data = []
            deleted = False
            for item in data:
                match = True
                for key, value in query.items():
                    # Handle ObjectId conversion if necessary
                    if str(item.get(key)) != str(value):
                        match = False
                        break
                if match and not deleted:
                    deleted = True
                    continue
                new_data.append(item)
            _save_data(self.file_path, new_data)
            return deleted

db = LocalDB()
