from sqlalchemy import Column, Boolean, String, Integer, ForeignKey, Float
from sqlalchemy.orm import relationship
from database import Base


class Role(Base):
    __tablename__ = 'roles'
    
    role_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    is_admin = Column(Boolean, default=False)


class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True, index=True)
    username  = Column(String, index=True, unique=True)
    password = Column(String)
    is_email_verified = Column(Boolean, default=False, index=True)
    role = Column(String, ForeignKey('roles.name'))
    
    roles = relationship("Role", backref="users")
    ratings = relationship("Rating", back_populates="user")


class Recipe(Base):
    __tablename__ = 'recipes'
    
    recipe_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, index=True)
    ingredients = Column(String, index=True)
    instructions = Column(String, index=True)
    is_veg = Column(Boolean, default=True, index=True)
    overall_rating = Column(Float, default=0, nullable=False) 

    ratings = relationship("Rating", back_populates="recipe") 
    
class Rating(Base):
    __tablename__ = "ratings"

    rating_id = Column(Integer, primary_key=True, index=True)
    recipe_name = Column(String, nullable=False)
    ratings = Column(Float, nullable=False)
    recipe_id = Column(Integer, ForeignKey("recipes.recipe_id"))
    user_name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id")) 
    reviews = Column(String, nullable=True)
    previous_ratings = Column(Float, nullable=False) 
    previous_reviews = Column(String, nullable=True)

    user = relationship("User", back_populates="ratings") 
    recipe = relationship("Recipe", back_populates="ratings")
    