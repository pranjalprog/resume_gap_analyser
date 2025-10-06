from lpg import app
from dotenv import load_dotenv
import os
import openai

load_dotenv()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port="8000", threaded=True, debug=True)


