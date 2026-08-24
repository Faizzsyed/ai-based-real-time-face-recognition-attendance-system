"""Interactively verify real local Admin auth without displaying credentials or tokens."""
from __future__ import annotations
import getpass,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"backend"))
from fastapi.testclient import TestClient
from app.main import app

def main():
    identifier=input("Admin username or email: ").strip()
    password=getpass.getpass("Admin password: ")
    with TestClient(app) as client:
        login=client.post("/api/v1/auth/login",json={"identifier":identifier,"password":password,"device_name":"Local verification"})
        del password
        if login.status_code!=200:
            print("REAL API ADMIN LOGIN: FAIL");return 2
        data=login.json()["data"];access=data["accessToken"];refresh=data["refreshToken"]
        me=client.get("/api/v1/auth/me",headers={"Authorization":f"Bearer {access}"})
        rotated=client.post("/api/v1/auth/refresh",json={"refresh_token":refresh,"device_name":"Local verification"})
        if me.status_code!=200 or rotated.status_code!=200:
            print("REAL API ADMIN LOGIN: FAIL");return 2
        user=me.json()["data"]["user"]
        if user.get("role")!="admin" or user.get("username")!=identifier.casefold() and user.get("email")!=identifier.casefold():
            print("REAL API ADMIN LOGIN: FAIL");return 2
        fresh=rotated.json()["data"];client.post("/api/v1/auth/logout",json={"refresh_token":fresh["refreshToken"]},headers={"Authorization":f"Bearer {fresh['accessToken']}"})
        print("REAL API ADMIN LOGIN: PASS")
        print("AUTH ME ROLE: admin")
        print("REFRESH ROTATION: PASS")
        print("TOKENS DISPLAYED: NO")
        return 0
if __name__=="__main__":raise SystemExit(main())
