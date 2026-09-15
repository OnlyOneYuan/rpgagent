from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from passlib.context import CryptContext
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

# 假设你的 html 文件放在项目根目录的 templates 文件夹下，命名为 game.html
templates = Jinja2Templates(directory="templates")

# ================= 1. 数据库配置与 get_db 定义 =================
DATABASE_URL = "sqlite+aiosqlite:///./game.db"

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

# 核心：定义 get_db 依赖注入函数
async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ================= 2. 数据库模型 (ORM) =================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    current_page = Column(String, default="inventory")
    is_in_combat = Column(Boolean, default=False)

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    container_type = Column(String, default="backpack")  # backpack / warehouse
    slot_index = Column(Integer, default=0)

# ================= 3. Pydantic 数据校验模型 =================
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class ItemMove(BaseModel):
    target_container: str
    slot_index: int

class UISettings(BaseModel):
    current_page: str
    is_in_combat: bool

# ================= 4. FastAPI 路由与接口 =================
app = FastAPI(title="RPG 游戏后端")
@app.get("/game")
async def game_page(request: Request):
    return templates.TemplateResponse("agent\web\static\index.html", {"request": request})
# 启动时创建数据库表
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# 【接口 1：用户注册】
@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # 检查用户名是否已存在
    existing_user = await db.execute(
        User.__table__.select().where(User.username == user_data.username)
    )
    if existing_user.first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 密码哈希并创建新用户
    hashed_password = pwd_context.hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {"message": "注册成功", "user_id": new_user.id}

# 【接口 2：物品拖拽移动】
@app.patch("/items/{item_id}/move")
async def move_item(item_id: int, move_data: ItemMove, db: AsyncSession = Depends(get_db)):
    result = await db.execute(Item.__table__.select().where(Item.id == item_id))
    item = result.first()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    
    # 更新物品位置
    item.container_type = move_data.target_container
    item.slot_index = move_data.slot_index
    await db.commit()
    return {"message": f"物品 {item_id} 已移动至 {move_data.target_container} 的 {move_data.slot_index} 槽位"}

# 【接口 3：界面切换状态保存】
@app.put("/ui/settings")
async def update_ui_settings(settings: UISettings, db: AsyncSession = Depends(get_db)):
    # 这里假设通过 Header 或 Token 获取当前用户，这里简化为更新第一条数据作演示
    result = await db.execute(User.__table__.select().limit(1))
    user = result.first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.current_page = settings.current_page
    user.is_in_combat = settings.is_in_combat
    await db.commit()
    return {"message": "界面状态已更新", "current_page": user.current_page, "is_in_combat": user.is_in_combat}