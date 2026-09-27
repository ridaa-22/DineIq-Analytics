from config import PATHS, REPORTS_DIR, MODELS_DIR, DATASET_VERSION

print("Dataset Version:", DATASET_VERSION)
print("Reports Dir:", REPORTS_DIR)
print("Models Dir:", MODELS_DIR)

for name, path in PATHS.items():
    exists = "✅ Found" if __import__("os").path.exists(path) else "❌ Missing"
    print(f"{name}: {path} -> {exists}")