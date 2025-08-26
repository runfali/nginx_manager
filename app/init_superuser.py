from sqlalchemy.orm import Session
from app.core.database import get_db, engine, Base
from app.models.user import User
from app.core.security import get_password_hash


def create_superuser(username: str, email: str, password: str):
    # 创建数据库会话
    db = Session(engine)

    try:
        # 检查用户是否已存在
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"用户 {username} 已存在")
            return

        # 创建超级管理员用户
        hashed_password = get_password_hash(password)
        superuser = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_superuser=True,
            is_active=True,
        )

        # 添加到数据库并提交
        db.add(superuser)
        db.commit()
        print(f"超级管理员 {username} 创建成功")

    except Exception as e:
        print(f"创建超级管理员失败: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    # 确保数据库表已创建
    Base.metadata.create_all(bind=engine)

    # 设置超级管理员信息
    username = input("请输入用户名: ")
    email = input("请输入邮箱: ")
    password = input("请输入密码: ")

    # 创建超级管理员
    create_superuser(username, email, password)
