
import urllib.parse

ref_link = "https://t.me/SenseiBot?start=ref_123456"
share_text = (
    "🐉 Стань самураем! Забирай бонусы и вступай в битву! ⚔️\n\n"
    "Присоединяйся к Sensei, сражайся с боссами и строй свою империю! 🏰💰"
)

encoded_url = urllib.parse.quote(ref_link)
encoded_text = urllib.parse.quote(share_text)
share_url = f"https://t.me/share/url?url={encoded_url}&text={encoded_text}"

print(f"Original URL: {ref_link}")
print(f"Encoded URL: {encoded_url}")
print(f"Encoded Text: {encoded_text}")
print(f"Final Share URL: {share_url}")
