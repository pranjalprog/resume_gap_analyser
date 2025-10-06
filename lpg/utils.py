import random
import string
import os


def generate_random_string(length=8):
    # Define the pool of characters: letters and digits
    characters = string.ascii_letters + string.digits
    # Randomly select characters from the pool
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string


# Get API key and environment from environment variables
'''PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")

# Initialize Pinecone
pinecone.init(
    api_key=os.getenv("PINECONE_API_KEY"),
    environment=os.getenv("PINECONE_ENVIRONMENT")
)

# Example: connect to an index (replace 'your-index-name' with your actual index)
index = pinecone.Index("question-bank-index)
try:
    index = pinecone.Index(index_name)
    # Try to describe the index
    description = pinecone.describe_index(index_name)
    print("Index connected! Description:", description)
except Exception as e:
    print("Failed to connect to index:", e)

try:
    indexes = pinecone.list_indexes()
    if index_name in indexes:
        print(f"Index '{index_name}' is available and connected.")
    else:
        print(f"Index '{index_name}' does not exist.")
except Exception as e:
    print("Error listing indexes:", e)'''