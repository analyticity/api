#########################
#Author: Patrik Haas (xhaasp00)
#########################

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from utils import verify_password, hash_password, create_token
from models import  Base, User, Town, Show, Settings

import os
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from geoalchemy2.shape import to_shape, from_shape
from shapely import wkt
from sqlalchemy.sql import func
from database import CentralSessionLocal, central_engine
import jwt
import secrets
import string


router = APIRouter()

load_dotenv()
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 15))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

Base.metadata.create_all(bind=central_engine)

def get_db():
    db = CentralSessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(User).filter(User.name == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/test")
async def test():
    return {"token": "TEST"}

@router.post("/login")
async def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == form_data.username).first()
    if not user or not verify_password(form_data.password, user.passwordhash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.active:
        raise HTTPException(status_code=401, detail="Deactivated account")

    access_token = create_token(
        {"sub": user.name, "role": user.admintype},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_token(
        {"sub": user.name, "role": user.admintype},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False, #V production nastavit na true
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS*24*3600,
        path="/",
    )
    
    return {"token": access_token}

@router.get("/logout")
async def logout(response: Response):
    response.delete_cookie(key="refresh_token")

@router.get("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not valid token")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)
        access_token = create_token(
            {"sub": payload.get("sub"), "role": payload.get("role")},
            timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        refresh_token = create_token(
            {"sub": payload.get("sub"), "role": payload.get("role")},
            timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False, #V production nastavit na true
            samesite="lax",
            max_age=REFRESH_TOKEN_EXPIRE_DAYS*24*3600,
        )
        return {"token": access_token}
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/getUsers")
async def getUsers(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{"name": u.name} for u in users]

@router.post("/getUser")
async def getUsers(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == data.get("user")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    AssingedTown = user.town
    if user.town is not None:
        town = db.query(Town).filter(Town.id == user.town).first()
        AssingedTown = town.name
    return [{"Name": "Id", "Value": user.id, "Show": False},
            {"Name": "Name", "Value": user.name, "Show": True},
            {"Name": "Email", "Value": user.email, "Show": True},
            {"Name": "AdminType", "Value": user.admintype, "Show": False},
            {"Name": "Active", "Value": user.active, "Show": False},
            {"Name": "CreatedAt", "Value": user.createdat.strftime("%d.%m.%Y %H:%M:%S"), "Show": False},
            {"Name": "UpdatedAt", "Value": user.updatedat.strftime("%d.%m.%Y %H:%M:%S"), "Show": False},
            {"Name": "Town", "Value": AssingedTown, "Show": False}]

@router.get("/getTowns")
async def getUsers(db: Session = Depends(get_db)):
    towns = db.query(Town).all()
    return [{"name": t.name, "active": t.active} for t in towns]

@router.post("/getTown")
async def getUsers(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    town = db.query(Town).filter(Town.name == data.get("town")).first()
    show = db.query(Show).filter(Show.town == town.id).first()
    settings = db.query(Settings).filter(Settings.town == town.id).all()
    defaultSettings = db.query(Settings).filter(Settings.town == None).all()
    if not town:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    returnValues = [{"Name": "Id", "Value": town.id, "Show": False, "GroupName": ''},
            {"Name": "Name", "Value": town.name, "Show": show.name, "GroupName": ''},
            {"Name": "DbName", "Value": town.dbname, "Show": show.dbname, "GroupName": ''},
            {"Name": "DbUser", "Value": town.dbuser, "Show": show.dbuser, "GroupName": ''},
            {"Name": "CoverageArea", "Value": to_shape(town.coveragearea).wkt, "Show": show.coveragearea, "GroupName": ''},
            {"Name": "WazeLink", "Value": town.wazelink, "Show": show.wazelink, "GroupName": ''},
            {"Name": "DbHost", "Value": town.dbhost, "Show": show.dbhost, "GroupName": ''},
            {"Name": "DbPortExternal", "Value": town.dbportexternal, "Show": show.dbportexternal, "GroupName": ''},
            {"Name": "DbPortInternal", "Value": town.dbportinternal, "Show": show.dbportinternal, "GroupName": ''},
            {"Name": "DbPassword", "Value": town.dbpassword, "Show": show.dbpassword, "GroupName": ''},
            {"Name": "Description", "Value": town.description, "Show": show.description, "GroupName": ''},
            {"Name": "Active", "Value": town.active, "Show": show.active, "GroupName": ''},
            {"Name": "CreatedAt", "Value": town.createdat.strftime("%d.%m.%Y %H:%M:%S"), "Show": show.createdat, "GroupName": ''},
            {"Name": "UpdatedAt", "Value": town.updatedat.strftime("%d.%m.%Y %H:%M:%S"), "Show": show.updatedat, "GroupName": ''}]
    
    for setting in settings:
         returnValues.append({
            "Name": setting.settingname, 
            "Value": setting.setting, 
            "Description": setting.description,
            "GroupName": setting.groupname,
            "Show": True
        })
    
    for setting in defaultSettings:
        if not any(item["Name"] == setting.settingname for item in returnValues):
            returnValues.append({
            "Name": setting.settingname, 
            "Value": setting.setting,
            "Description": setting.description,
            "GroupName": setting.groupname,
            "Show": True
        })
    
    return {"data": returnValues}

@router.post("/addNewUser")
async def SaveNewUser(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == data.get("name")).first()
    if user:
        return {"error" : "Name"}
    user = db.query(User).filter(User.email == data.get("email")).first()
    if user:
        return {"error" : "Email"}
    
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for _ in range(10))
    AssingedTown = None
    if data.get("town") is not '':
        town = db.query(Town).filter(Town.name == data.get("town")).first()
        AssingedTown = town.id 
    newUser = User(
        name=data.get("name"),
        passwordhash=hash_password(password),
        email=data.get("email"),
        admintype=data.get("admintype"),
        active=str(data.get("active")).strip().lower() == "true",
        updatedat=func.now(),
        town=AssingedTown,
    )
    try:
        db.add(newUser)
        db.commit()         
        return {"ok" : "ok"}
    except Exception as e:
        return {"error" : "Db"}

@router.post("/editOldUser")
async def SaveNewUser(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    editUser = db.query(User).filter(User.id == data.get("id")).first()
    user = db.query(User).filter(User.name == data.get("name")).first()
    if user:
        if user.name != editUser.name:
            return {"error" : "Name"}
    user = db.query(User).filter(User.email == data.get("email")).first()
    if user:
        if user.email != editUser.email:
            return {"error" : "Email"}
    AssingedTown = None
    if data.get("town") is not None:
        town = db.query(Town).filter(Town.name == data.get("town")).first()
        AssingedTown = town.id
    
    editUser.name = data.get("name")
    editUser.email = data.get("email")
    editUser.admintype = data.get("admintype")
    editUser.active = str(data.get("active")).strip().lower() == "true"
    editUser.updatedat = func.now()
    editUser.town = AssingedTown
    try:
        db.commit()
        return {"ok" : "ok"} 
    except Exception as e:
        return {"error" : "Db"}

@router.post("/addNewTown")
async def AddNewTown(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    town = db.query(Town).filter(Town.name == data.get("name")).first()
    if town:
        return {"error" : "Name"}
    
    NewTown = Town(
        name=data.get("name"),
        wazelink=data.get("wazelink"),
        dbhost=data.get("dbhost"),
        dbportexternal=data.get("dbportexternal"),
        dbportinternal=data.get("dbportinternal"),
        dbname=data.get("dbname"),
        dbuser=data.get("dbuser"),
        dbpassword=data.get("dbpassword"),
        description=data.get("description"),
        active=str(data.get("active")).strip().lower() == "true",
        #coveragearea=AssingedTown, need to work out map
        updatedat=func.now(),
    )
    try:
        db.add(NewTown)
        db.commit()
        db.refresh(NewTown)    
    except Exception as e:
        return {"error" : "Db"}

    NewShow = Show(
        name = str(data.get("showname")).strip().lower() == "true",
        dbname = str(data.get("showdbname")).strip().lower() == "true",
        dbuser = str(data.get("showdbuser")).strip().lower() == "true",
        coveragearea = str(data.get("showcoveragearea")).strip().lower() == "true",
        wazelink = str(data.get("showwazelink")).strip().lower() == "true",
        dbhost = str(data.get("showdbhost")).strip().lower() == "true",
        dbportexternal = str(data.get("showdbportexternal")).strip().lower() == "true",
        dbportinternal = str(data.get("showdbportinternal")).strip().lower() == "true",
        dbpassword = str(data.get("showdbpassword")).strip().lower() == "true",
        description = str(data.get("showdescription")).strip().lower() == "true",
        active = str(data.get("showactive")).strip().lower() == "true",
        createdat = False,
        updatedat = False,
        town = NewTown.id,
    )

    try:
        db.add(NewShow)
        db.commit()         
        return {"ok" : "ok"}
    except Exception as e:
        return {"error" : "Db"}

@router.post("/editOldTown")
async def EditOldTown(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    editTown = db.query(Town).filter(Town.id == data.get("id")).first()
    show = db.query(Show).filter(Show.town == data.get("id")).first()
    town = db.query(Town).filter(Town.name == data.get("name")).first()
    if town:
        if town.name != editTown.name:
            return {"error" : "Name"}

    editTown.name = data.get("name")
    editTown.wazelink = data.get("wazelink")
    editTown.dbhost = data.get("dbhost")
    editTown.dbportexternal = data.get("dbportexternal")
    editTown.dbportinternal = data.get("dbportinternal")
    editTown.dbname = data.get("dbname")
    editTown.dbuser = data.get("dbuser")
    editTown.dbpassword = data.get("dbpassword")
    editTown.description = data.get("description")
    editTown.active = str(data.get("active")).strip().lower() == "true"
    editTown.coveragearea =  from_shape(wkt.loads(data.get("coveragearea")), srid=4326)
    editTown.updatedat = func.now()

    show.name = str(data.get("showname")).strip().lower() == "true"
    show.dbname = str(data.get("showdbname")).strip().lower() == "true"
    show.dbuser = str(data.get("showdbuser")).strip().lower() == "true"
    show.coveragearea = str(data.get("showcoveragearea")).strip().lower() == "true"
    show.wazelink = str(data.get("showwazelink")).strip().lower() == "true"
    show.dbhost = str(data.get("showdbhost")).strip().lower() == "true"
    show.dbportexternal = str(data.get("showdbportexternal")).strip().lower() == "true"
    show.dbportinternal = str(data.get("showdbportinternal")).strip().lower() == "true"
    show.dbpassword = str(data.get("showdbpassword")).strip().lower() == "true"
    show.description = str(data.get("showdescription")).strip().lower() == "true"
    show.active = str(data.get("showactive")).strip().lower() == "true"
    show.createdat = str(data.get("showcreatedat")).strip().lower() == "true"
    show.updatedat = str(data.get("showupdatedat")).strip().lower() == "true"

    try:
        db.commit()
        return {"ok" : "ok"} 
    except Exception as e:
        return {"error" : "Db"}

@router.get("/getSettings")
async def GetSettings(db: Session = Depends(get_db)):
    settings = db.query(Settings).filter(Settings.town == None).all()
    settingsData = [
        {
            "settingname": setting.settingname,
            "setting": setting.setting,
            "description": setting.description,
            "groupName": setting.groupname,
        }
        for setting in settings
    ]
    return {"settings": settingsData}

@router.post("/getTownSettings")
async def GetTownSettings(data: dict, db: Session = Depends(get_db)):
    town = db.query(Town).filter(Town.name == data.get("name")).first()
    if not town:
        settings = db.query(Settings).filter(Settings.town.is_(None)).all()
        settingsData = [
            {
                "settingname": setting.settingname,
                "setting": setting.setting,
                "description": setting.description,
                "groupName": setting.groupname,
            }
            for setting in settings
        ]
        return {"settings": settingsData}
    else:
        defaultsettings = db.query(Settings).filter(Settings.town.is_(None)).all()
        settings = db.query(Settings).filter(Settings.town == town.id).all()
        townDict = {s.settingname: s.setting for s in settings}

        mergedSettings = []
        for default in defaultsettings:
            value = townDict.get(default.settingname, default.setting)
            
            mergedSettings.append({
                "settingname": default.settingname,
                "setting": value,
                "description": default.description,
                "groupName": default.groupname,
            })
        return {"settings": mergedSettings, 'id': town.id}


@router.post("/SaveSettings")
async def SaveSettings(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return {'test': 'test'}

@router.post("/saveNewSetting") #Add new thins in settings too
async def SaveNewSetting(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    NewSetting = Settings(
        settingname = data.get('name'),
        setting = data.get('value'),
    )
    try:
        db.add(NewSetting)
        db.commit()       
        return {"ok" : "ok"}  
    except  Exception as e:
        return {"error" : "Db"}