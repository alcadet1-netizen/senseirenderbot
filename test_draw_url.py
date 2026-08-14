from urllib.parse import quote

def generate_image_url(prompt: str) -> str:
    encoded_prompt = quote(prompt.strip())
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}"

print(generate_image_url("кот в космосе"))
print(generate_image_url("sunset beach"))
