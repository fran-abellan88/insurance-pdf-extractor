import sys
from pathlib import Path

import google.generativeai as genai

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings

settings = get_settings()


# Configure the API key
genai.configure(api_key=settings.gemini_api_key)

# Upload the file
file_path = Path("test_pdfs/ATENT.pdf")
uploaded_file = genai.upload_file(path=file_path, display_name="ATENT.pdf")

# Optional: see file ID
print(f"Uploaded file ID: {uploaded_file.name}")

# Create model instance
model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")

# Count tokens
token_count = model.count_tokens(["Give me a summary of this document.", uploaded_file])
print(f"token_count={token_count.total_tokens}")

# Generate content
response = model.generate_content(["Give me a summary of this document.", uploaded_file])

# Print result
print(response.text)

# Optional: usage metadata
print(response.usage_metadata)
