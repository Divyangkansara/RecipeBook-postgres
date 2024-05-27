import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status
from database import SessionLocal
from models import User, Role
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm.exc import NoResultFound
from typing import List , Optional

router = APIRouter(
    prefix = '/auth',
    tags = ['auth']
)

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token')

EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT=587 
EMAIL_USE_TLS=True  
EMAIL_HOST_USER = 'divyang.kansara@technostacks.com' 
EMAIL_HOST_PASSWORD= 'xjix ucjb dkgj uzfx'

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = 'User'
    is_email_verified: bool = False
    
class Token(BaseModel):
    access_token: str
    token_type: str
    
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        

class CreateRoleRequest(BaseModel):
    name: str
    is_admin: bool = False


#  Create Roles
@router.post("/roles", status_code=status.HTTP_201_CREATED)
async def create_role(create_role_req: CreateRoleRequest, db: Session = Depends(get_db)):
    role_exists = db.query(Role).filter(Role.name == create_role_req.name).first()
    
    if role_exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role already exists")

    role = Role(name=create_role_req.name, is_admin=create_role_req.is_admin)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

#  Generate Token
def create_access_token(username: str, user_id: int, role: str, expires_delta: timedelta):
    encode = {'sub': username, 'id': user_id, 'role': role}
    expires = datetime.utcnow() + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


#  Email Setup
def send_email(recipient_email: str, subject: str, message: str):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_HOST_USER
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'html'))

    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls() 
        server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        response = server.sendmail(EMAIL_HOST_USER, recipient_email, msg.as_string())
        print(response)

def send_email_async(recipient_email: str, subject: str, message: str):
    thread = threading.Thread(target=send_email, args=(recipient_email, subject, message))
    thread.start()
    
    
#  Create New User
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.name == user.role).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    new_user = User(
        username=user.username,
        password=pwd_context.hash(user.password),
        is_email_verified=user.is_email_verified,
        role=role.name
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    token = create_access_token(user.username, new_user.user_id, new_user.role, timedelta(minutes=10))
    print('➡ auth.py:119 token:', token)
    
    base_url = f'http://127.0.0.1:8000/auth/verify-email?token={token}'
    
    recipient_email = new_user.username
    subject = "Verify your email"
    html_txt = f"""<!DOCTYPE html>
        <html lang="en">
            <head></head>
            <body>
            Click the following link to verify your email: <a href='{base_url}'>link</a>
            </body>
        </html>"""
    
    send_email_async(recipient_email, subject, html_txt)
    
    return {"user": new_user, "token": token}

    
#  Email Verification
@router.get("/verify-email")
async def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get('id')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid Link"
            )
            
        user = db.query(User).filter(User.user_id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid Link"
            )
        
        user.is_email_verified = True
        db.commit()
        
        return {"message": "Email verified successfully!!"}

    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token."
        )
        

#  Login for Access
@router.post("/token", response_model=Token)
async def login_for_access(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
        
    token = create_access_token(user.username, user.user_id, user.role, timedelta(minutes=10))

    return {"access_token": token, "token_type": "bearer"}
         
#  logout  
@router.post("/logout")
async def logout():
    return JSONResponse(content={"message": "Logged out successfully"})        
        
#  Authenticate User
def authenticate_user(username: str, password: str, db):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not pwd_context.verify(password, user.password):
        return False
    return user


#  Get Current User
async def get_current_user(token: str = Depends(oauth2_bearer)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print('➡ auth.py:187 payload:', payload)
        username: str = payload.get('sub') 
        print('➡ auth.py:189 username:', username)
        user_id: int = payload.get('id')
        print('➡ auth.py:191 user_id:', user_id)
        role: str = payload.get('role')
        print('➡ auth.py:212 role:', role)
        print("username::::",username)
        print("user_id::::",user_id)
        if username is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        return {"username": username, "user_id": user_id, "role": role}
    except JWTError:
        print ("CAME HERE:::::::")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    
    