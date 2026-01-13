from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get MongoDB URI from environment variables
MONGO_URI = os.getenv("MONGO_URI")

# Connect to MongoDB client
client = MongoClient(MONGO_URI)
db = client["factchecker_db"]  # Specify database name for MongoDB Atlas

# Check MongoDB connection
try:
    client.admin.command('ping')
    print("MongoDB connection is successful!")
except ConnectionFailure:
    print("MongoDB connection failed!")

# Collections
claims_collection = db["claims"]
users_collection = db["users"]
