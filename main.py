import auth
from fastapi import FastAPI, Request, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect 
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal, Base, engine
from models import Recipe as RecipeModel, Rating as RatingModel, User, Role
from passlib.context import CryptContext
from auth import get_current_user
from typing import Union, List
from enum import Enum

app = FastAPI()
app.include_router(auth.router)
Base.metadata.create_all(bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

templates = Jinja2Templates(directory="templates")

app.mount("/static", StaticFiles(directory="static"), name="static")

class OrderEnum(str, Enum):
    asc = "asc"
    desc = "desc"

class RecipeCreate(BaseModel):
    name: str
    description: str
    ingredients: str
    instructions: str
    is_veg: bool = True

class RatingCreate(BaseModel):
    ratings: Union[float, int]
    reviews: str

    class Config:
        orm_mode = True
        
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        

@app.websocket("/ws/ratings/")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"You wrote: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# @app.get("/Test-socket")
# async def test_socket(first:str):
#     # data = await websocket.receive_text()
#     await manager.broadcast(f"You wrote: {first}")
#     # await websocket.send_text(f"Hey! Test Socket-- {first}")
#     return {"message": f"{first}"}
def get_recipe(db, recipe_id):
    recipe = db.query(RecipeModel).filter(RecipeModel.recipe_id == recipe_id).first()
    return recipe

def authorize_user(users: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id ==  users['user_id']).first()
    if not user:
        raise HTTPException(status_code=403, detail="User not found")
    role = users.get('role')
    if not role:
        raise HTTPException(status_code=403, detail="User role not found")
    role = db.query(Role).filter(Role.name == role).first()
    if role and role.is_admin:
        return
    raise HTTPException(status_code=403, detail="Permission denied, user is not an admin")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    recipes = db.query(RecipeModel).all()
    return templates.TemplateResponse("index.html", {"request": request, "recipes": recipes})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/verify-email", response_class=HTMLResponse)
async def verify_email_page(request: Request):
    return templates.TemplateResponse("verify_email.html", {"request": request})

@app.post("/logout")
async def logout():
    return {"message": "Logged out successfully"}

@app.get("/recipes/new", response_class=HTMLResponse)
async def add_new_recipe_page(request: Request):
    return templates.TemplateResponse("add_recipe.html", {"request": request})


#  CRUD 
@app.post("/recipes/", dependencies=[Depends(authorize_user)])
async def create_recipe(recipe: RecipeCreate, user: Session = Depends(get_current_user), db: Session = Depends(get_db)):
    if not recipe.name or not recipe.ingredients or not recipe.instructions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name, ingredients, and instructions are required.")
    
    db_recipe = RecipeModel(**recipe.dict())
    db.add(db_recipe)
    db.commit()
    db.refresh(db_recipe)
    
    await manager.broadcast("New recipe has been added!!!")
    
    return db_recipe

@app.get("/recipes/")
async def read_recipes(user: Session = Depends(get_current_user), db: Session = Depends(get_db)):
    recipes = db.query(RecipeModel).all()
    return recipes

# @app.get("/recipe/{recipe_id}")
# async def read_particular_recipe(recipe_id: int, user: Session = Depends(get_current_user), db: Session = Depends(get_db)):
#     db_recipe = get_recipe(db, recipe_id)
#     if db_recipe is None:   
#         raise HTTPException(status_code=404, detail="Recipe not found")
#     return db_recipe


@app.get("/recipes/{recipe_id}", response_class=HTMLResponse)
async def read_recipe(recipe_id: int, request: Request, db: Session = Depends(get_db)):
    recipe = db.query(RecipeModel).filter(RecipeModel.recipe_id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return templates.TemplateResponse("recipe_detail.html", {"request": request, "recipe": recipe})

@app.put("/recipes/{recipe_id}", dependencies=[Depends(authorize_user)])
async def update_recipe(recipe_id: int, recipe: RecipeCreate, user: Session = Depends(get_current_user), db: Session = Depends(get_db)):
    db_recipe = get_recipe(db, recipe_id)
    if db_recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    for attr, value in recipe.dict().items():
        setattr(db_recipe, attr, value)
    db.commit()
    db.refresh(db_recipe)
    
    await manager.broadcast("Recipe has been updated successfully!!")
    
    return db_recipe

@app.delete("/recipes/{recipe_id}", dependencies=[Depends(authorize_user)])
async def delete_recipe(recipe_id: int, user: Session = Depends(get_current_user), db: Session = Depends(get_db)):
    db_recipe = get_recipe(db, recipe_id)
    if db_recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    db.delete(db_recipe)
    db.commit()
    return {"message": "Recipe deleted successfully"}

@app.get("/recipes/{recipe_id}/rate", response_class=HTMLResponse)
async def rate_recipe_page(recipe_id: int, request: Request, db: Session = Depends(get_db)):
    recipe = db.query(RecipeModel).filter(RecipeModel.recipe_id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return templates.TemplateResponse("rate_recipe.html", {"request": request, "recipe": recipe})

# @app.post("/recipes/{recipe_id}/ratings/", dependencies=[Depends(get_current_user)])
# def rate_recipe(recipe_id: int, rating: RatingCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
#     user_id = user['user_id']
#     existing_rating = db.query(RatingModel).filter(RatingModel.recipe_id == recipe_id, RatingModel.user_id == user_id).first()
#     if existing_rating:
#         raise HTTPException(status_code=400, detail="User has already rated this recipe")
#     recipe = get_recipe(db, recipe_id)
#     if not recipe:
#         raise HTTPException(status_code=404, detail="Recipe not found")
#     user_db = db.query(User).filter(User.user_id == user_id).first()
#     if not user_db:
#         raise HTTPException(status_code=404, detail="User not found")
#     db_rating = RatingModel(
#         ratings=rating.ratings,         
#         recipe_id=recipe_id,
#         user_id=user_id,
#         user_name=user_db.username,
#         recipe_name=recipe.name,
#         reviews=rating.reviews
#     )
#     db.add(db_rating)
#     db.commit()
#     db.refresh(db_rating)
#     return db_rating

def update_overall_rating(db: Session, recipe_id: int):
    overall_rating = db.query(func.avg(RatingModel.ratings)).filter(RatingModel.recipe_id == recipe_id).scalar()
    recipe = db.query(RecipeModel).filter(RecipeModel.recipe_id == recipe_id).first()
    if recipe:
        recipe.overall_rating = overall_rating
        db.commit()
        db.refresh(recipe)


@app.post("/recipes/{recipe_id}/ratings/", dependencies=[Depends(get_current_user)])
async def rate_recipe(recipe_id: int, rating: RatingCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = user['user_id']
    existing_rating = db.query(RatingModel).filter(RatingModel.recipe_id == recipe_id, RatingModel.user_id == user_id).first()
    if existing_rating:
        raise HTTPException(status_code=400, detail="User has already rated this recipe")
    recipe = get_recipe(db, recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    user_db = db.query(User).filter(User.user_id == user_id).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="User not found")
    db_rating = RatingModel(
        ratings=rating.ratings,
        recipe_id=recipe_id,
        user_id=user_id,
        user_name=user_db.username,
        recipe_name=recipe.name,
        reviews=rating.reviews
    )
    db.add(db_rating)
    db.commit()
    db.refresh(db_rating)
    
    update_overall_rating(db, recipe_id)
    
    await manager.broadcast(f"New rating added for recipe {recipe_id}: {rating.ratings}")
    
    return db_rating



@app.get("/recipes/{recipe_id}/ratings/", dependencies=[Depends(get_current_user)])
def get_ratings_for_recipe(recipe_id: int, order: OrderEnum = Query(OrderEnum.asc), db: Session = Depends(get_db)):
    if order == "asc":
        ratings = db.query(RatingModel).filter(RatingModel.recipe_id == recipe_id).order_by(RatingModel.ratings.asc()).all()
    else:
        ratings = db.query(RatingModel).filter(RatingModel.recipe_id == recipe_id).order_by(RatingModel.ratings.desc()).all()
    if not ratings:
        raise HTTPException(status_code=404, detail="No ratings found for this recipe")
    return ratings

@app.put("/recipes/{recipe_id}/ratings/{user_id}", dependencies=[Depends(get_current_user)])
async def update_rating_review_for_recipe(recipe_id: int, user_id: int, new_rating: float, new_review: str, db: Session = Depends(get_db)):
    rating = db.query(RatingModel).filter(RatingModel.recipe_id == recipe_id, RatingModel.user_id == user_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found for this user and recipe")
    rating.previous_ratings = rating.ratings
    rating.previous_reviews = rating.reviews
    rating.ratings = new_rating
    rating.reviews = new_review
    db.commit()
    
    update_overall_rating(db, recipe_id)
    
    await manager.broadcast(f"Rating updated for recipe {recipe_id}: {new_rating}")
    
    return {"message": "Rating and review updated successfully"}



