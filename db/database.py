from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://postgres:1234@db.vgpnerdevdazcckwrnze.supabase.co:5432/postgres"
# rico wie geht das nochmal mit den passwörtern??
engine = create_engine(DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)