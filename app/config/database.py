from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+psycopg2://postgres:1234@db.vgpnerdevdazcckwrnze.supabase.co:5432/postgres"
#                  ^ User   ^Passwort                    ^ Host                                   ^ Port  ^ DB-Name

engine = create_engine(DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
