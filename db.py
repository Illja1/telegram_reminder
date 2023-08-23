from pymongo import MongoClient
from bson.objectid import ObjectId 

# MongoDB connection settings
DATABASE_URL = "mongodb://localhost:27017"
DATABASE_NAME = "Telegram_bot"
REMINDER_COLLECTION = "test" 

# Establish a connection to the database
client = MongoClient(DATABASE_URL)
db = client[DATABASE_NAME]
