import os
import re

def rep(filename, old, new):
    path = os.path.join("ProFolio/backend", filename)
    if os.path.exists(path):
        with open(path, "r") as f: content = f.read()
        content = content.replace(old, new)
        with open(path, "w") as f: f.write(content)

# test_auth_middleware.py Fixes
rep("tests/test_auth_middleware.py", "test_client: TestClient", "client: AsyncClient")
rep("tests/test_auth_middleware.py", "app_with_middleware: FastAPI", "app_with_middleware: FastAPI, client: AsyncClient")
rep("tests/test_auth_middleware.py", "TestClient", "AsyncClient")

