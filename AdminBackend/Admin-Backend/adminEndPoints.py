#########################
#Author: Patrik Haas (xhaasp00)
#########################

from datetime import timedelta
from datetime import datetime
from zoneinfo import ZoneInfo
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

from zoneinfo import ZoneInfo

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

#######################################
#Authentication routes
#######################################
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

#######################################
#Get User/Town list
#######################################
@router.get("/getUsers")
async def getUsers(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{"name": u.name} for u in users]

@router.post("/getUser")
async def getUser(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
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
            {"Name": "CreatedAt", "Value": user.createdat.astimezone(ZoneInfo("Europe/Bratislava")).strftime("%d.%m.%Y %H:%M:%S"), "Show": False},
            {"Name": "UpdatedAt", "Value": user.updatedat.astimezone(ZoneInfo("Europe/Bratislava")).strftime("%d.%m.%Y %H:%M:%S"), "Show": False},
            {"Name": "Town", "Value": AssingedTown, "Show": False}]

@router.get("/getTowns")
async def getTowns(db: Session = Depends(get_db)):
    towns = db.query(Town).all()
    return [{"id": t.id, "name": t.name, "active": t.active, "description": t.description} for t in towns]

@router.post("/getTown")
async def getTown(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    town = db.query(Town).filter(Town.name == data.get("town")).first()
    show = db.query(Show).filter(Show.town == town.id).first()
    settings = db.query(Settings).filter(Settings.town == town.id).all()
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
            {"Name": "CreatedAt", "Value": town.createdat.astimezone(ZoneInfo("Europe/Bratislava")).strftime("%d.%m.%Y %H:%M:%S"), "Show": show.createdat, "GroupName": ''},
            {"Name": "UpdatedAt", "Value": town.updatedat.astimezone(ZoneInfo("Europe/Bratislava")).strftime("%d.%m.%Y %H:%M:%S"), "Show": show.updatedat, "GroupName": ''}]
    

    settings.sort(key=lambda x: x.varname)
    for setting in settings:
         returnValues.append({
            "VarName": setting.varname,
            "Name": setting.settingname, 
            "Value": setting.setting, 
            "Description": setting.description,
            "GroupName": setting.groupname,
            "Show": True
        })
    
    return {"data": returnValues}

#######################################
#User routes
#######################################
@router.post("/addNewUser")
async def SaveNewUser(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == data.get("name")).first()
    if user:
        return {"error" : "Name"}
    user = db.query(User).filter(User.email == data.get("email")).first()
    if user:
        return {"error" : "Email"}
    
    AssingedTown = None
    print(data.get("town"))
    if data.get("town") is not '':
        town = db.query(Town).filter(Town.name == data.get("town")).first()
        AssingedTown = town.id 
    newUser = User(
        name=data.get("name"),
        passwordhash=hash_password(data.get("password")),
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
async def SaveOldUser(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    editUser = db.query(User).filter(User.id == data.get("id")).first()
    user = db.query(User).filter(User.name == data.get("name")).first()
    if user:
        if user.id != editUser.id:
            return {"error" : "Name"}
    user = db.query(User).filter(User.email == data.get("email")).first()
    if user:
        if user.id != editUser.id:
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

@router.post("/editPassChange")
async def editPassChange(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == data.get("UserName")).first()
    if data.get("New1") != data.get("New2"):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user or not verify_password(data.get("Old"), user.passwordhash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user.passwordhash = hash_password(data.get("New2"))

    try:
        db.commit()
        return {"ok" : "ok"} 
    except Exception as e:
        return {"error" : "Db"}

@router.post("/deleteUser")
async def DeleteUser(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == data.get("id")).first()
    try:
        db.delete(user)
        db.commit()
    except Exception as e:
        return {"error" : "Db"}

#######################################
#Town routes
#######################################
@router.post("/addNewTown")
async def AddNewTown(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    townSettings = data.get('settings');
    townValues = data.get('townValues')

    town = db.query(Town).filter(Town.name == townValues.get("name")).first()
    if town:
        return {"error" : "Name"}
    
    NewTown = Town(
        name=townValues.get("name"),
        wazelink=townValues.get("wazelink"),
        dbhost=townValues.get("dbhost"),
        dbportexternal=townValues.get("dbportexternal"),
        dbportinternal=townValues.get("dbportinternal"),
        dbname=townValues.get("dbname"),
        dbuser=townValues.get("dbuser"),
        dbpassword=townValues.get("dbpassword"),
        description=townValues.get("description"),
        active=str(townValues.get("active")).strip().lower() == "true",
        coveragearea=from_shape(wkt.loads(townValues.get("coveragearea")), srid=4326),
        updatedat=func.now(),
    )
    try:
        db.add(NewTown)
        db.commit()
        db.refresh(NewTown)    
    except Exception as e:
        return {"error" : "Db"}

    settings = db.query(Settings).filter(Settings.town == None).all()
    for setting in settings:
        for townSetting in townSettings:
            if setting.varname == townSetting.get("VarName"):
                NewSetting = Settings(
                    varname = setting.varname,
                    settingname = setting.settingname,
                    setting = townSetting.get('Value'),
                    town = NewTown.id,
                    description =  setting.description,
                    groupname =  setting.groupname
                )
                try:
                    db.add(NewSetting)
                    db.commit()
                except Exception as e:
                    return {"error" : "Db"}

    NewShow = Show(
        name = str(townValues.get("showname")).strip().lower() == "true",
        dbname = str(townValues.get("showdbname")).strip().lower() == "true",
        dbuser = str(townValues.get("showdbuser")).strip().lower() == "true",
        coveragearea = str(townValues.get("showcoveragearea")).strip().lower() == "true",
        wazelink = str(townValues.get("showwazelink")).strip().lower() == "true",
        dbhost = str(townValues.get("showdbhost")).strip().lower() == "true",
        dbportexternal = str(townValues.get("showdbportexternal")).strip().lower() == "true",
        dbportinternal = str(townValues.get("showdbportinternal")).strip().lower() == "true",
        dbpassword = str(townValues.get("showdbpassword")).strip().lower() == "true",
        description = str(townValues.get("showdescription")).strip().lower() == "true",
        active = str(townValues.get("showactive")).strip().lower() == "true",
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
    settings = data.get('settings');
    townValues = data.get('townValues')

    editSettings = db.query(Settings).filter(Settings.town == townValues.get("id")).all()
    for OldSetting in editSettings:
        for NewSetting in settings:
            if OldSetting.varname == NewSetting.get("VarName"):
                OldSetting.setting = NewSetting.get("Value")

    editTown = db.query(Town).filter(Town.id == townValues.get("id")).first()
    show = db.query(Show).filter(Show.town == townValues.get("id")).first()

    town = db.query(Town).filter(Town.name == townValues.get("name")).first()
    if town:
        if town.id != editTown.id:
            return {"error" : "Name"}

    editTown.name = townValues.get("name")
    editTown.wazelink = townValues.get("wazelink")
    editTown.dbhost = townValues.get("dbhost")
    editTown.dbportexternal = townValues.get("dbportexternal")
    editTown.dbportinternal = townValues.get("dbportinternal")
    editTown.dbname = townValues.get("dbname")
    editTown.dbuser = townValues.get("dbuser")
    editTown.dbpassword = townValues.get("dbpassword")
    editTown.description = townValues.get("description")
    editTown.active = str(townValues.get("active")).strip().lower() == "true"
    editTown.coveragearea =  from_shape(wkt.loads(townValues.get("coveragearea")), srid=4326)
    editTown.updatedat = func.now()

    show.name = str(townValues.get("showname")).strip().lower() == "true"
    show.dbname = str(townValues.get("showdbname")).strip().lower() == "true"
    show.dbuser = str(townValues.get("showdbuser")).strip().lower() == "true"
    show.coveragearea = str(townValues.get("showcoveragearea")).strip().lower() == "true"
    show.wazelink = str(townValues.get("showwazelink")).strip().lower() == "true"
    show.dbhost = str(townValues.get("showdbhost")).strip().lower() == "true"
    show.dbportexternal = str(townValues.get("showdbportexternal")).strip().lower() == "true"
    show.dbportinternal = str(townValues.get("showdbportinternal")).strip().lower() == "true"
    show.dbpassword = str(townValues.get("showdbpassword")).strip().lower() == "true"
    show.description = str(townValues.get("showdescription")).strip().lower() == "true"
    show.active = str(townValues.get("showactive")).strip().lower() == "true"
    show.createdat = str(townValues.get("showcreatedat")).strip().lower() == "true"
    show.updatedat = str(townValues.get("showupdatedat")).strip().lower() == "true"

    try:
        db.commit()
        return {"ok" : "ok"} 
    except Exception as e:
        return {"error" : "Db"}

@router.post("/deleteTown")
async def DeleteTown(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    town = db.query(Town).filter(Town.id == data.get("id")).first()
    show = db.query(Show).filter(Show.town == data.get("id")).first()
    settings = db.query(Settings).filter(Settings.town == data.get("id")).all()

    for setting in settings:
        try:
            db.delete(setting)
            db.commit()
        except Exception as e:
            return {"error" : "Db"}

    try:
        db.delete(show)
        db.commit()
    except Exception as e:
        return {"error" : "Db"}

    try:
        db.delete(town)
        db.commit()
    except Exception as e:
        return {"error" : "Db"}

@router.post("/getCoverageArea")
async def GetCoverageArea(data: dict, db: Session = Depends(get_db)):
    town = db.query(Town).filter(Town.name == data.get("name")).first()
    if town:
        print(town)
        return {"coveragearea": to_shape(town.coveragearea).wkt}
    else:
        print(data.get("name"))

@router.post("/getTownSettings")
async def GetTownSettings(data: dict, db: Session = Depends(get_db)):
    town = db.query(Town).filter(Town.name == data.get("name")).first()
    if not town:
        settings = db.query(Settings).filter(Settings.town.is_(None)).all()
        settingsData = [
            {
                "varname": setting.varname,
                "settingname": setting.settingname,
                "setting": setting.setting,
                "description": setting.description,
                "groupName": setting.groupname,
            }
            for setting in settings
        ]
        settingsData.sort(key=lambda x: x["varname"])
        return {"settings": settingsData}
    else:
        settings = db.query(Settings).filter(Settings.town == town.id).all()
        mergedSettings = []
        for default in settings:
            mergedSettings.append({
                "varname": default.varname,
                "settingname": default.settingname,
                "setting": default.setting,
                "description": default.description,
                "groupName": default.groupname,
            })
            mergedSettings.sort(key=lambda x: x["varname"])
        return {"settings": mergedSettings, 'id': town.id}

#######################################
#Default settings routes
#######################################
@router.get("/getSettings")
async def GetSettings(db: Session = Depends(get_db)):
    settings = db.query(Settings).filter(Settings.town == None).all()
    settingsData = [
        {
            "id": setting.id,
            "varname": setting.varname,
            "settingname": setting.settingname,
            "setting": setting.setting,
            "description": setting.description,
            "groupName": setting.groupname,
        }
        for setting in settings
    ]
    settingsData.sort(key=lambda x: x["varname"])
    return {"settings": settingsData}

@router.post("/SaveSettings")
async def SaveSettings(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    setting = db.query(Settings).filter(Settings.id == data.get("Id")).first()
    allsettings = db.query(Settings).filter(Settings.varname == setting.varname).all()

    defaultsettings = db.query(Settings).filter(Settings.town == None).all()
    for defsetting in defaultsettings:
        if defsetting.varname == setting.varname and defsetting.id != setting.id:
            return {"error" : "Name"}    

    setting.settingname = data.get("Name")
    setting.setting = data.get("Value")
    setting.varname = data.get("VarName")
    setting.description = data.get("AllDescription")
    setting.groupname = data.get("AllGroupName")

    for allsetting in allsettings:
        allsetting.settingname = data.get("Name")
        allsetting.varname = data.get("VarName")
        allsetting.description = data.get("AllDescription")
        allsetting.groupname = data.get("AllGroupName")
        
    try:
        db.commit()
    except Exception as e:
        return {"error" : "Db"}


    return {'test': 'test'}

@router.post("/saveNewSetting") #Add new thins in settings too
async def SaveNewSetting(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    NewSetting = Settings(
        varname = data.get('VarName'),
        settingname = data.get('Name'),
        setting = data.get('Value'),
        town = None,
        description =  data.get('AllDescription'),
        groupname =  data.get('AllGroupName')
    )

    settings = db.query(Settings).filter(Settings.town == None).all()
    for setting in settings:
        if setting.varname == NewSetting.varname:
            return {"error" : "Name"}

    try:
        db.add(NewSetting)
        db.commit() 
    except  Exception as e:
        return {"error" : "Db"}

    towns = db.query(Town).all()
    for town in towns:
        NewSetting = Settings(
            varname = data.get('VarName'),
            settingname = data.get('Name'),
            setting = data.get('Value'),
            town = town.id,
            description =  data.get('AllDescription'),
            groupname =  data.get('AllGroupName')
        )
        try:
            db.add(NewSetting)
            db.commit()
        except  Exception as e:
            return {"error" : "Db"}

    return {'ok': 'ok'}

@router.post("/deleteSetting") #Add new thins in settings too
async def DeleteSetting(data: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = db.query(Settings).filter(Settings.varname == data.get("VarName")).all()

    for setting in settings:
        try:
            db.delete(setting)
            db.commit()
        except Exception as e:
            return {"error" : "Db"}
