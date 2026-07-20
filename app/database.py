from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
    )

Base = declarative_base()

def get_db():
    # fastapi数据库依赖函数
    # 通过depends(get_db)注入到路由中，提供数据库会话
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # 初始化数据库
    # mvp阶段使用sqlaichemy的create_all方法创建表，后续可以使用alembic进行数据库迁移管理
    from app import models

    Base.metadata.create_all(bind=engine)