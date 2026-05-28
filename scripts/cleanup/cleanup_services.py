
import re
file_path = 'src/service_layer/services.py'
with open(file_path, 'r') as f:
    content = f.read()

# Define the pattern for justification functions more explicitly to avoid over-matching
def remove_function(name, content):
    pattern = rf'def {name}\(.*?\n\s+uow\.commit\(\)\n\s+uow\.commit\(\)'
    return re.sub(pattern, '', content, flags=re.DOTALL)

# Also need to manually trim the remaining parts if needed
content = re.sub(r'def submit_justification\(.*?\n\s+uow\.commit\(\)\n', '', content, flags=re.DOTALL)
content = re.sub(r'def dismiss_justification\(.*?\n\s+uow\.commit\(\)\n', '', content, flags=re.DOTALL)

with open(file_path, 'w') as f:
    f.write(content)
