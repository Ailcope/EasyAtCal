import re

url = "https://eu-west-3.api.easyatwork.com/customers/1234/employees/5678/shifts?from=2024-01-01"
match = re.search(r"^(https?://[^/]+)/customers/(\d+)/employees/(\d+)", url)
if match:
    print(match.groups())
