import re
import json

content = '```json\n[\n  "0123456789"\n]\n```'
content = re.sub(r'^```json\s*|\s*```$', '', content.strip(), flags=re.MULTILINE)
print(content)
print(json.loads(content))
