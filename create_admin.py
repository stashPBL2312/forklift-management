from sqlalchemy.orm import Session
from app.database import get_db, engine, SessionLocal
from app.models import User
from app.routes.auth import hash_password

# Create a database session
db = SessionLocal()

# Check if admin user already exists
existing_user = db.query(User).filter(User.email == "rey@admin123.com").first()

if existing_user:
    print("Admin user already exists!")
else:
    # Create admin user with specified credentials
    admin_user = User(
        name="Admin",
        email="rey@admin123.com",
        password=hash_password("nimda123"),
        role="admin"
    )
    
    # Add to database and commit
    db.add(admin_user)
    db.commit()
    print("Admin user created successfully!")

# Close the session
db.close()