import yaml

INPUT_FILE = "/home/noah/Downloads/TFE-github/TFE-Kathara-Lab/lab-variation-project-statique/variation_model/variants.yaml"
OUTPUT_FILE = "/home/noah/Downloads/TFE-github/TFE-Kathara-Lab/lab-variation-project-statique/variation_model/variants.yaml"

assert INPUT_FILE == OUTPUT_FILE, "Input and output files must be the same for in-place modification"

with open(INPUT_FILE, "r") as f:
    data = yaml.safe_load(f)

variants = data["variants"]

for i, variant in enumerate(variants):
    variant["id"] = i

with open(OUTPUT_FILE, "w") as f:
    yaml.dump(data, f, sort_keys=False)

print(f"✅ IDs reassigned from 0 to {len(variants)-1}")