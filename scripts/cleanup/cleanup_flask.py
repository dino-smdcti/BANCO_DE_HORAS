import re
file_path = 'src/entrypoints/flask_app.py'
with open(file_path, 'r') as f:
    content = f.read()

# Remove generate_missing route
content = re.sub(r'@app\.route\("/manager/generate-missing", methods=\["POST"\]\).*?return redirect\(url_for\("dashboard"\)\)', '', content, flags=re.DOTALL)

with open(file_path, 'w') as f:
    f.write(content)
