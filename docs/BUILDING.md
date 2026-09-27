# Build and dependency workflow

Use Python 3.12 on the target OS. Create a clean virtual environment, install `pip-tools==7.5.2`, and generate a fully hashed lock:

```powershell
python -m pip install pip-tools==7.5.2
python -m piptools compile --generate-hashes --resolver=backtracking --output-file=requirements-lock.txt requirements.in
python -m piptools compile --allow-unsafe --generate-hashes --resolver=backtracking --output-file=requirements-dev-lock.txt requirements-dev.in
python -m pip install --require-hashes -r requirements-lock.txt
python -m pip install --require-hashes -r requirements-dev-lock.txt
```

Review every dependency change and run `python -m pip_audit -r requirements-lock.txt` and `python -m pip_audit -r requirements-dev-lock.txt`. Vulnerability scanning is a development/CI activity and may contact advisory services; it is never invoked by the application.

Build a wheel with `python -m build`. For a standalone desktop package, install a reviewed, pinned PyInstaller version in a separate packaging environment and run `pyinstaller --windowed --name SecureKeePassDiff src/secure_keepass_diff/__main__.py`. PyInstaller is deliberately not a runtime dependency or part of the primary lock. Test the artifact offline on each target OS, retain its build log and hashes, and include all dependency license texts.

