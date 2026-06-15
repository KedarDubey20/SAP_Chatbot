"""
Chat Database - Singleton instance of ChatStorageService
Import chat_db from here everywhere in the app.
"""
from .chat_storage import ChatStorageService

# Single instance shared across the entire app
chat_db = ChatStorageService(db_path="./chat_history.db")