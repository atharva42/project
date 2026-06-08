import os
from dotenv import load_dotenv

def load_config():
    load_dotenv()
    return {
        "api_key": os.getenv("GOOGLE_API_KEY"),
        # "endpoint": os.getenv("ENDPOINT"),
        # "deployment": os.getenv("DEPLOYMENT").
        "model_name": os.getenv("MODEL_NAME")
    }
