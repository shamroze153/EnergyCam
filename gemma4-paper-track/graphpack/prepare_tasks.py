"""Turn a task dataset into the tasks.jsonl that graphpack.run reads.

The competition data layout is not hard-coded here. First look at it:

  python -m graphpack.prepare_tasks --inspect /kaggle/input/<dataset>

then convert, naming the fields if the guesses are wrong:

  python -m graphpack.prepare_tasks --src /kaggle/input/<dataset>/tasks.jsonl \
      --repo-template "/kaggle/input/<dataset>/repos/{instance_id}" --out tasks.jsonl

A row whose snapshot is not on disk but has `repo` + `base_commit` (SWE-bench
style) can be cloned with --clone-to DIR (needs internet in the notebook).

For the Gemma 4 Developer Agent dataset itself there is a one-step mode that
extracts the Python files of every snapshot and links the provided graph and
embeddings (no internet needed):

  python -m graphpack.prepare_tasks --competition /kaggle/input/competitions/gemma-4-developer-agent \
      --extract-to /kaggle/temp/snapshots --out tasks.jsonl
"""
import argparse
import csv
import json
import os
import posixpath
import subprocess
import sys
import tarfile

GUESSES = {
    "instance_id": ["instance_id", "task_id", "id", "name"],
    "problem_statement": ["problem_statement", "issue", "issue_text", "description", "prompt", "task"],
    "patch": ["patch", "gold_patch", "fix_patch", "reference_patch", "solution"],
    "repo": ["repo", "repository", "repo_name"],
    "base_commit": ["base_commit", "commit", "base_sha", "environment_setup_commit"],
    "repo_dir": ["repo_dir", "repo_path", "workspace", "snapshot_dir", "path"],
}


def read_rows(src):
    if src.endswith(".jsonl"):
        with open(src, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]
    if src.endswith(".json"):
        with open(src, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else list(data.values())
    if src.endswith(".csv"):
        with open(src, encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    if src.endswith(".parquet"):
        import pandas as pd
        return pd.read_parquet(src).to_dict("records")
    raise SystemExit(f"unsupported file type: {src}")


def pick(row, field, override):
    if override:
        return row.get(override)
    for k in GUESSES[field]:
        if row.get(k) not in (None, ""):
            return row[k]
    return None


def inspect(path, depth=3):
    print(f"== tree of {path} (depth {depth}, first 15 entries per dir)")
    base = path.rstrip("/").count("/")
    for dp, dns, fns in os.walk(path):
        level = dp.rstrip("/").count("/") - base
        if level >= depth:
            dns[:] = []
            continue
        print("  " * level + os.path.basename(dp) + "/")
        for f in sorted(fns)[:15]:
            full = os.path.join(dp, f)
            print("  " * (level + 1) + f"{f}  ({os.path.getsize(full):,} B)")
        dns[:] = sorted(dns)[:15]
    for dp, _, fns in os.walk(path):
        for f in sorted(fns):
            if f.endswith((".jsonl", ".json", ".csv", ".parquet")):
                full = os.path.join(dp, f)
                try:
                    rows = read_rows(full)
                except Exception as e:
                    print(f"\n== {full}: could not read ({e})")
                    continue
                if rows and isinstance(rows[0], dict):
                    print(f"\n== {full}: {len(rows)} rows, keys = {sorted(rows[0])}")
                    for k, v in rows[0].items():
                        print(f"   {k}: {str(v)[:160]!r}")
                return


def clone(repo, commit, dest_root):
    dest = os.path.join(dest_root, repo.replace("/", "__") + "__" + commit[:10])
    if os.path.isdir(dest):
        return dest
    mirror = os.path.join(dest_root, "_mirrors", repo.replace("/", "__"))
    if not os.path.isdir(mirror):
        subprocess.run(["git", "clone", "--quiet", f"https://github.com/{repo}.git", mirror], check=True)
    subprocess.run(["git", "-C", mirror, "worktree", "add", "--detach", "--force", dest, commit],
                   check=True, capture_output=True)
    return dest


def extract_python(tgz, dest):
    """Extract only .py files (no .git, no symlinks, no paths escaping dest)."""
    if os.path.isdir(dest) and os.listdir(dest):
        return sum(len([f for f in fs if f.endswith(".py")]) for _, _, fs in os.walk(dest))
    count = 0
    with tarfile.open(tgz, "r:*") as tf:
        for m in tf:
            name = posixpath.normpath(m.name[2:] if m.name.startswith("./") else m.name)
            if (not m.isfile() or not name.endswith(".py") or name.startswith(("/", "..", ".git/"))
                    or "/../" in name or "/.git/" in name):
                continue
            out = os.path.join(dest, *name.split("/"))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with tf.extractfile(m) as src, open(out, "wb") as dst:
                dst.write(src.read())
            count += 1
    return count


def prepare_competition(root, extract_to, out, limit=None):
    from .provided import find_files
    with open(os.path.join(root, "tasks.jsonl"), encoding="utf-8") as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    rows = rows[:limit] if limit else rows
    written, skipped = [], []
    for i, r in enumerate(rows, 1):
        tgz = os.path.join(root, "snapshots", f"{r['instance_id']}.tgz")
        if not os.path.exists(tgz):
            skipped.append((r["instance_id"], "no snapshot"))
            continue
        dest = os.path.join(extract_to, r["instance_id"])
        n = extract_python(tgz, dest)
        if n == 0:
            skipped.append((r["instance_id"], "no .py files in snapshot"))
            continue
        graph_json, emb_npz = find_files(root, r["repo"], r["base_commit"])
        written.append({"instance_id": r["instance_id"], "repo": r["repo"], "base_commit": r["base_commit"],
                        "repo_dir": dest, "problem_statement": r["problem_statement"],
                        "hints_text": r.get("hints_text", ""), "patch": r["patch"],
                        "graph_json": graph_json, "emb_npz": emb_npz})
        print(f"[{i}/{len(rows)}] {r['instance_id']}: {n} .py files, graph={'yes' if graph_json else 'no'}, "
              f"embeddings={'yes' if emb_npz else 'no'}", file=sys.stderr)
    with open(out, "w", encoding="utf-8") as fh:
        for t in written:
            fh.write(json.dumps(t) + "\n")
    print(f"wrote {len(written)} tasks to {out}; skipped {len(skipped)}: {skipped}", file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--inspect")
    p.add_argument("--competition", help="root of the Gemma 4 Developer Agent dataset")
    p.add_argument("--extract-to", default="/kaggle/temp/snapshots")
    p.add_argument("--limit", type=int)
    p.add_argument("--src")
    p.add_argument("--out", default="tasks.jsonl")
    p.add_argument("--repo-template", help="e.g. /kaggle/input/x/repos/{instance_id}")
    p.add_argument("--clone-to")
    for f in GUESSES:
        p.add_argument(f"--field-{f.replace('_', '-')}", dest=f"field_{f}")
    a = p.parse_args(argv)
    if a.inspect:
        return inspect(a.inspect)
    if a.competition:
        return prepare_competition(a.competition, a.extract_to, a.out, a.limit)
    if not a.src:
        p.error("--src or --inspect is required")
    rows, out, skipped = read_rows(a.src), [], 0
    for row in rows:
        t = {f: pick(row, f, getattr(a, f"field_{f}")) for f in GUESSES}
        if a.repo_template:
            t["repo_dir"] = a.repo_template.format(**{**row, **{k: v for k, v in t.items() if v}})
        if (not t["repo_dir"] or not os.path.isdir(str(t["repo_dir"]))) and a.clone_to and t["repo"] and t["base_commit"]:
            t["repo_dir"] = clone(t["repo"], t["base_commit"], a.clone_to)
        if not (t["instance_id"] and t["problem_statement"] and t["patch"] and t["repo_dir"]
                and os.path.isdir(str(t["repo_dir"]))):
            skipped += 1
            continue
        out.append({k: t[k] for k in ("instance_id", "repo_dir", "problem_statement", "patch")})
    with open(a.out, "w", encoding="utf-8") as fh:
        for t in out:
            fh.write(json.dumps(t) + "\n")
    print(f"wrote {len(out)} tasks to {a.out}; skipped {skipped} (missing field or snapshot)", file=sys.stderr)


if __name__ == "__main__":
    main()
