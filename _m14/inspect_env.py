import json, glob, collections

KEYS = ("python", "numpy", "python_version", "numpy_version", "platform", "environment")
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
files = sorted(glob.glob(str(REPO / "results/*/decision.json")))
print("decision.json files:", len(files))

counter = collections.Counter()
no_env = []
for f in files:
    d = json.load(open(f))
    out = {}

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in KEYS and isinstance(v, (str, int, float)):
                    out[k] = str(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(d)
    if out:
        counter[tuple(sorted(out.items()))] += 1
    else:
        no_env.append(f.split("/")[-2])

print("\n-- recorded environments --")
for k, v in counter.most_common():
    print(f"  {v:3d} runs -> {dict(k)}")
print(f"\n-- artifacts with NO env fields: {len(no_env)} --")
for n in no_env[:60]:
    print("   ", n)
