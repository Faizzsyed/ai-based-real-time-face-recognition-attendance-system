"""Review nonignored checkpoint sources; report locations, never secret values."""
from pathlib import Path
import json,re,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
    "credentialed_database_uri":re.compile(r"mongodb(?:\+srv)?://[^\s\"']+:[^\s\"']+@",re.I),
    "private_key":re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token":re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "jwt":re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b"),
    "literal_password":re.compile(r"(?i)\b(?:password|jwt_secret|face_embedding_encryption_key)\s*=\s*[\"']([^\"']{8,})[\"']"),
}


def candidates():
    result=subprocess.run(["git","ls-files","--cached","--others","--exclude-standard","-z"],cwd=ROOT,capture_output=True,check=True)
    return sorted(set(result.stdout.decode().strip("\0").split("\0")))


def audit():
    findings=[];files=candidates()
    for name in files:
        path=ROOT/name
        if not path.is_file():continue
        if (path.name.startswith(".env") and name!=".env.example" or name.startswith(("data/private/","data/face_enrollments/","uploads/"))
                or path.suffix.casefold() in {".enc",".db",".sqlite",".sqlite3",".pem",".p12",".pfx",".jpg",".jpeg",".webp",".onnx",".task",".apk",".aab"}):
            findings.append({"path":name,"kind":"forbidden_checkpoint_artifact"});continue
        try:content=path.read_text(encoding="utf-8-sig")
        except UnicodeError:continue
        for number,line in enumerate(content.splitlines(),1):
            for kind,pattern in PATTERNS.items():
                for match in pattern.finditer(line):
                    # Explicit dummy values in tests/documentation are reviewed fixtures,
                    # not runtime secrets. Never allow actual token/private-key shapes.
                    fixture=name.startswith(("backend/tests/","app/test_"))
                    dummy=any(word in match.group(0).casefold() for word in ("example","placeholder","replace_with","test-","fake","too_short","localhost","username:password"))
                    if kind in {"literal_password","credentialed_database_uri"} and (fixture or dummy):continue
                    findings.append({"path":name,"line":number,"kind":kind})
    return {"files_reviewed":len(files),"findings":findings,"scope":"tracked and nonignored untracked source; values omitted"}


if __name__=="__main__":
    report=audit();print(json.dumps(report,indent=2));raise SystemExit(bool(report["findings"]))
