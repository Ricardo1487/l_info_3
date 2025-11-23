import openai
import base64
import os
from dotenv import load_dotenv

load_dotenv()
# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Paths to your images
image_path_1 = "/Users/ricardogiessler/Uni/3. Semester/LInfo3/test6.jpg"
image_path_2 = "/Users/ricardogiessler/Uni/3. Semester/LInfo3/test5.jpg"

# Getting the base64 string
b64_img_1 = encode_image(image_path_1)
b64_img_2 = encode_image(image_path_2)

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
                {"type": "text", "text": """Vergleiche die beiden folgenden Bilder und vergleiche welche gegenstände zu sehen sehen sind, gib mir das Ergebnis ausschließlich als JSON im folgenden Format zurück, bezieh dich dabei nur darum was das für Gegenstände sind:

                {
                  "vergleich": {
                    "gemeinsamkeiten": [ "string", "string", ... ],
                    "unterschiede": [ "string", "string", ... ],
                    "zusammenfassung": "string"
                  }
                }

                Erkläre nichts außerhalb des JSON. Keine Einleitung, keine Erklärung, keine Markdown-Formatierung.
                """},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_img_2}"
                    }
                }
            ],
        }
    ],
)
print(response.choices[0])