import re
file_path = 'src/entrypoints/flask_app.py'
with open(file_path, 'r') as f:
    content = f.read()

# Pattern for justification routes
routes_to_remove = [
    r'@app\.route\("/manager/justify-ponto/.*?\n.*?return redirect\(url_for\("dashboard"\)\)',
]
for route in routes_to_remove:
    content = re.sub(route, '', content, flags=re.DOTALL)

with open(file_path, 'w') as f:
    f.write(content)
