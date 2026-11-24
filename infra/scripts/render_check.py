"""Valida o render.yaml: schema oficial do Render + regras que o schema não cobre.

Uso: make render-check   (baixa https://render.com/schema/render.yaml.json)
"""

import json
import ssl
import sys
import urllib.request

import certifi
import jsonschema
import yaml

SCHEMA_URL = "https://render.com/schema/render.yaml.json"


def main(path: str) -> int:
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(SCHEMA_URL, timeout=20, context=context) as response:  # noqa: S310
        schema = json.load(response)
    doc = yaml.safe_load(open(path, encoding="utf-8"))
    problems = [
        f"schema: {'/'.join(map(str, e.path)) or '(raiz)'}: {e.message[:200]}"
        for e in jsonschema.Draft202012Validator(schema).iter_errors(doc)
    ]

    services = doc.get("services", [])
    names = {(s["type"], s["name"]) for s in services}
    databases = {d["name"] for d in doc.get("databases", [])}
    groups = {g["name"] for g in doc.get("envVarGroups", [])}

    for group in doc.get("envVarGroups", []):
        for var in group.get("envVars", []):
            if var.get("sync") is False:
                problems.append(f"grupo {group['name']}: sync:false não é permitido ({var['key']})")

    regions = {r.get("region", "oregon") for r in [*services, *doc.get("databases", [])]}
    if len(regions) > 1:
        problems.append(f"regiões diferentes não conversam pela rede privada: {sorted(regions)}")

    for service in services:
        for var in service.get("envVars", []):
            ref = var.get("fromService")
            if ref and (ref["type"], ref["name"]) not in names:
                problems.append(f"{service['name']}: fromService inexistente {ref}")
            db = var.get("fromDatabase")
            if db and db["name"] not in databases:
                problems.append(f"{service['name']}: fromDatabase inexistente {db['name']}")
            if "fromGroup" in var and var["fromGroup"] not in groups:
                problems.append(f"{service['name']}: grupo inexistente {var['fromGroup']}")

    for problem in problems:
        print("✗", problem)  # noqa: T201
    print("render.yaml válido" if not problems else f"{len(problems)} problema(s)")  # noqa: T201
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "render.yaml"))
