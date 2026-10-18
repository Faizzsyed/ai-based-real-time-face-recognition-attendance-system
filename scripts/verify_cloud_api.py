"""Verify a real Render HTTPS endpoint before building a remote-test APK."""
from pathlib import Path
import argparse,json,runpy,sys
from urllib.parse import urlsplit
import httpx

ROOT=Path(__file__).resolve().parents[1]


def verify(api_url,client):
    normalize=runpy.run_path(str(ROOT/"app/core/api_config.py"))["normalize_api_url"]
    base=normalize(api_url,require_https=True)
    if not (urlsplit(base).hostname or "").endswith(".onrender.com"):
        raise ValueError("Use the actual Render HTTPS service URL.")
    responses={name:client.get(base+path) for name,path in {
        "health":"/api/v1/health","readiness":"/api/v1/ready",
        "unknown_route":"/api/v1/_cloud_probe_nonexistent","authentication":"/api/v1/admin/students"}.items()}
    health=responses["health"].json();ready=responses["readiness"].json()
    checks={"https":True,"health":responses["health"].status_code==200 and health.get("success") is True,
            "cloud_database":health.get("database")=="connected" and health.get("databaseName")=="attendai_cloud_test",
            "readiness":responses["readiness"].status_code==200 and ready.get("status")=="ready",
            "face_models":ready.get("faceModels")=="loaded","unknown_route":responses["unknown_route"].status_code==404,
            "authentication":responses["authentication"].status_code==401,
            "no_traceback":all(not any(marker in r.text.casefold() for marker in ("traceback","site-packages","file \"")) for r in responses.values())}
    return {"api_url":base,"checks":checks,"passed":all(checks.values())}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--api-url",required=True)
    parser.add_argument("--output",type=Path,default=ROOT/"dist/cloud-api-verification.json");args=parser.parse_args()
    try:
        # A cold free instance can take about a minute; TLS verification stays on.
        with httpx.Client(timeout=90.,follow_redirects=False) as client:report=verify(args.api_url,client)
    except (ValueError,httpx.HTTPError):
        print("Cloud verification failed. Check the real HTTPS URL, wait for cold start, and retry; no APK should be built yet.",file=sys.stderr);return 1
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2));return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
