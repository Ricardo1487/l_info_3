import openai
import base64
import os
from dotenv import load_dotenv

load_dotenv()
# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Path to your image
image_path = "/Users/ricardogiessler/Uni/3. Semester/LInfo3/test1.jpg"

# Getting the base64 string
b64_img = encode_image(image_path)

client = openai.Client(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=f"https://xinference.ostfalialabs.org/v1"
)
response = client.chat.completions.create(
    model="qwen2.5-vl-instruct",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What’s in this image?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_img}",
                    },
                },
            ],
        }
    ],
)
print(response.choices[0])